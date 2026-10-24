"""Stored NHL context and its pre-puck-drop freshness rule."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from app.core.nhl_context import NhlGoalieObservation, NhlInjuryEntry
from app.core.nhl_context_resolution import EventLink, PlayerLink

Freshness = Literal["fresh", "stale", "unavailable"]


@dataclass(frozen=True)
class StoredInjury:
    entry: NhlInjuryEntry
    player: PlayerLink


@dataclass(frozen=True)
class StoredGoalie:
    observation: NhlGoalieObservation
    player: PlayerLink
    game: EventLink


@dataclass(frozen=True)
class InjurySnapshot:
    fetched_at: datetime
    source_timestamp: datetime | None
    injuries: tuple[StoredInjury, ...]


@dataclass(frozen=True)
class GoalieSnapshot:
    fetched_at: datetime
    source_timestamp: datetime | None
    observations: tuple[StoredGoalie, ...]


def context_freshness(fetched: datetime | None, start: datetime | None, as_of: datetime) -> Freshness:
    if any(value is not None and value.utcoffset() is None for value in (fetched, start, as_of)):
        raise ValueError("NHL context clocks must be timezone-aware")
    if fetched is None or start is None or fetched >= start or fetched > as_of:
        return "unavailable"
    return "stale" if min(start, as_of) - fetched > timedelta(hours=6) else "fresh"
