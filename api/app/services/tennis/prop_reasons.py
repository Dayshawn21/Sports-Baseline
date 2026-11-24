"""Why over / why under for one PrizePicks tennis line (63).

The router enriches the line exactly as the board does and hands both forms of
it here, so the panel's projection, sample and flags are the row's own.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tennis_prop_reasons import (
    SPLIT_WINDOW,
    WINDOW,
    LogMatch,
    PropReasons,
    ReasonInput,
    RecentValue,
    build_reasons,
    recent_values,
)
from app.repositories.props import Prop
from app.schemas.props import PropLine
from app.services.tennis.player_detail import MatchLogEntry, match_log


@dataclass(frozen=True)
class PropReasonsResult:
    reasons: PropReasons
    chart: list[RecentValue]
    """Oldest first, at most `WINDOW`: the order the bar chart draws."""


def log_match(entry: MatchLogEntry) -> LogMatch:
    row = entry.match
    return LogMatch(row.match_id, row.match_date, row.opponent_name, row.surface, row.best_of, row.score, entry.box)


def line_cutoff(prop: Prop) -> date:
    """The UTC day the line was for: matches from that day on were not known when it was posted.

    UTC can run a day ahead of a tournament's local date, which costs at most
    the day-before match; using a later day would let a result leak in.
    """
    moment = prop.start_time or prop.fetched_at
    return moment.astimezone(UTC).date() if moment.tzinfo else moment.date()


def reason_input(prop: Prop, line: PropLine, recent: Sequence[RecentValue]) -> ReasonInput:
    return ReasonInput(
        stat_type=prop.stat_type,
        line=float(prop.line),
        recent=recent,
        player_linked=prop.player_id is not None,
        projection=line.stat_avg if line.projection_status == "ok" else None,
        rolling_matches=line.matches_count,
        opponent_figure=line.opponent_stat_avg,
        opponent_matches=line.opponent_matches_count,
        surface=prop.surface,
        best_of=prop.best_of,
        stats_stale=bool(line.stats_stale),
    )


async def build_prop_reasons(db: AsyncSession, prop: Prop, line: PropLine) -> PropReasonsResult:
    recent: list[RecentValue] = []
    if prop.player_id is not None:
        log = await match_log(db, prop.player_id, SPLIT_WINDOW)
        matches = [log_match(e) for e in log]
        recent = recent_values(prop.stat_type, matches, exclude_match_id=prop.match_id, before=line_cutoff(prop))
    reasons = build_reasons(reason_input(prop, line, recent))
    return PropReasonsResult(reasons, list(reversed(recent[:WINDOW])))
