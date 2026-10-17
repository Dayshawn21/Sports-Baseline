"""NBA's side of the shared prop pipeline (20c, 20g3): the period is the regular-season week."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import nba_over_probability_fit as fit
from app.core.nba_projection_backtest import NBA_PROJECTION_MODEL_VERSION
from app.core.nba_resolution import index_nba_candidates, resolve_nba_line
from app.core.nfl_resolution import MATCHED_REASONS, PlayerCandidate
from app.core.prop_predictions import FreezableGame
from app.core.prop_ranking_check import FrozenLine
from app.nba.markets import NBA_PROPS
from app.repositories import nba as nba_repo
from app.repositories import sport_props
from app.services.nba.prop_predictions import week_freezable_games
from app.services.sport_props import LineLinkage, LineResolver, ProviderLine


class NbaPropSource:
    config = NBA_PROPS
    model_version = NBA_PROJECTION_MODEL_VERSION
    over_probability_version = fit.OVER_PROBABILITY_VERSION

    async def load_resolver(self, db: AsyncSession) -> LineResolver:
        """Players, schedule and aliases loaded once, then resolved per line in memory."""
        candidate_index = index_nba_candidates([
            PlayerCandidate(*row) for row in await nba_repo.get_player_candidates(db)
        ])
        game_index = await sport_props.get_game_index(db, NBA_PROPS.code)
        aliases = await sport_props.get_player_aliases(db, NBA_PROPS.code)

        def resolve(line: ProviderLine) -> LineLinkage:
            result, game_id = resolve_nba_line(
                line.player_name, line.team, line.start_time, candidate_index, game_index, aliases,
            )
            return LineLinkage(
                player_id=result.player_id, game_id=game_id,
                reason=str(result.reason), matched=result.reason in MATCHED_REASONS,
            )

        return resolve

    async def current_period(self, db: AsyncSession, now: datetime) -> tuple[int, int] | None:
        return await nba_repo.get_current_week(db, now)

    async def freezable_games(
        self, db: AsyncSession, season: int, period: int, now: datetime,
    ) -> list[FreezableGame]:
        return await week_freezable_games(db, season, period, now)

    async def frozen_lines(self, db: AsyncSession, season: int) -> list[FrozenLine]:
        return await nba_repo.get_frozen_gradeable_lines(db, season)

    async def finished_periods(self, db: AsyncSession, season: int) -> set[int]:
        return await nba_repo.get_finished_weeks(db, season)

    async def frozen_coverage(self, db: AsyncSession, season: int) -> dict[int, tuple[int, int]]:
        return await nba_repo.get_frozen_coverage(db, season)
