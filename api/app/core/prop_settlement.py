"""Settling PrizePicks tennis lines from a final match score or a box score.

Score-derived stats need only the match's own score. Aces, double faults and
break points need the player's box score, joined by app.core.box_score_join.

Pure: no database, no clock.
"""
from __future__ import annotations

import re
from typing import Callable, Literal

from app.core.box_score_join import BoxScoreCandidate, JoinReason, JoinResult

SETTLEABLE_STATS = frozenset({
    "total_games",
    "total_games_won",
    "total_sets",
    "total_tie_breaks",
    "1st_set_total_games",
    "1st_set_total_games_won",
})

LineOutcome = Literal["over", "under", "push"]

_SET_SCORE = re.compile(r"(\d+)-(\d+)")


def parse_sets(score: str | None) -> list[tuple[int, int]]:
    """p1-oriented games per set. Stored scores carry no tie-break points."""
    return [(int(a), int(b)) for a, b in _SET_SCORE.findall(score or "")]


def actual_value(stat: str, sets: list[tuple[int, int]], player_is_p1: bool) -> int | None:
    """The stat's final value for this player, or None when the score cannot decide it.

    A 7-6 set counts as 13 games: PrizePicks scores the tie break as a game.
    """
    if stat not in SETTLEABLE_STATS or not sets:
        return None
    mine = [a if player_is_p1 else b for a, b in sets]
    if stat == "total_games":
        return sum(a + b for a, b in sets)
    if stat == "total_games_won":
        return sum(mine)
    if stat == "total_sets":
        return len(sets)
    if stat == "total_tie_breaks":
        return sum(1 for a, b in sets if {a, b} == {6, 7})
    if stat == "1st_set_total_games":
        return sum(sets[0])
    return mine[0]


# PrizePicks' "Break Points Won" is the player's converted break points.
BOX_SCORE_STATS: dict[str, Callable[[BoxScoreCandidate], int | None]] = {
    "aces": lambda box: box.aces,
    "double_faults": lambda box: box.double_faults,
    "break_points_won": lambda box: box.break_points_converted,
}


def box_score_value(stat: str, box: BoxScoreCandidate) -> int | None:
    """The stat's value from the player's own box score, or None when it has none."""
    read = BOX_SCORE_STATS.get(stat)
    return read(box) if read else None


UnsettledReason = Literal["not_settleable", "missing_count"] | JoinReason


def resolve_actual(
    stat: str, score: str | None, player_is_p1: bool, box: JoinResult | None,
) -> tuple[int | None, UnsettledReason | None]:
    """The stat's final value, from the score or the joined box score, or why there is none.

    `box` is the join for this player and match; None means no join was attempted,
    which for a box-score stat reads as no candidate at all.
    """
    if stat in SETTLEABLE_STATS:
        value = actual_value(stat, parse_sets(score), player_is_p1)
        return (value, None) if value is not None else (None, "not_settleable")
    if stat not in BOX_SCORE_STATS:
        return None, "not_settleable"
    if box is None:
        return None, "no_candidate"
    if box.candidate is None:
        return None, box.reason
    value = box_score_value(stat, box.candidate)
    return (value, None) if value is not None else (None, "missing_count")


def settle(actual: float, line: float) -> LineOutcome:
    if actual > line:
        return "over"
    if actual < line:
        return "under"
    return "push"
