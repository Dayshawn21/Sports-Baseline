"""Freeze what the NHL pages serve for each line before puck drop (item 56c4)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nhl_prop_predictions import NhlFreezeLine, prediction_row
from app.core.prop_predictions import FreezableGame, PropPredictionRow
from app.nhl.markets import NhlLineOnlyMarket
from app.repositories import nhl
from app.schemas.nhl_context import NhlGameContextSchema
from app.services.nhl.context import load_contexts
from app.services.nhl.projections import ProjectionInputs, core_projection
from app.services.nhl.slate import slate_games


async def _week_contexts(db: AsyncSession, season: int, week: int, now: datetime) -> dict[int, NhlGameContextSchema]:
    """Stored context as of `now`; an unreadable store freezes goalie lines as unreported, never a crash."""
    games = await nhl.get_week_games(db, season, week)
    try:
        return await load_contexts(db, slate_games(games, [], [], {}), now)
    except HTTPException:
        return {}


async def week_freezable_games(db: AsyncSession, season: int, week: int, now: datetime) -> list[FreezableGame]:
    """The week's lines, each projected from the player's games before its own game date."""
    lines = await nhl.get_week_freeze_lines(db, season, week)
    players_by_date: dict[date, set[int]] = defaultdict(set)
    for line in lines:
        players_by_date[line.game_date].add(line.player_id)
    # The history read comes before the context read: a failed context statement can abort the transaction.
    history_by_date = {
        game_date: await nhl.get_prior_history(db, sorted(player_ids), game_date)
        for game_date, player_ids in players_by_date.items()
    }
    contexts = await _week_contexts(db, season, week, now)
    by_game: dict[int, list[NhlFreezeLine]] = defaultdict(list)
    for line in lines:
        by_game[line.game_id].append(line)
    return [
        FreezableGame(game_lines[0].start_utc, [
            _freeze(line, ProjectionInputs(history_by_date[line.game_date], contexts.get(line.game_id)), now)
            for line in game_lines
        ])
        for game_lines in by_game.values()
    ]


def _freeze(line: NhlFreezeLine, inputs: ProjectionInputs, now: datetime) -> PropPredictionRow:
    projection = core_projection(NhlLineOnlyMarket(line.market), line.player_id, line.line, line.position, line.team, inputs)
    return prediction_row(line, projection, now)
