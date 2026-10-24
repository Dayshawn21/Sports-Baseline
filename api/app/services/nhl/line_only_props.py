"""Full-game stored offerings without projections or performance analysis."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nhl_names import nhl_team_code
from app.nhl.markets import NhlLineOnlyMarket
from app.repositories import nhl
from app.schemas.nhl import NhlLineOnlyLineSchema, NhlLineOnlyPropsResponse

_MARKET_ORDER = {market: index for index, market in enumerate(NhlLineOnlyMarket)}


def line_only_props(
    game: Mapping[str, object], lines: Sequence[Mapping[str, object]],
) -> NhlLineOnlyPropsResponse:
    parsed: list[NhlLineOnlyLineSchema] = []
    for line in lines:
        team = nhl_team_code(cast(str | None, line["team"]))
        # Provider team is historical context; never substitute the current roster.
        team = team if team in (game["home_team"], game["away_team"]) else None
        parsed.append(NhlLineOnlyLineSchema.model_validate({**line, "team": team}))
    return NhlLineOnlyPropsResponse(
        game_id=int(str(game["game_id"])),
        lines=sorted(parsed, key=lambda line: (
            _MARKET_ORDER[line.market], line.player_name, line.player_id,
            line.odds_type, line.line, line.provider_prop_id,
        )),
    )


async def build_line_only_props(db: AsyncSession, game_id: int) -> NhlLineOnlyPropsResponse | None:
    game = await nhl.get_game(db, game_id)
    if game is None:
        return None
    return line_only_props(game, await nhl.get_line_only_lines(db, game_id))
