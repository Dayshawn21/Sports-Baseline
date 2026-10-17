"""What a sport supplies to the shared prop pipeline (17c).

The pipeline (PrizePicks ingest, freezing, the forward ranking check) reads a
sport only through `SportPropSource`. Everything sport-specific sits behind it:
roster-based name resolution, the grading period, the projection that fills
frozen rows, and settlement against the sport's own stat tables.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prop_predictions import FreezableGame
from app.core.prop_ranking_check import FrozenLine
from app.core.prop_sports import SportPropConfig


@dataclass(frozen=True)
class LineLinkage:
    player_id: int | None
    game_id: int | None
    # Why the player did or did not link, for the ingest log.
    reason: str
    matched: bool


@dataclass(frozen=True)
class ProviderLine:
    """The provider fields resolution reads, from a fresh feed item or a stored line."""

    player_name: str
    team: str | None
    position: str | None
    start_time: datetime | None


LineResolver = Callable[[ProviderLine], LineLinkage]


class PropLineSource(Protocol):
    """What a sport needs to store and relink provider lines, before it has a projection."""

    @property
    def config(self) -> SportPropConfig: ...

    async def load_resolver(self, db: AsyncSession) -> LineResolver: ...


class SportPropSource(PropLineSource, Protocol):
    """A sport that also freezes and grades its lines; only these join `PROP_SOURCES`."""

    @property
    def model_version(self) -> str: ...

    @property
    def over_probability_version(self) -> str: ...

    async def current_period(self, db: AsyncSession, now: datetime) -> tuple[int, int] | None:
        """(season, period) whose lines are being bet now, or None when no schedule is loaded."""
        ...

    async def freezable_games(
        self, db: AsyncSession, season: int, period: int, now: datetime,
    ) -> list[FreezableGame]: ...

    async def frozen_lines(self, db: AsyncSession, season: int) -> list[FrozenLine]:
        """Each provider prop's latest frozen pre-start row on a completed game, already settled."""
        ...

    async def finished_periods(self, db: AsyncSession, season: int) -> set[int]: ...

    async def frozen_coverage(self, db: AsyncSession, season: int) -> dict[int, tuple[int, int]]:
        """Per period: (gradeable full-game lines, how many have any frozen row)."""
        ...
