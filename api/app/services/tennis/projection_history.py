"""The tennis player page's projection history: frozen props-v3 lines against results (60a)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.projection_history import ProjectionHistoryPoint, history_point, latest_line_per_match
from app.repositories import player_match_stats as box_score_repo
from app.repositories import players as player_repo
from app.repositories import prop_snapshots as prop_snapshot_repo
from app.services.tennis.prop_snapshots import PROJECTION_VERSION


@dataclass(frozen=True)
class ProjectionHistory:
    projection_version: str
    points: list[ProjectionHistoryPoint]
    unsettled: int


async def build_projection_history(db: AsyncSession, player_id: int) -> ProjectionHistory | None:
    if await player_repo.get_player_header(db, player_id) is None:
        return None
    rows = latest_line_per_match(
        await prop_snapshot_repo.get_player_projection_history(db, player_id, PROJECTION_VERSION),
    )
    contexts = await box_score_repo.get_box_score_candidates(
        db, sorted({(player_id, r.match_id) for r in rows}), sources=("tennisabstract", "tennismylife"),
    )
    settled: list[ProjectionHistoryPoint] = []
    unsettled = 0
    for row in rows:
        context = contexts.get((player_id, row.match_id))
        point = history_point(row, context.join() if context else None)
        if point is None:
            continue
        if point.actual is None:
            unsettled += 1
        else:
            settled.append(point)
    settled.sort(key=lambda p: (p.match_date is None, p.match_date, p.stat))
    return ProjectionHistory(PROJECTION_VERSION, settled, unsettled)
