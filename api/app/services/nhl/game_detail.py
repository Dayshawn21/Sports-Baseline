from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.line_history import line_history_steps
from app.repositories import nhl
from app.schemas.nhl import NhlGameDetailResponse, NhlSlateGameSchema
from app.services.nhl.slate import assemble_games


def game_detail(game: NhlSlateGameSchema, history_rows: Sequence[Mapping[str, object]]) -> NhlGameDetailResponse:
    return NhlGameDetailResponse.model_validate({
        **game.model_dump(), "line_history": [asdict(history) for history in line_history_steps(history_rows)],
    })


async def build_game_detail(
    db: AsyncSession, game_id: int, *, as_of: datetime | None = None,
) -> NhlGameDetailResponse | None:
    clock = as_of if as_of is not None else datetime.now(timezone.utc)
    game = await nhl.get_game(db, game_id)
    if game is None:
        return None
    (assembled,) = await assemble_games(db, [game], as_of=clock)
    return game_detail(assembled, await nhl.get_game_line_history(db, game_id))
