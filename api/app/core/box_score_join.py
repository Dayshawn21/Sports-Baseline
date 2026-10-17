"""Deciding which TennisAbstract box score belongs to a stored match.

Box scores are dated by tournament start, so date alone cannot tell a player's
rounds apart. Opponent and score can. A candidate joins only when it is the one
row left after every check: a wrong box score would quietly corrupt a hit rate,
which is worse than a smaller sample.

Pure: no database, no clock.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from app.core.tennis_odds_events import names_player

# From 26b's measured offsets: box-score dates sit up to two weeks before the
# match, and a few days after when a match's local day differs from ours.
WINDOW_BEFORE = timedelta(days=14)
WINDOW_AFTER = timedelta(days=3)

JoinReason = Literal["joined", "no_candidate", "no_opponent_match", "score_mismatch", "ambiguous"]

_SET = re.compile(r"(\d+)-(\d+)")


@dataclass(frozen=True)
class BoxScoreCandidate:
    stats_id: int
    match_date: date
    result: str | None
    opponent_name: str | None
    score: str | None
    aces: int | None
    double_faults: int | None
    break_points_converted: int | None
    break_chances_created: int | None = None
    break_points_faced: int | None = None
    break_points_saved: int | None = None


@dataclass(frozen=True)
class JoinResult:
    candidate: BoxScoreCandidate | None
    reason: JoinReason


def winner_first(p1_score: str | None, p1_won: bool) -> str | None:
    """A p1-first stored score, reoriented to read from the winner's side."""
    if p1_score is None or p1_won:
        return p1_score
    return " ".join(f"{b}-{a}" for a, b in _SET.findall(p1_score))


def _sets(score: str | None) -> list[tuple[int, int]]:
    # findall on "7-6(3)" sees only "7-6": the tie-break points have no hyphen.
    return [(int(a), int(b)) for a, b in _SET.findall(score or "")]


def join_box_score(
    match_date: date,
    result: str,
    opponent_name: str,
    match_score_winner_first: str | None,
    candidates: list[BoxScoreCandidate],
) -> JoinResult:
    in_window = [
        c for c in candidates
        if c.result == result and match_date - WINDOW_BEFORE <= c.match_date <= match_date + WINDOW_AFTER
    ]
    if not in_window:
        return JoinResult(None, "no_candidate")

    same_opponent = [c for c in in_window if c.opponent_name and names_player(opponent_name, c.opponent_name)]
    if not same_opponent:
        return JoinResult(None, "no_opponent_match")

    expected = _sets(match_score_winner_first)
    # The score check applies only when both sides have one; opponent alone decides otherwise.
    agreeing = [c for c in same_opponent if not expected or not c.score or _sets(c.score) == expected]
    if not agreeing:
        return JoinResult(None, "score_mismatch")
    if len(agreeing) == 1:
        return JoinResult(agreeing[0], "joined")
    real = [c for c in agreeing if not _is_empty(c)]
    # A refetch can store the same box score twice under a new row key; identical facts
    # mean one match, so either copy is right. Different facts are never guessed between,
    # and several empty placeholders carry nothing to join.
    if not real or len({_facts(c) for c in real}) > 1:
        return JoinResult(None, "ambiguous")
    return JoinResult(min(real, key=lambda c: c.stats_id), "joined")


def _is_empty(c: BoxScoreCandidate) -> bool:
    """A placeholder stored before the match was played: no score and no stats."""
    return c.score is None and all(
        v is None for v in (c.aces, c.double_faults, c.break_points_converted, c.break_chances_created)
    )


def _facts(c: BoxScoreCandidate) -> tuple:
    return (c.match_date, c.result, c.score, c.aces, c.double_faults, c.break_points_converted, c.break_chances_created)
