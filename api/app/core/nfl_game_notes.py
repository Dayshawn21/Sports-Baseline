"""Per-game pre-bet notes: injury order, depth moves, line movement, form and rest.

Display only, like `nfl_availability`: nothing here feeds a projection, an edge,
or the slate's ranking. Pure: no DB, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.core.nfl_availability import (
    DEPTH_DEMOTED,
    DEPTH_NEW,
    DEPTH_PROMOTED,
    NflAvailability,
    availability_flags,
)

DepthChange = Literal["promoted", "demoted", "new"]
Result = Literal["W", "L", "T"]

# Moves below the first backup are practice-squad shuffles that flood the list
# without changing who gets snaps.
DEPTH_RANK_CAP = 2
SHORT_WEEK_DAYS = 6
FULL_PRACTICE = "Full Participation in Practice"

_DEPTH_CHANGES: dict[str, DepthChange] = {
    DEPTH_PROMOTED: "promoted", DEPTH_DEMOTED: "demoted", DEPTH_NEW: "new",
}
_STATUS_ORDER = {"Out": 0, "Doubtful": 1, "Questionable": 2}
_POSITION_ORDER = {"QB": 0, "RB": 1, "WR": 2, "TE": 3}


def depth_change(availability: NflAvailability) -> DepthChange | None:
    """The player's depth move this week, or None when it is not worth showing."""
    ranks = [availability.depth_rank, availability.previous_depth_rank]
    if not any(rank is not None and rank <= DEPTH_RANK_CAP for rank in ranks):
        return None
    for flag in availability_flags(availability):
        if flag in _DEPTH_CHANGES:
            return _DEPTH_CHANGES[flag]
    return None


def worth_listing(injury_status: str | None, practice_status: str | None) -> bool:
    """A game status always lists; a practice-only entry lists unless the player practiced fully."""
    if injury_status is not None:
        return True
    return practice_status is not None and practice_status != FULL_PRACTICE


def injury_sort_key(injury_status: str | None, position: str, player_name: str) -> tuple[int, int, str]:
    """Out, Doubtful, Questionable, then practice-report-only; QB, RB, WR, TE within each."""
    return (
        _STATUS_ORDER.get(injury_status or "", len(_STATUS_ORDER)),
        _POSITION_ORDER.get(position, len(_POSITION_ORDER)),
        player_name,
    )


def line_move(open_line: float | None, current_line: float | None) -> float | None:
    if open_line is None or current_line is None:
        return None
    return round(current_line - open_line, 1)


@dataclass(frozen=True)
class LineStep:
    fetched_at: datetime
    line: float


@dataclass(frozen=True)
class LineHistory:
    market: str
    book: str
    steps: list[LineStep]


def line_history_steps(rows: list[dict]) -> list[LineHistory]:
    """One history per market, keeping only the rows where the line changed.

    `rows` hold market, book, line and fetched_at, one book per market, ordered by
    market then fetch time. Odds runs repeat an unchanged line many times; only
    the moves matter for a step chart.
    """
    histories: dict[str, LineHistory] = {}
    for row in rows:
        history = histories.setdefault(row["market"], LineHistory(row["market"], row["book"], []))
        if not history.steps or history.steps[-1].line != row["line"]:
            history.steps.append(LineStep(row["fetched_at"], row["line"]))
    return list(histories.values())


def short_week(rest_days: int | None) -> bool:
    return rest_days is not None and rest_days < SHORT_WEEK_DAYS


def result(points_for: int, points_against: int) -> Result:
    if points_for > points_against:
        return "W"
    if points_for < points_against:
        return "L"
    return "T"
