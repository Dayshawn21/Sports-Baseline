"""Bounded reads for the two players on a tennis match page."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tennis_match_context import WorkloadMatch


@dataclass(frozen=True)
class BookFreshness:
    book: str
    fetched_at: datetime


async def get_workload_matches(db: AsyncSession, player_ids: list[int], on: date) -> dict[int, list[WorkloadMatch]]:
    rows = await db.execute(text("""
        SELECT p.player_id, m.id, m.match_date, m.status, m.score
        FROM unnest(CAST(:ids AS integer[])) AS p(player_id)
        JOIN matches m ON (m.p1_id = p.player_id OR m.p2_id = p.player_id)
        WHERE m.match_date >= :since AND m.match_date < :on
          AND m.status IN ('completed', 'retired')
        ORDER BY p.player_id, m.match_date DESC, m.id
    """), {"ids": player_ids, "since": on - timedelta(days=365), "on": on})
    result: dict[int, list[WorkloadMatch]] = {pid: [] for pid in player_ids}
    for player_id, match_id, day, status, score in rows.fetchall():
        result[player_id].append(WorkloadMatch(match_id, day, status, score))
    return result


async def get_book_freshness(db: AsyncSession, match_id: int, before: datetime | None) -> list[BookFreshness]:
    rows = await db.execute(text("""
        SELECT book, max(fetched_at)
        FROM match_odds
        WHERE match_id = :mid
          AND (CAST(:before AS timestamptz) IS NULL OR fetched_at < :before)
        GROUP BY book ORDER BY book
    """), {"mid": match_id, "before": before})
    return [BookFreshness(*row) for row in rows.fetchall()]
