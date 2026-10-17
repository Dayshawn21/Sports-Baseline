"""The grading report must exclude what it says it excludes and compare components
only on matches where every compared component exists."""
from datetime import datetime, timezone

from app.backtest.tennis_predictions import DEFAULT_MODEL_VERSION, report
from app.repositories.predictions import GradedPrediction

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
    _row(8, tour="CHALLENGER", ml_prob=None),               # no ML: dropped from both tables
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
