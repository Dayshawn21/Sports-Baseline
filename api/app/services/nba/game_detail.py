"""The NBA game page's data: the slate's view of one game plus its line history (item 20e1)."""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_game_notes import line_history_steps
from app.repositories import nba as nba_repo
from app.schemas.nba import NbaGameDetailResponse, NbaLineHistorySchema, NbaLineStepSchema, NbaSlateGameSchema
from app.services.nba.slate import assemble_games


async def build_game_detail(db: AsyncSession, game_id: int) -> NbaGameDetailResponse | None:
    game = await nba_repo.get_game(db, game_id)
    if game is None:
        return None
    (slate_game,) = await assemble_games(db, [game], cast(dt.date, game["game_date"]))
    return game_detail(slate_game, await nba_repo.get_game_line_history(db, game_id))


def game_detail(game: NbaSlateGameSchema, history_rows: Sequence[Mapping[str, object]]) -> NbaGameDetailResponse:
    return NbaGameDetailResponse(
        **game.model_dump(),
        line_history=[
            NbaLineHistorySchema(
                market=history.market, book=history.book,
                steps=[NbaLineStepSchema(fetched_at=step.fetched_at, line=step.line) for step in history.steps],
            )
            for history in line_history_steps([dict(row) for row in history_rows])
        ],
    )
