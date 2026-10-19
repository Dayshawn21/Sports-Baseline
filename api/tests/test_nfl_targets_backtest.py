import pytest

from app.core.nfl_targets_backtest import REGULAR_SEASON_WEEKS, select_baseline
from app.core.nfl_targets_projection import TargetsObservation, TargetsProjectionInput, TargetsReplayRow

# Weeks 1-8 give B = 5 and R (weeks 8 to 4) = 8, so recent_base = 6.5.
HISTORY = (0.0, 0.0, 0.0, 0.0, 10.0, 10.0, 10.0, 10.0)


def _row(
    player_id: int,
    actual: float | None,
    *,
    history: tuple[float | None, ...] = HISTORY,
    prob: float | None = 0.7,
    is_home: bool | None = True,
    week: int = 9,
    season: int = 2024,
    position: str = "WR",
    game_id: int | None = None,
) -> TargetsReplayRow:
    observations = tuple(
        TargetsObservation(1000 * player_id + index, season, index, None, value)
        for index, value in enumerate(history, start=1)
    )
    return TargetsReplayRow(
        player_id, game_id or 100 + week, week, position,
        TargetsProjectionInput(season, week, observations, prob, is_home), actual,
    )


def _rows(n: int, actual: float, **kwargs: object) -> list[TargetsReplayRow]:
    return [_row(player_id, actual, **kwargs) for player_id in range(1, n + 1)]


def test_recent_form_stacks_on_an_accepted_moneyline_factor() -> None:
    result = select_baseline(_rows(300, 7.02))

    moneyline, recent = result.comparisons
    assert (moneyline.arm, moneyline.incumbent, moneyline.verdict) == ("moneyline", "reference", "adopt")
    assert (recent.arm, recent.incumbent, recent.verdict) == ("recent_form", "moneyline", "adopt")
    assert {case.projection for case in result.cases_by_arm["recent_form"]} == {7.02}
    assert (result.selected_arm, result.moneyline_scaled, result.recent_form) == ("recent_form", True, True)


def test_rejected_moneyline_leaves_recent_form_unscaled_against_reference() -> None:
    result = select_baseline(_rows(300, 6.5, is_home=False))

    moneyline, recent = result.comparisons
    assert moneyline.verdict == "reject"
    assert (recent.incumbent, recent.verdict) == ("reference", "adopt")
    assert {case.projection for case in result.cases_by_arm["recent_form"]} == {6.5}
    assert (result.selected_arm, result.moneyline_scaled, result.recent_form) == ("recent_form", False, True)


def test_rejected_candidates_retain_the_reference() -> None:
    result = select_baseline(_rows(300, 5.0, is_home=False))

    assert [comparison.verdict for comparison in result.comparisons] == ["reject", "reject"]
    assert (result.selected_arm, result.moneyline_scaled, result.recent_form) == ("reference", False, False)


def test_accepted_moneyline_is_kept_when_recent_form_is_rejected() -> None:
    result = select_baseline(_rows(300, 5.4))

    assert [comparison.verdict for comparison in result.comparisons] == ["adopt", "reject"]
    assert result.comparisons[1].incumbent == "moneyline"
    assert (result.selected_arm, result.moneyline_scaled, result.recent_form) == ("moneyline", True, False)


def test_fewer_than_300_pairs_is_insufficient_and_keeps_the_reference() -> None:
    result = select_baseline(_rows(299, 7.02))

    assert [comparison.verdict for comparison in result.comparisons] == ["insufficient", "insufficient"]
    assert result.comparisons[0].diff is not None and result.comparisons[0].diff.n == 299
    assert result.selected_arm == "reference"


def test_missing_moneyline_ties_the_reference_and_is_rejected() -> None:
    result = select_baseline(_rows(300, 6.0, prob=None))

    diff = result.comparisons[0].diff
    assert diff is not None and diff.mean_diff == 0 and result.comparisons[0].verdict == "reject"


def test_every_arm_scores_the_same_eligible_cohort_and_coverage_reconciles() -> None:
    rows = [
        *_rows(3, 6.0),
        _row(10, None),
        _row(11, -1.0),
        _row(12, float("nan")),
        _row(13, 4.0, history=()),
        _row(14, 4.0, history=(1.0, 2.0, 3.0)),
        _row(15, 4.0, history=(None, None, 1.0, 2.0, 3.0, 4.0), prob=None, is_home=None),
        _row(16, 4.0, history=(-2.0, 1.0, 2.0, 3.0, 4.0), prob=1.0),
    ]
    result = select_baseline(rows)

    keys = {arm: {case.key for case in cases} for arm, cases in result.cases_by_arm.items()}
    assert keys["reference"] == keys["moneyline"] == keys["recent_form"]
    assert {player_id for player_id, _, _ in keys["reference"]} == {1, 2, 3, 15, 16}
    week = result.coverage[8]
    assert (week.total, week.missing_actual, week.invalid_actual, week.no_baseline,
            week.thin_baseline, week.scored) == (10, 1, 2, 1, 1, 5)
    assert week.total == (week.missing_actual + week.invalid_actual + week.no_baseline
                          + week.thin_baseline + week.scored)
    assert (week.missing_moneyline, week.unresolved_side) == (2, 1)
    assert (week.missing_history, week.invalid_history) == (2, 1)


def test_history_at_or_after_the_target_week_is_not_counted_as_context() -> None:
    row = _row(1, 3.0, history=(1.0, 2.0, 3.0, 4.0, None), week=5)

    assert select_baseline([row]).coverage[4].missing_history == 0


def test_an_empty_week_reports_zero_coverage() -> None:
    result = select_baseline(_rows(2, 6.0))

    assert [week.week for week in result.coverage] == list(REGULAR_SEASON_WEEKS)
    assert result.coverage[2].total == result.coverage[2].scored == 0
    assert result.coverage[8].scored == 2


def test_an_empty_season_selects_nothing() -> None:
    result = select_baseline([])

    assert result.selected_arm is None
    assert all(comparison.diff is None and comparison.verdict == "insufficient"
               for comparison in result.comparisons)
    assert all(not cases for cases in result.cases_by_arm.values())
    assert sum(week.total for week in result.coverage) == 0


def test_only_ineligible_rows_select_nothing() -> None:
    assert select_baseline([_row(1, 4.0, history=())]).selected_arm is None


def test_duplicate_replay_keys_are_rejected() -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        select_baseline([_row(1, 6.0), _row(1, 6.0)])


def test_rows_from_another_season_are_rejected() -> None:
    with pytest.raises(ValueError, match="2024 only"):
        select_baseline([_row(1, 6.0, season=2025)])


@pytest.mark.parametrize("kwargs", [{"week": 19}, {"position": "QB"}])
def test_rows_outside_the_regular_season_driver_are_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="REG week"):
        select_baseline([_row(1, 6.0, **kwargs)])
