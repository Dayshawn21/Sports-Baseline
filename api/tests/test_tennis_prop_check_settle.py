from datetime import date

import pytest

from app.backtest.tennis_prop_snapshots import grade
from app.core.box_score_join import BoxScoreCandidate, JoinResult
from app.core.tennis_prop_check import INCOMPLETE_SCORE, settled_outcome
from app.repositories.prop_snapshots import GradedPropSnapshot

STRAIGHT_SETS = "6-4 6-3"
BOX = BoxScoreCandidate(
    stats_id=1, match_date=date(2026, 11, 3), result="W", opponent_name="Opponent", score=STRAIGHT_SETS,
    aces=7, double_faults=2, break_points_converted=3,
)


def test_a_score_stat_settles_over() -> None:
    assert settled_outcome("Total Games", 18.5, STRAIGHT_SETS, 3, True, None) == "over"


def test_a_whole_number_line_on_the_actual_is_a_push() -> None:
    assert settled_outcome("Total Games", 19.0, STRAIGHT_SETS, 3, True, None) == "push"


def test_a_retirement_has_no_result() -> None:
    assert settled_outcome("Total Games", 18.5, "6-4 3-1", 3, True, None) == INCOMPLETE_SCORE


def test_an_ace_line_settles_from_its_box_score() -> None:
    assert settled_outcome("Aces", 6.5, STRAIGHT_SETS, 3, True, JoinResult(BOX, "joined")) == "over"


def test_an_ace_line_without_a_join_carries_the_join_reason() -> None:
    assert settled_outcome("Aces", 6.5, STRAIGHT_SETS, 3, True, None) == "no_candidate"
    assert settled_outcome("Aces", 6.5, STRAIGHT_SETS, 3, True, JoinResult(None, "ambiguous")) == "ambiguous"


def test_a_stat_with_no_settlement_source_is_not_settleable() -> None:
    assert settled_outcome("Fantasy Score", 20.5, STRAIGHT_SETS, 3, True, None) == "not_settleable"


@pytest.mark.parametrize(("stat_type", "line", "player_is_p1"), [
    ("Total Games", 18.5, True), ("Total Games", 19.0, True), ("Total Games Won", 12.5, False),
    ("Aces", 6.5, True), ("Aces", 7.0, True),
])
def test_matches_the_26f_grader(stat_type: str, line: float, player_is_p1: bool) -> None:
    row = GradedPropSnapshot(
        snapshot_id=1, player_id=1, match_id=1, tour="ATP", stat_type=stat_type, odds_type="standard", line=line,
        recommendation="OVER", confidence=None, hit_probability=0.6, player_is_p1=player_is_p1,
        score=STRAIGHT_SETS, best_of=3,
    )
    join = JoinResult(BOX, "joined")
    picks, _ = grade([row], {(1, 1): join})
    expected = {True: "over", False: "under", None: "push"}[picks[0].hit]

    assert settled_outcome(stat_type, line, STRAIGHT_SETS, 3, player_is_p1, join) == expected
