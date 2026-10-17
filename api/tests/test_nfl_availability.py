import pytest

from app.core.nfl_availability import NflAvailability, availability_flags

WR2_BEFORE = {"previous_depth_team_id": 7, "previous_depth_position": "WR", "previous_depth_rank": 2}


def _flags(**fields: object) -> list[str]:
    return availability_flags(NflAvailability(**fields))


@pytest.mark.parametrize(("status", "flag"), [
    ("Out", "injury_out"), ("Doubtful", "injury_doubtful"), ("Questionable", "injury_questionable"),
])
def test_each_game_status_has_its_own_flag(status: str, flag: str) -> None:
    assert _flags(injury_status=status) == [flag]


def test_no_report_or_an_unknown_status_adds_no_injury_flag() -> None:
    assert _flags() == []
    assert _flags(injury_status="Probable") == []


def test_a_lower_rank_at_the_same_team_and_position_is_a_promotion() -> None:
    assert _flags(depth_team_id=7, depth_position="WR", depth_rank=1, **WR2_BEFORE) == ["depth_promoted"]


def test_a_higher_rank_is_a_demotion_and_the_same_rank_is_no_flag() -> None:
    assert _flags(depth_team_id=7, depth_position="WR", depth_rank=3, **WR2_BEFORE) == ["depth_demoted"]
    assert _flags(depth_team_id=7, depth_position="WR", depth_rank=2, **WR2_BEFORE) == []


@pytest.mark.parametrize("change", [
    {"depth_team_id": 9},
    {"depth_position": "TE"},
])
def test_a_new_team_or_position_is_a_new_role_not_a_rank_move(change: dict[str, object]) -> None:
    fields = {"depth_team_id": 7, "depth_position": "WR", "depth_rank": 1} | change
    assert _flags(**fields, **WR2_BEFORE) == ["depth_new"]


def test_a_first_chart_with_no_earlier_row_is_new() -> None:
    assert _flags(depth_team_id=7, depth_position="WR", depth_rank=4) == ["depth_new"]


def test_no_chart_this_week_says_nothing_about_depth() -> None:
    assert _flags(**WR2_BEFORE) == []


def test_injury_and_depth_flags_combine_injury_first() -> None:
    fields = {"injury_status": "Questionable", "depth_team_id": 7, "depth_position": "WR", "depth_rank": 3}
    assert _flags(**fields, **WR2_BEFORE) == ["injury_questionable", "depth_demoted"]
