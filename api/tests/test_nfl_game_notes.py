import pytest

from app.core.nfl_availability import NflAvailability
from datetime import UTC, datetime

from app.core.nfl_game_notes import (
    LineStep, depth_change, injury_sort_key, line_history_steps, line_move, result, short_week, worth_listing,
)

WR_ON_7 = {"depth_team_id": 7, "depth_position": "WR", "previous_depth_team_id": 7, "previous_depth_position": "WR"}


def _change(**fields: object) -> str | None:
    return depth_change(NflAvailability(**fields))


def test_starter_moves_are_promotions_and_demotions() -> None:
    assert _change(**WR_ON_7, depth_rank=1, previous_depth_rank=2) == "promoted"
    assert _change(**WR_ON_7, depth_rank=3, previous_depth_rank=2) == "demoted"


def test_an_unchanged_rank_is_no_change() -> None:
    assert _change(**WR_ON_7, depth_rank=2, previous_depth_rank=2) is None


def test_moves_entirely_below_the_first_backup_are_hidden() -> None:
    assert _change(**WR_ON_7, depth_rank=4, previous_depth_rank=5) is None
    assert _change(depth_team_id=7, depth_position="WR", depth_rank=5) is None


def test_a_first_listing_or_new_team_near_the_top_is_new() -> None:
    assert _change(depth_team_id=7, depth_position="RB", depth_rank=1) == "new"
    assert _change(**(WR_ON_7 | {"depth_team_id": 9}), depth_rank=2, previous_depth_rank=1) == "new"


def test_injury_status_alone_is_not_a_depth_change() -> None:
    assert _change(injury_status="Out") is None


def test_injuries_sort_by_severity_then_position_then_name() -> None:
    rows = [
        ("Questionable", "QB", "A"), (None, "QB", "B"), ("Out", "TE", "C"),
        ("Out", "QB", "D"), ("Doubtful", "WR", "E"), ("Out", "QB", "Aa"),
    ]
    ordered = sorted(rows, key=lambda row: injury_sort_key(*row))
    assert [name for _, _, name in ordered] == ["Aa", "D", "C", "E", "A", "B"]


@pytest.mark.parametrize(("open_line", "current", "expected"), [
    (-4.5, -5.5, -1.0), (42.5, 44.0, 1.5), (42.5, 42.5, 0.0), (None, 44.0, None), (42.5, None, None),
])
def test_line_move_is_current_minus_open(open_line: float | None, current: float | None, expected: float | None) -> None:
    assert line_move(open_line, current) == expected


@pytest.mark.parametrize(("rest", "expected"), [(4, True), (5, True), (6, False), (10, False), (None, False)])
def test_short_week_is_under_six_days_and_unknown_is_not_short(rest: int | None, expected: bool) -> None:
    assert short_week(rest) is expected


def test_result_is_from_the_teams_side() -> None:
    assert (result(24, 17), result(10, 20), result(20, 20)) == ("W", "L", "T")


@pytest.mark.parametrize(("status", "practice", "expected"), [
    ("Out", "Full Participation in Practice", True),
    ("Questionable", None, True),
    (None, "Limited Participation in Practice", True),
    (None, "Did Not Participate In Practice", True),
    (None, "Full Participation in Practice", False),
    (None, None, False),
])
def test_practice_only_entries_list_unless_the_player_practiced_fully(
    status: str | None, practice: str | None, expected: bool,
) -> None:
    assert worth_listing(status, practice) is expected


def _odds(market: str, hour: int, line: float, book: str = "draftkings") -> dict:
    return {"market": market, "book": book, "line": line, "fetched_at": datetime(2026, 9, 22, hour, tzinfo=UTC)}


def test_line_history_drops_unchanged_repeats() -> None:
    [spread] = line_history_steps([_odds("spread", 1, -1.5), _odds("spread", 2, -1.5), _odds("spread", 3, -2.5), _odds("spread", 4, -2.5)])
    assert spread.market == "spread" and spread.book == "draftkings"
    assert [step.line for step in spread.steps] == [-1.5, -2.5]
    assert spread.steps[1].fetched_at.hour == 3


def test_a_line_that_moves_back_keeps_every_move() -> None:
    [total] = line_history_steps([_odds("total", 1, 47.0), _odds("total", 2, 48.0), _odds("total", 3, 47.0)])
    assert [step.line for step in total.steps] == [47.0, 48.0, 47.0]


def test_a_single_row_is_one_step() -> None:
    [total] = line_history_steps([_odds("total", 5, 44.5, book="fanduel")])
    assert total.book == "fanduel"
    assert total.steps == [LineStep(datetime(2026, 9, 22, 5, tzinfo=UTC), 44.5)]


def test_markets_get_separate_histories_in_row_order() -> None:
    histories = line_history_steps([_odds("spread", 1, 3.0), _odds("spread", 2, 3.5), _odds("total", 1, 41.0)])
    assert [(item.market, len(item.steps)) for item in histories] == [("spread", 2), ("total", 1)]


def test_no_rows_is_no_history() -> None:
    assert line_history_steps([]) == []
