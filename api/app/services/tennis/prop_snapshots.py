"""Which PrizePicks projections may be frozen as pre-match predictions, and how.

Pure: the caller passes the clock, so the "already started" rule is testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.repositories.props import Prop
from app.schemas.props import PropLine

# Bump on any change to projection, probability or EV logic, so grading never
# pools P(over) produced by different code. Rows written after 48f carry no
# confidence; their probabilities match the earlier v3 rows.
PROJECTION_VERSION = "props-v3"
# The match simulation's shadow rows (48c), stored beside v3 and never pooled with it.
SIM_PROJECTION_VERSION = "props-v4"
SNAPSHOT_ELIGIBILITY_POLICY = "pre-match-v1"

SkipReason = Literal[
    "not_prizepicks", "missing_player", "missing_match", "no_start_time", "no_line", "started", "live",
    "match_finished", "match_link_invalid",
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
    snapshot_at: datetime


def _flagged_live(prop: Prop) -> bool:
    attributes = (prop.raw_json or {}).get("attributes") or {}
    return bool(attributes.get("is_live")) or bool(attributes.get("in_game"))


def skip_reason(prop: Prop, line: PropLine, now: datetime) -> SkipReason | None:
    """Why this projection cannot be stored as a pre-match prediction, or None if it can.

    Known match status and either source's start can veto a later display time.
    """
    if line.source != "prizepicks":
        return "not_prizepicks"
    if line.player_id is None:
        return "missing_player"
    if line.match_id is None:
        return "missing_match"
    if prop.match_link_invalid:
        return "match_link_invalid"
    if prop.match_status in ("completed", "cancelled"):
        return "match_finished"
    if prop.match_status == "live" or _flagged_live(prop):
        return "live"
    if line.start_time is None:
        return "no_start_time"
    if line.line is None:
        return "no_line"
    starts = [start for start in (prop.source_start_time, prop.match_start_time) if start is not None]
    if not starts:
        return "no_start_time"
    if line.start_time <= now or any(start <= now for start in starts):
        return "started"
    return None


def to_snapshot(
    prop: Prop, line: PropLine, snapshot_at: datetime, version: str = PROJECTION_VERSION,
) -> PropProjectionSnapshot:
    """Freeze the page's projection with the source context observed at capture."""
    if snapshot_at.tzinfo is None or snapshot_at.utcoffset() is None:
        raise ValueError("snapshot_at must be timezone-aware")
    if line.player_id is None or line.match_id is None or line.start_time is None or line.line is None:
        raise ValueError(f"prop {line.id} is not snapshot-eligible; check skip_reason first")
    if (prop.id, prop.player_id, prop.match_id) != (line.id, line.player_id, line.match_id):
        raise ValueError("snapshot source and projection must identify the same resolved line")
    reason = skip_reason(prop, line, snapshot_at)
    if reason is not None:
        raise ValueError(f"prop {line.id} is not snapshot-eligible: {reason}")
    inputs = dict(line.projection_inputs)
    inputs["snapshot_eligibility_policy"] = SNAPSHOT_ELIGIBILITY_POLICY
    for key, start in (("source_start_time", prop.source_start_time), ("match_start_time", prop.match_start_time)):
        if start is not None:
            inputs[key] = start.isoformat()
    if prop.match_status is not None:
        inputs["match_status_at_capture"] = prop.match_status
    return PropProjectionSnapshot(
        prop_id=line.id,
        projection_version=version,
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
        projection_inputs=inputs,
        snapshot_at=snapshot_at,
    )
