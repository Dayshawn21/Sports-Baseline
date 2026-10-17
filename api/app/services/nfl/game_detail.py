"""The NFL game page's own data: the game and its pre-kickoff line history.

Slate lines and game notes come from the week endpoints the page already reads,
so this never calls `build_slate`.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_game_notes import line_history_steps
from app.repositories import nfl as nfl_repo
from app.schemas.nfl import NflGameDetailResponse, NflLineHistorySchema, NflLineStepSchema


async def build_game_detail(db: AsyncSession, game_id: int) -> NflGameDetailResponse | None:
    game = await nfl_repo.get_game(db, game_id)
    if game is None:
        return None
    return game_detail(game, await nfl_repo.get_game_line_history(db, game_id))


def game_detail(game: dict, history_rows: list[dict]) -> NflGameDetailResponse:
    return NflGameDetailResponse(
        **game,
        line_history=[
            NflLineHistorySchema(
                market=history.market, book=history.book,
                steps=[NflLineStepSchema(fetched_at=step.fetched_at, line=step.line) for step in history.steps],
            )
            for history in line_history_steps(history_rows)
        ],
    )
