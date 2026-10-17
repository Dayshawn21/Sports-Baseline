"""Every settled line depends on reading the score from the right player's side."""
from dataclasses import replace
from datetime import date

import pytest

from app.core.box_score_join import BoxScoreCandidate, JoinResult
from app.core.prop_settlement import (
    SETTLEABLE_STATS,
    actual_value,
    box_score_value,
    parse_sets,
    resolve_actual,
    settle,
)

STRAIGHT = parse_sets("6-4 6-3")
THREE_WITH_TIE_BREAK = parse_sets("6-7 7-5 6-2")
BEST_OF_FIVE = parse_sets("6-7 7-6 6-1 6-4")


class TestParseSets:
    def test_reads_sets_p1_first(self):
        assert THREE_WITH_TIE_BREAK == [(6, 7), (7, 5), (6, 2)]

    @pytest.mark.parametrize("score", [None, ""])
    def test_empty_score_has_no_sets(self, score):
        assert parse_sets(score) == []


class TestActualValue:
    @pytest.mark.parametrize(
        ("stat", "straight", "three_sets"),
        [
            ("total_games", 19, 33),
            ("total_games_won", 12, 19),
            ("total_sets", 2, 3),
            ("total_tie_breaks", 0, 1),
            ("1st_set_total_games", 10, 13),
            ("1st_set_total_games_won", 6, 6),
        ],
    )
    def test_p1_side(self, stat, straight, three_sets):
        assert actual_value(stat, STRAIGHT, player_is_p1=True) == straight
        assert actual_value(stat, THREE_WITH_TIE_BREAK, player_is_p1=True) == three_sets

    def test_games_won_reads_the_p2_side(self):
        assert actual_value("total_games_won", STRAIGHT, player_is_p1=False) == 7
        assert actual_value("total_games_won", THREE_WITH_TIE_BREAK, player_is_p1=False) == 14

    def test_first_set_games_won_reads_the_p2_side(self):
        assert actual_value("1st_set_total_games_won", STRAIGHT, player_is_p1=False) == 4
        assert actual_value("1st_set_total_games_won", THREE_WITH_TIE_BREAK, player_is_p1=False) == 7

    def test_match_totals_do_not_depend_on_side(self):
        for stat in ("total_games", "total_sets", "total_tie_breaks", "1st_set_total_games"):
            assert actual_value(stat, THREE_WITH_TIE_BREAK, True) == actual_value(stat, THREE_WITH_TIE_BREAK, False)

    def test_best_of_five(self):
        assert actual_value("total_games", BEST_OF_FIVE, True) == 13 + 13 + 7 + 10
        assert actual_value("total_sets", BEST_OF_FIVE, True) == 4
        assert actual_value("total_tie_breaks", BEST_OF_FIVE, True) == 2

    def test_box_score_stats_are_not_settleable(self):
        assert "aces" not in SETTLEABLE_STATS
        assert actual_value("aces", STRAIGHT, True) is None

    def test_no_sets_settles_nothing(self):
        assert actual_value("total_games", [], True) is None


class TestBoxScoreValue:
    BOX = BoxScoreCandidate(
        stats_id=1, match_date=date(2026, 6, 29), result="W", opponent_name="Alexander Zverev",
        score="6-4 6-4", aces=14, double_faults=2, break_points_converted=3,
    )

    @pytest.mark.parametrize(
        ("stat", "expected"), [("aces", 14), ("double_faults", 2), ("break_points_won", 3)],
    )
    def test_each_box_score_stat(self, stat, expected):
        assert box_score_value(stat, self.BOX) == expected

    def test_a_score_derived_stat_is_not_read_from_the_box_score(self):
        assert box_score_value("total_games", self.BOX) is None

    def test_a_missing_count_stays_none(self):
        assert box_score_value("aces", replace(self.BOX, aces=None)) is None


class TestSettle:
    def test_a_whole_line_can_push(self):
        assert settle(22, 22.0) == "push"

    @pytest.mark.parametrize(("actual", "expected"), [(23, "over"), (22, "under")])
    def test_a_half_line_never_pushes(self, actual, expected):
        assert settle(actual, 22.5) == expected


class TestResolveActual:
    BOX = TestBoxScoreValue.BOX

    def test_a_score_stat_ignores_the_join(self):
        assert resolve_actual("total_games", "6-4 6-3", True, None) == (19, None)

    def test_a_joined_box_score_stat(self):
        assert resolve_actual("aces", "6-4 6-3", True, JoinResult(self.BOX, "joined")) == (14, None)

    def test_an_unjoined_box_score_stat_carries_the_join_reason(self):
        assert resolve_actual("aces", "6-4 6-3", True, JoinResult(None, "score_mismatch")) == (None, "score_mismatch")

    def test_no_join_attempted_reads_as_no_candidate(self):
        assert resolve_actual("double_faults", "6-4 6-3", True, None) == (None, "no_candidate")

    def test_a_joined_box_score_missing_the_count(self):
        box = JoinResult(replace(self.BOX, aces=None), "joined")
        assert resolve_actual("aces", "6-4 6-3", True, box) == (None, "missing_count")

    def test_a_stat_with_no_source(self):
        assert resolve_actual("fantasy_score", "6-4 6-3", True, None) == (None, "not_settleable")
