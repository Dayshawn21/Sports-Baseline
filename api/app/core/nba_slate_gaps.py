"""The NBA slate digest's rule (38c2): the day's largest reference-projection gaps.

The one place an NBA gap is sorted. Display only and gray, never a pick: the
game page and props keep 20g2's unsorted order. Changing this rule is a ranking
change. Pure: the caller passes the lines and the clock.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

DIGEST_LIMIT = 4
STANDARD = "standard"


@dataclass(frozen=True)
class GapCandidate:
    game_id: int
    start_utc: dt.datetime | None
    status: str
    player_id: int
    player_name: str
    market: str
    odds_type: str | None
    line: float
    projection: float | None
    gap: float | None


@dataclass(frozen=True)
class RankedGap:
    candidate: GapCandidate
    # |gap| / line, so a 2-point gap on a 4.5 line outranks one on a 25.5 line.
    gap_share: float


def _upcoming(candidate: GapCandidate, now: dt.datetime) -> bool:
    return candidate.status == "scheduled" and candidate.start_utc is not None and candidate.start_utc > now


def _qualifies(candidate: GapCandidate, now: dt.datetime) -> bool:
    return (
        candidate.odds_type == STANDARD and candidate.projection is not None and candidate.gap is not None
        and candidate.line > 0 and _upcoming(candidate, now)
    )


def rank_slate_gaps(candidates: Sequence[GapCandidate], now: dt.datetime, limit: int = DIGEST_LIMIT) -> list[RankedGap]:
    """Standard lines with a projection in games not yet tipped, by |gap| / line, one per player."""
    ranked = sorted(
        (RankedGap(candidate, abs(candidate.gap or 0.0) / candidate.line) for candidate in candidates if _qualifies(candidate, now)),
        key=lambda item: (-item.gap_share, item.candidate.player_name, item.candidate.market, item.candidate.game_id),
    )
    seen: set[int] = set()
    digest: list[RankedGap] = []
    for item in ranked:
        if item.candidate.player_id in seen:
            continue
        seen.add(item.candidate.player_id)
        digest.append(item)
        if len(digest) == limit:
            break
    return digest
