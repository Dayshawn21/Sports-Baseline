"""A box score joins a match only when exactly one candidate survives every check."""
from datetime import date
from itertools import count

import pytest

from app.core.box_score_join import BoxScoreCandidate, join_box_score, winner_first

TOURNAMENT_START = date(2026, 6, 29)
FINAL_DAY = date(2026, 7, 12)
_ids = count(1)


def _candidate(opponent="Alexander Zverev", score="6-7(7) 7-6(2) 6-3 6-4", result="W",
               match_date=TOURNAMENT_START, aces=12) -> BoxScoreCandidate:
    return BoxScoreCandidate(
        stats_id=next(_ids), match_date=match_date, result=result, opponent_name=opponent,
        score=score, aces=aces, double_faults=2, break_points_converted=3,
    )


FINAL = _candidate()
SEMI = _candidate(opponent="Novak Djokovic", score="6-4 6-4 6-4", aces=9)


def test_two_wins_in_one_event_are_told_apart_by_opponent():
    joined = join_box_score(FINAL_DAY, "W", "Alexander Zverev", "6-7 7-6 6-3 6-4", [FINAL, SEMI])
    assert joined.reason == "joined" and joined.candidate == FINAL


def test_surname_order_does_not_matter():
    candidate = _candidate(opponent="Qinwen Zheng", score="7-5 6-3", result="L", match_date=date(2026, 8, 31))
    joined = join_box_score(date(2026, 9, 7), "L", "Zheng Qinwen", "7-5 6-3", [candidate])
    assert joined.reason == "joined"


def test_li_does_not_match_lin():
    candidate = _candidate(opponent="Zhu Lin", score="6-4 6-4")
    assert join_box_score(TOURNAMENT_START, "W", "Na Li", "6-4 6-4", [candidate]).reason == "no_opponent_match"


def test_a_different_score_is_refused():
    joined = join_box_score(FINAL_DAY, "W", "Alexander Zverev", "6-4 6-4 6-4", [FINAL])
    assert joined.reason == "score_mismatch" and joined.candidate is None


@pytest.mark.parametrize(("match_score", "candidate_score"), [(None, "6-4 6-4"), ("6-4 6-4", None)])
def test_a_missing_score_leaves_the_opponent_to_decide(match_score, candidate_score):
    candidate = _candidate(score=candidate_score)
    assert join_box_score(FINAL_DAY, "W", "Alexander Zverev", match_score, [candidate]).reason == "joined"


def test_two_survivors_are_ambiguous():
    # Round robin: the same opponent twice in one event, and the stored match has no score.
    first, second = _candidate(score="6-4 6-4"), _candidate(score="7-5 6-2")
    joined = join_box_score(FINAL_DAY, "W", "Alexander Zverev", None, [first, second])
    assert joined.reason == "ambiguous" and joined.candidate is None


def test_a_row_outside_the_window_is_ignored():
    stale = _candidate(match_date=date(2026, 6, 1))
    assert join_box_score(FINAL_DAY, "W", "Alexander Zverev", None, [stale]).reason == "no_candidate"


def test_a_row_with_the_other_result_is_ignored():
    assert join_box_score(FINAL_DAY, "L", "Alexander Zverev", None, [FINAL]).reason == "no_candidate"


class TestWinnerFirst:
    def test_a_p1_win_is_already_winner_first(self):
        assert winner_first("6-7 7-6 6-3", p1_won=True) == "6-7 7-6 6-3"

    def test_a_p1_loss_is_flipped(self):
        assert winner_first("5-7 3-6", p1_won=False) == "7-5 6-3"

    def test_no_score_stays_none(self):
        assert winner_first(None, p1_won=False) is None


def _copy(of: BoxScoreCandidate) -> BoxScoreCandidate:
    """The same box score stored again under a new row key after a refetch."""
    return BoxScoreCandidate(
        stats_id=next(_ids), match_date=of.match_date, result=of.result, opponent_name=of.opponent_name,
        score=of.score, aces=of.aces, double_faults=of.double_faults,
        break_points_converted=of.break_points_converted, break_chances_created=of.break_chances_created,
    )


def _placeholder(result="W") -> BoxScoreCandidate:
    return BoxScoreCandidate(
        stats_id=next(_ids), match_date=TOURNAMENT_START, result=result, opponent_name="Alexander Zverev",
        score=None, aces=None, double_faults=None, break_points_converted=None,
    )


def test_identical_copies_join_the_first_stored():
    first = _candidate(score="6-3 6-3")
    joined = join_box_score(FINAL_DAY, "W", "Alexander Zverev", "6-3 6-3", [_copy(first), first][::-1])
    assert joined.reason == "joined" and joined.candidate == first


def test_identical_copies_join_even_without_a_stored_match_score():
    first = _candidate(score="6-3 6-3")
    joined = join_box_score(FINAL_DAY, "W", "Alexander Zverev", None, [first, _copy(first)])
    assert joined.reason == "joined" and joined.candidate == first


def test_a_placeholder_beside_the_real_row_is_dropped():
    real = _candidate(score="6-3 6-3")
    joined = join_box_score(FINAL_DAY, "W", "Alexander Zverev", "6-3 6-3", [_placeholder(), real])
    assert joined.reason == "joined" and joined.candidate == real


def test_several_placeholders_alone_stay_ambiguous():
    joined = join_box_score(FINAL_DAY, "W", "Alexander Zverev", "6-3 6-3", [_placeholder(), _placeholder()])
    assert joined.reason == "ambiguous" and joined.candidate is None


def test_a_single_candidate_joins_as_before_even_when_empty():
    only = _placeholder()
    assert join_box_score(FINAL_DAY, "W", "Alexander Zverev", "6-3 6-3", [only]).candidate == only


def test_two_real_rows_with_different_stats_stay_ambiguous():
    first = _candidate(score="6-3 6-3", aces=12)
    other = _candidate(score="6-3 6-3", aces=4)
    joined = join_box_score(FINAL_DAY, "W", "Alexander Zverev", "6-3 6-3", [first, other])
    assert joined.reason == "ambiguous" and joined.candidate is None


def test_a_suffixed_opponent_now_joins():
    candidate = _candidate(opponent="Martin Damm", score="4-6 6-3 6-4")
    joined = join_box_score(FINAL_DAY, "W", "Martin Damm Jr", "4-6 6-3 6-4", [candidate])
    assert joined.reason == "joined"
