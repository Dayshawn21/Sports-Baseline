from app.backtest.nfl_kicker_projection import (
    FEWER_THAN_FOUR_GAMES, NO_PROJECTION, PREREGISTRATION_COMMIT, kicker_cases, report, without_missed_pats,
)
from app.core.nfl_projection_backtest import ReplayRow
from tests.helpers.nfl_kicker_rows import kicker_line_row, kicker_season


def _replay(player_id: int, games: int, player: float | None, actual: float) -> ReplayRow:
    row = kicker_line_row({2025: kicker_season(games, player)}) | {"player_id": player_id, "game_id": 100 + player_id}
    return ReplayRow(row=row, actual=actual, home_market_prob=None)


ROWS = [_replay(1, 6, 10.0, 12.0), _replay(2, 6, 7.0, 4.0), _replay(3, 2, 9.0, 9.0), _replay(4, 6, None, 8.0)]


def test_kicker_cases_pair_each_rated_kicker_with_the_position_mean_and_count_the_rest() -> None:
    cases = kicker_cases(ROWS, 2025, 5)

    assert [(case.player_id, case.projection) for case in cases.reference] == [(1, 8.5), (2, 8.5)]
    assert [case.player_id for case in cases.candidate] == [1, 2]
    assert cases.candidate[0].projection == round((6 * 10.0 + 10 * 8.5) / 16, 2)
    assert dict(cases.excluded) == {FEWER_THAN_FOUR_GAMES: 1, NO_PROJECTION: 1}


def test_missed_pats_lower_the_actual_by_one_each() -> None:
    cases = kicker_cases(ROWS, 2025, 5).candidate

    assert [case.actual for case in without_missed_pats(cases, {(1, 101): 2})] == [10.0, 4.0]


def test_report_prints_coverage_metrics_and_the_verdict() -> None:
    text = report(2025, 4, kicker_cases(ROWS, 2025, 5), {(1, 101): 1})

    assert f"pre-registered {PREREGISTRATION_COMMIT[:8]}" in text
    assert "  paired cases                                 2" in text
    assert "  candidate nfl-kicker-v1" in text
    # Two cases fall far short of 300.
    assert "Verdict: insufficient" in text
    assert "1 paired games had a missed PAT" in text


def test_report_with_nothing_paired_is_insufficient() -> None:
    assert report(2025, 0, kicker_cases([], 2025, 1), {}).endswith("Verdict: insufficient (no paired cases)")
