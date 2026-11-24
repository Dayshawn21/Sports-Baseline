"""The served reference projection (56c1) attached to stored NHL line-only offerings."""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nhl_player_values import GOALIE_MARKETS
from app.core.nhl_projection import Availability, GoalieAvailability, NhlLineProjection, project_line
from app.core.nhl_projection_backtest import NhlHistoryRow
from app.nhl.markets import NhlLineOnlyMarket
from app.repositories import nhl
from app.schemas.nhl import NhlProjectionSchema
from app.schemas.nhl_context import NhlGameContextSchema
from app.services.nhl.context import load_contexts
from app.services.nhl.slate import slate_games


@dataclass(frozen=True)
class ProjectionInputs:
    """Everything one game's projections read besides the line: prior games by player and the stored context."""

    history: Mapping[int, Sequence[NhlHistoryRow]]
    context: NhlGameContextSchema | None


NO_INPUTS = ProjectionInputs({}, None)


def availability(
    market: NhlLineOnlyMarket, player_id: int, team: str | None, context: NhlGameContextSchema | None,
) -> Availability:
    if context is None:
        return Availability()
    if market in GOALIE_MARKETS:
        sides = {context.goalies.away.team: context.goalies.away, context.goalies.home.team: context.goalies.home}
        side = sides.get(team) if team is not None else None
        goalie = None if side is None else GoalieAvailability(side.status, context.goalies.freshness, side.player_id)
        return Availability(goalie=goalie)
    injuries = context.injuries
    entry = next((row for row in (*injuries.away, *injuries.home) if row.player_id == player_id), None)
    return Availability(injury_status=None if entry is None else entry.status, injury_freshness=injuries.freshness)


def rounded_probability(probability: float | None) -> float | None:
    return None if probability is None else round(probability, 4)


def core_projection(
    market: NhlLineOnlyMarket, player_id: int, line: float, provider_position: str | None, team: str | None,
    inputs: ProjectionInputs,
) -> NhlLineProjection:
    """The one path the pages serve and the freeze stores, at full precision."""
    prior = inputs.history.get(player_id, [])
    # The stored roster position is what 56b replayed, so it wins over the provider's label.
    position = prior[-1].position if prior else provider_position
    return project_line(prior, market, line, position, player_id, availability(market, player_id, team, inputs.context))


RUNG_FLAGS = frozenset({"integer_line", "no_over_probability"})


def line_projection(
    market: NhlLineOnlyMarket, player_id: int, line: float, provider_position: str | None, team: str | None,
    inputs: ProjectionInputs,
) -> NhlProjectionSchema:
    served = core_projection(market, player_id, line, provider_position, team, inputs)
    return NhlProjectionSchema(
        model_version=served.model_version, value=served.projection, games_in_sample=served.games_in_sample,
        gap=served.gap, p_over=rounded_probability(served.p_over), flags=list(served.flags),
    )


async def load_projection_inputs(
    db: AsyncSession, games: Sequence[Mapping[str, object]],
    lines_by_game: Mapping[int, Sequence[Mapping[str, object]]], as_of: dt.datetime,
) -> tuple[dict[int, list[NhlHistoryRow]], dict[int, NhlGameContextSchema]]:
    """Prior games and stored context for games on one Eastern date, one batched read each.

    A context read that fails leaves the board served without it (goalies read as having no
    report), never a 500 for a page that rendered before. The history read comes first because
    nothing may query after a failed context read: the failed statement can abort the transaction.
    """
    if not games:
        return {}, {}
    dates = {cast(dt.date, game["game_date"]) for game in games}
    if len(dates) != 1:
        raise ValueError(f"projection inputs are read for one game date at a time, got {sorted(dates)}")
    player_ids = sorted({int(str(line["player_id"])) for lines in lines_by_game.values() for line in lines})
    history = await nhl.get_prior_history(db, player_ids, dates.pop())
    try:
        contexts = await load_contexts(db, slate_games(games, [], [], {}), as_of)
    except HTTPException:
        contexts = {}
    return history, contexts
