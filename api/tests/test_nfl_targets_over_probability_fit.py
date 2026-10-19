import sys

import pytest

from app.backtest import nfl_targets_over_probability_fit as cli
from app.core.nfl_over_probability import QUANTILE_LEVELS
from app.core.nfl_projection_backtest import ReplayCase
from app.core.nfl_targets_over_probability import ScoredLine, TargetsCaseCoverage

FIT_COVERAGE = TargetsCaseCoverage(season=2024, total=10, no_baseline=2, thin_baseline=1, zero_projection=1, cases=6)
SCORED_COVERAGE = TargetsCaseCoverage(season=2025, total=400, missing_actual=0, cases=300)


def _scored(cases: int) -> list[ScoredLine]:
    # Every case at the line nearest its projection (5.5): half go over, each predicted 0.5.
    positions = ("RB", "WR", "TE")
    return [
        ScoredLine(
            case=ReplayCase(player_id=player_id, game_id=1, week=5, position=positions[player_id % 3],
                            market="receiving_targets", projection=5.0 + (player_id % 3) * 0.2,
                            actual=6.0 if player_id % 2 else 4.0),
            line=5.5, p_over=0.5, normal_p_over=0.4, over=bool(player_id % 2),
        )
        for player_id in range(cases)
    ]


@pytest.fixture
def no_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "app.db.pool", None)
    monkeypatch.setitem(sys.modules, "app.repositories.nfl_targets", None)


def test_report_prints_the_pooled_verdict_row() -> None:
    text = cli.report(FIT_COVERAGE, SCORED_COVERAGE, _scored(300))

    assert "2025 holdout read 8 (no projection verdict)" in text
    assert "nfl-targets-v1" in text and "nfl-targets-pover-v1" in text
    assert "  receiving_targets           300     300   0.000   0.000  0.2500  0.2600  show" in text


def test_report_prints_information_rows_without_a_verdict() -> None:
    text = cli.report(FIT_COVERAGE, SCORED_COVERAGE, _scored(300))

    assert "  RB                          100     100   0.000      --  0.2500  0.2600" in text
    assert "  all positions               300      0.500     0.500   0.400" in text
    assert "  WR                          100      0.500" in text


def test_report_prints_coverage_for_both_seasons() -> None:
    text = cli.report(FIT_COVERAGE, SCORED_COVERAGE, _scored(300))

    assert "  2024         10          0        0        2      1          1      6" in text
    assert "  2025        400          0        0        0      0          0    300" in text


def test_too_few_cases_read_insufficient() -> None:
    scored = _scored(299)
    assert cli.verdict(scored) == "insufficient"
    assert "insufficient cases" in cli.report(FIT_COVERAGE, SCORED_COVERAGE, scored)


def test_an_empty_scored_set_is_insufficient_with_no_metrics() -> None:
    text = cli.report(FIT_COVERAGE, SCORED_COVERAGE, [])

    assert cli.verdict([]) == "insufficient"
    assert "Verdict: insufficient (no 2025 pairs scored)" in text
    assert "Verdict (positions pooled)" not in text and "Reliability" not in text


def test_help_needs_no_database(no_database: None, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.parse_args(["--help"])

    assert exit_info.value.code == 0
    assert "2024" in capsys.readouterr().out


def test_no_season_option_exists(no_database: None) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.parse_args(["--season", "2025"])
    assert exit_info.value.code == 2


def _exec(text: str) -> dict[str, object]:
    namespace: dict[str, object] = {}
    exec(compile(text, "<rendered>", "exec"), namespace)
    return namespace


def test_render_a_shown_fit_round_trips() -> None:
    quantiles = tuple(round(level * 2, 4) for level in QUANTILE_LEVELS)
    namespace = _exec(cli.render_module(True, {"WR": quantiles, "RB": quantiles}))

    assert namespace["SHOWN"] is True
    assert namespace["FIT_SEASON"] == 2024 and namespace["SCORED_SEASON"] == 2025
    assert namespace["FIT_PROJECTION_MODEL_VERSION"] == "nfl-targets-v1"
    assert namespace["OVER_PROBABILITY_VERSION"] == "nfl-targets-pover-v1"
    assert namespace["QUANTILES_BY_POSITION"] == {"RB": quantiles, "WR": quantiles}


def test_render_a_hidden_fit_holds_no_tables() -> None:
    text = cli.render_module(False, {})
    namespace = _exec(text)

    assert namespace["SHOWN"] is False
    assert namespace["QUANTILES_BY_POSITION"] == {}
    assert "Do not edit." in text


def test_the_generated_fit_matches_the_served_versions() -> None:
    from app.core import nfl_targets_over_probability_fit as fit
    from app.core.nfl_targets_over_probability import NFL_TARGETS_OVER_PROBABILITY_VERSION
    from app.core.nfl_targets_projection import NFL_TARGETS_MODEL_VERSION

    assert fit.FIT_PROJECTION_MODEL_VERSION == NFL_TARGETS_MODEL_VERSION
    assert fit.OVER_PROBABILITY_VERSION == NFL_TARGETS_OVER_PROBABILITY_VERSION
    assert (fit.FIT_SEASON, fit.SCORED_SEASON) == (2024, 2025)
    if fit.SHOWN:
        assert set(fit.QUANTILES_BY_POSITION) == {"RB", "WR", "TE"}
        for quantiles in fit.QUANTILES_BY_POSITION.values():
            assert len(quantiles) == len(QUANTILE_LEVELS)
            assert list(quantiles) == sorted(quantiles)
    else:
        assert fit.QUANTILES_BY_POSITION == {}
