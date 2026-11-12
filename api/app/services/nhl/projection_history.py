"""The NHL player page's projection history: frozen nhl-reference-v1 lines against results (60b)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nhl_projection_backtest import NHL_PROJECTION_REFERENCE_VERSION
from app.core.nhl_projection_history import NhlProjectionHistoryPoint, nhl_history_point
from app.core.projection_history import latest_line_per_match
from app.repositories import nhl as nhl_repo


@dataclass(frozen=True)
class NhlProjectionHistory:
    projection_version: str
    points: list[NhlProjectionHistoryPoint]
    unsettled: int


async def build_projection_history(db: AsyncSession, player_id: int) -> NhlProjectionHistory | None:
    if await nhl_repo.get_player(db, player_id) is None:
        return None
    lines = latest_line_per_match(await nhl_repo.get_player_projection_history(
        db, player_id, NHL_PROJECTION_REFERENCE_VERSION, nhl_repo.NHL_PROJECTION_HISTORY_FIRST_SEASON,
    ))
    points: list[NhlProjectionHistoryPoint] = []
    unsettled = 0
    for line in lines:
        point = nhl_history_point(line)
        if isinstance(point, NhlProjectionHistoryPoint):
            points.append(point)
        elif point == "unsettled":
            unsettled += 1
    points.sort(key=lambda p: (p.game_date, p.game_id, p.stat))
    return NhlProjectionHistory(NHL_PROJECTION_REFERENCE_VERSION, points, unsettled)
