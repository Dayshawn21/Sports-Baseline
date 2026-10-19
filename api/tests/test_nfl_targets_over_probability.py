from statistics import stdev

import pytest

from app.core import nfl_targets_over_probability as rule
from app.core.nfl_over_probability import QUANTILE_LEVELS, ratio_quantiles
from app.core.nfl_over_probability_calibration import CalibrationBin, CalibrationReport
from app.core.nfl_projection_backtest import ReplayCase
from app.core.nfl_targets_over_probability import (
    NFL_TARGETS_OVER_PROBABILITY_VERSION, PositionFit, fit_positions, score_cases, targets_cases,
    targets_display_verdict,
)
from app.core.nfl_targets_projection import TargetsObservation, TargetsProjectionInput, TargetsReplayRow


def history(season: int, counts: tuple[float | None, ...]) -> tuple[TargetsObservation, ...]:
    return tuple(
        TargetsObservation(game_id=100 + week, season=season, week=week, start_utc=None, targets=count)
        for week, count in enumerate(counts, start=1)
    )


def row(
    counts: tuple[float | None, ...] = (4.0, 6.0, 5.0, 5.0),
    actual: float | None = 7.0,
    season: int = 2025,
    week: int = 8,
    position: str = "WR",
    player_id: int = 1,
) -> TargetsReplayRow:
    return TargetsReplayRow(
        player_id=player_id, game_id=900 + player_id, week=week, position=position,
        input=TargetsProjectionInput(season=season, week=week, observations=history(season, counts)),
        actual=actual,
    )


def case(projection: float, actual: float, position: str = "WR", player_id: int = 1) -> ReplayCase:
    return ReplayCase(
        player_id=player_id, game_id=1, week=5, position=position, market="receiving_targets",
        projection=projection, actual=actual,
    )


def report(ece: float = 0.01, bins: tuple[CalibrationBin, ...] = (), brier: float = 0.20) -> CalibrationReport:
    return CalibrationReport(n=1000, brier=brier, ece=ece, bins=bins, worst_gap=None)


def test_a_2025_row_becomes_a_case_without_the_2024_only_guard() -> None:
    result = targets_cases([row()], 2025)

    assert result.cases == (case_from(row(), 5.0),)
    assert result.coverage.total == 1 and result.coverage.cases == 1


def case_from(source: TargetsReplayRow, projection: float) -> ReplayCase:
    assert source.actual is not None
    return ReplayCase(
        player_id=source.player_id, game_id=source.game_id, week=source.week, position=source.position,
        market="receiving_targets", projection=projection, actual=source.actual,
    )


@pytest.mark.parametrize("bad", [
    row(season=2024),
    row(position="QB"),
    row(week=19),
])
def test_a_wrong_season_position_or_week_is_rejected(bad: TargetsReplayRow) -> None:
    with pytest.raises(ValueError):
        targets_cases([bad], 2025)


def test_a_duplicate_player_game_is_rejected() -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        targets_cases([row(), row()], 2025)


def test_dropped_rows_are_counted_by_reason() -> None:
    result = targets_cases([
        row(actual=None, player_id=1),
        row(actual=-1.0, player_id=2),
        row(counts=(), player_id=3),
        row(counts=(4.0, 5.0, None), player_id=4),
        row(counts=(0.0, 0.0, 0.0, 0.0), player_id=5),
        row(player_id=6),
    ], 2025)
    coverage = result.coverage

    assert (coverage.missing_actual, coverage.invalid_actual, coverage.no_baseline) == (1, 1, 1)
    assert (coverage.thin_baseline, coverage.zero_projection, coverage.cases) == (1, 1, 1)
    assert coverage.total == 6
    assert [item.player_id for item in result.cases] == [6]


def test_fit_takes_ratio_quantiles_and_the_error_spread_per_position() -> None:
    fits = fit_positions([
        case(4.0, 2.0), case(4.0, 4.0), case(4.0, 6.0),
        case(2.0, 1.0, position="RB"), case(2.0, 3.0, position="RB"),
        case(0.0, 1.0, position="TE"), case(0.0, 0.0, position="TE"),
    ])

    assert fits["WR"].quantiles == ratio_quantiles([(4.0, 2.0), (4.0, 4.0), (4.0, 6.0)])
    assert len(fits["WR"].quantiles) == len(QUANTILE_LEVELS)
    assert fits["WR"].sigma == pytest.approx(stdev([-2.0, 0.0, 2.0]))
    assert fits["RB"].sigma == pytest.approx(stdev([-1.0, 1.0]))
    assert "TE" not in fits


def test_a_position_without_a_fit_is_not_scored() -> None:
    fits = fit_positions([case(4.0, 3.0), case(4.0, 5.0)])
    assert score_cases(fits, [case(3.0, 4.0, position="TE")]) == []


def test_a_zero_projection_is_never_scored() -> None:
    fits = {"WR": PositionFit(quantiles=tuple(level * 2 for level in QUANTILE_LEVELS), sigma=1.0)}
    assert score_cases(fits, [case(0.0, 1.0)]) == []


def test_each_case_is_scored_at_its_synthetic_lines() -> None:
    fits = fit_positions([case(6.0, actual) for actual in (2.0, 4.0, 6.0, 8.0, 10.0)])
    scored = score_cases(fits, [case(6.0, 7.0)])

    # floor(6 * m) + 0.5 for m in 0.5, 0.75, 1.0, 1.25, 1.5.
    assert [line.line for line in scored] == [3.5, 4.5, 6.5, 7.5, 9.5]
    assert [line.over for line in scored] == [True, True, True, False, False]
    assert all(0.0 <= line.p_over <= 1.0 and 0.0 <= line.normal_p_over <= 1.0 for line in scored)
    assert scored[0].p_over > scored[-1].p_over


def test_verdict_needs_three_hundred_cases() -> None:
    assert targets_display_verdict(299, report(), 0.25) == "insufficient"
    assert targets_display_verdict(300, report(), 0.25) == "show"


def test_ece_at_the_limit_passes_and_above_hides() -> None:
    assert targets_display_verdict(300, report(ece=0.02), 0.25) == "show"
    assert targets_display_verdict(300, report(ece=0.0201), 0.25) == "hide"


def test_a_large_bin_at_the_gap_limit_passes_and_beyond_hides() -> None:
    at_limit = (CalibrationBin(n=200, mean_predicted=0.40, observed=0.45),)
    beyond = (CalibrationBin(n=200, mean_predicted=0.40, observed=0.46),)
    assert targets_display_verdict(300, report(bins=at_limit), 0.25) == "show"
    assert targets_display_verdict(300, report(bins=beyond), 0.25) == "hide"


def test_a_small_bin_far_off_is_ignored() -> None:
    small = (CalibrationBin(n=199, mean_predicted=0.10, observed=0.60),)
    assert targets_display_verdict(300, report(bins=small), 0.25) == "show"


def test_brier_equal_to_the_normal_passes_and_worse_hides() -> None:
    assert targets_display_verdict(300, report(brier=0.20), 0.20) == "show"
    assert targets_display_verdict(300, report(brier=0.2001), 0.20) == "hide"


def test_rule_constants_and_version_are_pinned() -> None:
    assert (rule.MIN_CASES, rule.MAX_ECE, rule.MAX_BIN_GAP, rule.MIN_BIN_PAIRS) == (300, 0.02, 0.05, 200)
    assert NFL_TARGETS_OVER_PROBABILITY_VERSION == "nfl-targets-pover-v1"
    assert NFL_TARGETS_OVER_PROBABILITY_VERSION != "nfl-pover-v1"
