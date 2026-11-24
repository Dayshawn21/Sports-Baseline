"""NHL's side of the shared prop pipeline (45c line-only, 56c4 freezing and grading): the period is the regular-season week."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import nhl_over_probability_fit as fit
from app.core.nfl_resolution import MATCHED_REASONS, PlayerCandidate
from app.core.nhl_resolution import index_nhl_candidates, resolve_nhl_line
from app.core.nhl_projection_backtest import NHL_PROJECTION_REFERENCE_VERSION
from app.core.prop_predictions import FreezableGame
from app.core.prop_ranking_check import FrozenLine
from app.nhl.markets import NHL_PROPS
from app.repositories import nhl, sport_props
from app.services.nhl.prop_predictions import week_freezable_games
from app.services.sport_props import LineLinkage, LineResolver, ProviderLine


class NhlPropSource:
    config = NHL_PROPS
    model_version = NHL_PROJECTION_REFERENCE_VERSION
    over_probability_version = fit.OVER_PROBABILITY_VERSION

    async def load_resolver(self, db: AsyncSession) -> LineResolver:
        candidates = index_nhl_candidates([PlayerCandidate(*row) for row in await nhl.get_player_candidates(db)])
        games = await sport_props.get_game_index(db, NHL_PROPS.code)
        aliases = await sport_props.get_player_aliases(db, NHL_PROPS.code)

        def resolve(line: ProviderLine) -> LineLinkage:
            result, game_id = resolve_nhl_line(
                line.player_name, line.team, line.start_time, candidates, games, aliases,
            )
            return LineLinkage(
                player_id=result.player_id, game_id=game_id,
                reason=str(result.reason), matched=result.reason in MATCHED_REASONS,
            )

        return resolve

    async def current_period(self, db: AsyncSession, now: datetime) -> tuple[int, int] | None:
        return await nhl.get_current_week(db, now)

    async def freezable_games(
        self, db: AsyncSession, season: int, period: int, now: datetime,
    ) -> list[FreezableGame]:
        return await week_freezable_games(db, season, period, now)

    async def frozen_lines(self, db: AsyncSession, season: int) -> list[FrozenLine]:
        return await nhl.get_frozen_gradeable_lines(db, season)

    async def finished_periods(self, db: AsyncSession, season: int) -> set[int]:
        return await nhl.get_finished_weeks(db, season)

    async def frozen_coverage(self, db: AsyncSession, season: int) -> dict[int, tuple[int, int]]:
        return await nhl.get_frozen_coverage(db, season)
