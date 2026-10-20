"""The grading report must exclude what it says it excludes and compare components
only on matches where every compared component exists."""
from datetime import datetime, timezone

import pytest

from app.backtest.tennis_predictions import DEFAULT_MODEL_VERSION, report
from app.repositories.predictions import GradedPrediction
from app.services.tennis.track_record import build_prediction_grading

START = datetime(2026, 9, 20, 18, tzinfo=timezone.utc)


def _row(match_id: int, **over) -> GradedPrediction:
    base = dict(
        match_id=match_id, tour="ATP", start_utc=START, generated_at=START.replace(hour=13),
        model_version=DEFAULT_MODEL_VERSION, p1_won=match_id % 2 == 0, completed_score=True,
        elo_prob=0.6, ml_prob=0.62, market_prob=0.55, ensemble_prob=0.6,
        market_book="draftkings", closing_market_prob=0.58,
    )
    base.update(over)
    return GradedPrediction(**base)


def _line(text: str, starts: str) -> str:
    return next(line for line in text.splitlines() if line.strip().startswith(starts))


ROWS = [
    _row(1), _row(2), _row(3), _row(4),
    _row(5, market_prob=None, closing_market_prob=None),   # model table only
    _row(6, completed_score=False),                         # retirement
    _row(7, model_version="ensemble-v1+lgbm-v5"),           # other version
    _row(8, tour="CHALLENGER", ml_prob=None),               # pair only
]


def test_exclusions_are_counted():
    text = report(ROWS)
    assert "settled matches with a pre-start prediction: 8" in text
    assert "excluded, other model versions:              1" in text
    assert "excluded, retirements and walkovers:         1" in text
    assert "graded:                                      6" in text


def test_every_section_is_present():
    text = report(ROWS)
    for header in ("Model components", "Against the market", "Paired log-loss difference",
                   "Calibration", "Closing-line value"):
        assert header in text


def test_components_share_one_subset_per_table():
    model_table, market_table = report(ROWS).split("Against the market")[0], report(ROWS).split("Against the market")[1]
    assert _line(model_table, "ATP ").split()[1] == "5"
    assert _line(market_table, "ATP ").split()[1] == "4"
    assert "CHALLENGER      0  (no matches with every component)" in model_table


def test_clv_counts_rows_with_both_prices_and_does_not_need_ml():
    # Rows 1-4 and the Challenger row 8 (no ML) have both prices; row 5 has neither.
    assert "eligible    5" in _line(report(ROWS), "all ")


@pytest.mark.parametrize("model_version", [DEFAULT_MODEL_VERSION, "ensemble-v3+lgbm-none"])
def test_ensemble_market_cli_matches_service_scores_counts_errors_and_signals(model_version):
    rows = ROWS + [
        _row(9, elo_prob=None, ml_prob=None),
        _row(10, elo_prob=0.99, ml_prob=None, ensemble_prob=0.55),
        _row(11, ensemble_prob=None),
        _row(12, tour="WTA", ml_prob=None),
        _row(13, tour="CHALLENGER", ml_prob=None, model_version="ensemble-v3+lgbm-none"),
    ]
    grading = build_prediction_grading(rows, model_version, START)
    section = report(rows, model_version).split("Ensemble versus market", 1)[1].split("Closing-line value", 1)[0]
    scores, paired = section.split("  Paired ensemble-minus-market log loss", 1)

    for group in grading.ensemble_market_groups:
        cells = _line(scores, group.group + " ").split()
        assert int(cells[1]) == group.n
        paired_line = _line(paired, group.group + " ")
        assert f"n={group.n}" in paired_line
        if not group.n:
            assert "no ensemble-market pairs" in paired_line
            continue
        market, ensemble = group.components
        assert [float(cell) for cell in cells[2:]] == pytest.approx(
            [market.log_loss, market.brier, ensemble.log_loss, ensemble.brier], abs=0.00005,
        )
        diff = ensemble.vs_market
        se = f"{diff.standard_error:.4f}" if diff.standard_error is not None else "n/a"
        assert f"ensemble {diff.mean:+.4f} +/- {se}  signal={diff.signal}" in paired_line


def test_ensemble_market_cli_reports_empty_samples_and_fallback_boundary():
    section = report([_row(1, market_prob=None)]).split("Ensemble versus market", 1)[1]

    assert section.count("n=0 (no ensemble-market pairs)") == 4
    assert "Market-free fallback rows are excluded" in section
