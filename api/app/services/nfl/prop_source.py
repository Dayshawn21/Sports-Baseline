"""NFL's side of the shared prop pipeline (17c): the period is the week."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_projection import NFL_PROJECTION_MODEL_VERSION
from app.core.nfl_resolution import MATCHED_REASONS, PlayerCandidate, find_game_id, index_candidates, resolve_player
from app.core.prop_predictions import FreezableGame
from app.core.prop_ranking_check import FrozenLine
from app.nfl.markets import NFL_PROPS
from app.repositories import nfl as nfl_repo
from app.repositories import sport_props
from app.services.nfl.prop_predictions import freezable_games
from app.services.nfl.slate import OVER_PROBABILITY_VERSION, build_slate
from app.services.sport_props import LineLinkage, LineResolver, ProviderLine


class NflPropSource:
    config = NFL_PROPS
    model_version = NFL_PROJECTION_MODEL_VERSION
    over_probability_version = OVER_PROBABILITY_VERSION

    async def load_resolver(self, db: AsyncSession) -> LineResolver:
        """Roster, schedule and alias lookups loaded once, then resolved per line in memory."""
        candidate_index = index_candidates([
            PlayerCandidate(*row) for row in await nfl_repo.get_player_candidates(db)
        ])
        game_index = await sport_props.get_game_index(db, NFL_PROPS.code)
        aliases = await sport_props.get_player_aliases(db, NFL_PROPS.code)

        def resolve(line: ProviderLine) -> LineLinkage:
            result = resolve_player(line.player_name, line.team, line.position, candidate_index, aliases)
            return LineLinkage(
                player_id=result.player_id, game_id=find_game_id(line.team, line.start_time, game_index),
                reason=str(result.reason), matched=result.reason in MATCHED_REASONS,
            )

        return resolve

    async def current_period(self, db: AsyncSession, now: datetime) -> tuple[int, int] | None:
        return await nfl_repo.get_current_week(db, now)

    async def freezable_games(
        self, db: AsyncSession, season: int, period: int, now: datetime,
    ) -> list[FreezableGame]:
        return freezable_games(await build_slate(db, season, period, now), now)

    async def frozen_lines(self, db: AsyncSession, season: int) -> list[FrozenLine]:
        return await nfl_repo.get_frozen_gradeable_lines(db, season)

    async def finished_periods(self, db: AsyncSession, season: int) -> set[int]:
        return await nfl_repo.get_finished_weeks(db, season)

    async def frozen_coverage(self, db: AsyncSession, season: int) -> dict[int, tuple[int, int]]:
        return await nfl_repo.get_frozen_coverage(db, season)
