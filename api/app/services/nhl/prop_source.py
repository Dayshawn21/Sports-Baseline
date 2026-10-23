"""NHL's line-only adapter for the shared PrizePicks pipeline (45c)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_resolution import MATCHED_REASONS, PlayerCandidate
from app.core.nhl_resolution import index_nhl_candidates, resolve_nhl_line
from app.nhl.markets import NHL_PROPS
from app.repositories import nhl, sport_props
from app.services.sport_props import LineLinkage, LineResolver, ProviderLine


class NhlPropSource:
    config = NHL_PROPS

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
