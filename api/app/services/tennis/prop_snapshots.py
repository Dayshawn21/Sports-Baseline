"""Which PrizePicks projections may be frozen as pre-match predictions, and how.

Pure: the caller passes the clock, so the "already started" rule is testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.repositories.props import Prop
from app.schemas.props import PropLine

# Bump on any change to projection, probability, EV or tier logic, so grading
# never pools tiers produced by different code.
PROJECTION_VERSION = "props-v2"

SkipReason = Literal[
    "not_prizepicks", "missing_player", "missing_match", "no_start_time", "no_line", "started", "live",
]


@dataclass(frozen=True)
class PropProjectionSnapshot:
    prop_id: int
    projection_version: str
    player_id: int
    match_id: int
    stat_type: str
    odds_type: str | None
    line: float
    start_time: datetime
    recommendation: str | None
    confidence: str | None
    hit_probability: float | None
    p_over: float | None
    p_under: float | None
    p_push: float | None
    stat_avg: float | None
    ev_pct: float | None
    break_even_pct: float | None
    matches_count: int | None
    market_total_games: float | None
    projection_status: str
    data_quality_flags: list[str]
    projection_inputs: dict[str, float | str]


def _flagged_live(prop: Prop) -> bool:
    attributes = (prop.raw_json or {}).get("attributes") or {}
    return bool(attributes.get("is_live")) or bool(attributes.get("in_game"))


def skip_reason(prop: Prop, line: PropLine, now: datetime) -> SkipReason | None:
    """Why this projection cannot be stored as a pre-match prediction, or None if it can.

    The live flag is checked even when the start is in the future: stored start
    times can run hours late, and PrizePicks knows when a match is under way.
    """
    if line.source != "prizepicks":
        return "not_prizepicks"
    if line.player_id is None:
        return "missing_player"
    if line.match_id is None:
        return "missing_match"
    if line.start_time is None:
        return "no_start_time"
    if line.line is None:
        return "no_line"
    if line.start_time <= now:
        return "started"
    if _flagged_live(prop):
        return "live"
    return None


def to_snapshot(line: PropLine) -> PropProjectionSnapshot:
    """The page's projection for an eligible line; call only when skip_reason is None."""
    if line.player_id is None or line.match_id is None or line.start_time is None or line.line is None:
        raise ValueError(f"prop {line.id} is not snapshot-eligible; check skip_reason first")
    return PropProjectionSnapshot(
        prop_id=line.id,
        projection_version=PROJECTION_VERSION,
        player_id=line.player_id,
        match_id=line.match_id,
        stat_type=line.stat_type,
        odds_type=line.odds_type,
        line=float(line.line),
        start_time=line.start_time,
        recommendation=line.recommendation,
        confidence=line.confidence,
        hit_probability=line.hit_probability,
        p_over=line.p_over,
        p_under=line.p_under,
        p_push=line.p_push,
        stat_avg=line.stat_avg,
        ev_pct=line.ev_pct,
        break_even_pct=line.break_even_pct,
        matches_count=line.matches_count,
        market_total_games=line.market_total_games,
        projection_status=line.projection_status,
        data_quality_flags=list(line.data_quality_flags),
        projection_inputs=dict(line.projection_inputs),
    )
