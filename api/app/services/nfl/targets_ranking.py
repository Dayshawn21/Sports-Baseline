"""Rec Targets' report-only source; ingest and freezing keep their existing sport source."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_targets_projection import NFL_TARGETS_MODEL_VERSION
from app.core.prop_ranking_check import FrozenLine
from app.nfl.markets import NFL_PROPS
from app.repositories import nfl, nfl_targets_ranking


class NflTargetsRankingSource:
    config = NFL_PROPS
    model_version = NFL_TARGETS_MODEL_VERSION
    over_probability_version: None = None

    async def frozen_lines(self, db: AsyncSession, season: int) -> list[FrozenLine]:
        return await nfl_targets_ranking.get_frozen_gradeable_lines(db, season)

    async def finished_periods(self, db: AsyncSession, season: int) -> set[int]:
        return await nfl.get_finished_weeks(db, season)

    async def frozen_coverage(self, db: AsyncSession, season: int) -> dict[int, tuple[int, int]]:
        return await nfl_targets_ranking.get_frozen_coverage(db, season)
