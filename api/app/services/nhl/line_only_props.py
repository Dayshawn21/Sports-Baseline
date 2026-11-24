"""Full-game stored offerings without projections or performance analysis."""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nhl_names import nhl_team_code
from app.core.nhl_projection import served_over_probability_version
from app.nhl.markets import NhlLineOnlyMarket
from app.repositories import nhl
from app.schemas.nhl import NhlLineOnlyLineSchema, NhlLineOnlyPropsResponse, NhlMarketProjectionSchema
from app.services.nhl.projections import RUNG_FLAGS, ProjectionInputs, line_projection, load_projection_inputs

_MARKET_ORDER = {market: index for index, market in enumerate(NhlLineOnlyMarket)}


def line_only_props(
    game: Mapping[str, object], lines: Sequence[Mapping[str, object]], inputs: ProjectionInputs,
) -> NhlLineOnlyPropsResponse:
    parsed: list[NhlLineOnlyLineSchema] = []
    projections: dict[tuple[int, NhlLineOnlyMarket], NhlMarketProjectionSchema] = {}
    for line in lines:
        team = nhl_team_code(cast(str | None, line["team"]))
        # Provider team is historical context; never substitute the current roster.
        team = team if team in (game["home_team"], game["away_team"]) else None
        market, player_id = NhlLineOnlyMarket(str(line["market"])), int(str(line["player_id"]))
        projection = line_projection(
            market, player_id, float(str(line["line"])), cast(str | None, line["position"]), team, inputs,
        )
        # The value does not depend on the line, so the first rung gives the market's one projection.
        projections.setdefault((player_id, market), NhlMarketProjectionSchema(
            player_id=player_id, market=market, model_version=projection.model_version, value=projection.value,
            games_in_sample=projection.games_in_sample,
            flags=[flag for flag in projection.flags if flag not in RUNG_FLAGS],
        ))
        parsed.append(NhlLineOnlyLineSchema.model_validate({
            **line, "team": team, "gap": projection.gap, "p_over": projection.p_over,
            "flags": [flag for flag in projection.flags if flag in RUNG_FLAGS],
        }))
    return NhlLineOnlyPropsResponse(
        game_id=int(str(game["game_id"])), over_probability_version=served_over_probability_version(),
        lines=sorted(parsed, key=lambda line: (
            _MARKET_ORDER[line.market], line.player_name, line.player_id,
            line.odds_type, line.line, line.provider_prop_id,
        )),
        projections=sorted(projections.values(), key=lambda item: (_MARKET_ORDER[item.market], item.player_id)),
    )


async def build_line_only_props(
    db: AsyncSession, game_id: int, *, as_of: dt.datetime | None = None,
) -> NhlLineOnlyPropsResponse | None:
    game = await nhl.get_game(db, game_id)
    if game is None:
        return None
    lines = await nhl.get_line_only_lines(db, game_id)
    clock = as_of if as_of is not None else dt.datetime.now(dt.timezone.utc)
    history, contexts = await load_projection_inputs(db, [game], {game_id: lines}, clock)
    return line_only_props(game, lines, ProjectionInputs(history, contexts.get(game_id)))
