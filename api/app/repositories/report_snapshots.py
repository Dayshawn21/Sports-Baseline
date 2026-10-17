"""Precomputed report payloads, one per report and season (37d)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

JsonObject = dict[str, object]


@dataclass(frozen=True)
class StoredSnapshot:
    payload: JsonObject
    computed_at: datetime


async def get_snapshot(db: AsyncSession, report: str, season: int) -> StoredSnapshot | None:
    row = (await db.execute(text("""
        SELECT payload, computed_at FROM report_snapshots
        WHERE report = :report AND season = :season
    """), {"report": report, "season": season})).first()
    if row is None:
        return None
    return StoredSnapshot(payload=row.payload, computed_at=row.computed_at)


async def get_snapshot_text(db: AsyncSession, report: str, season: int) -> str | None:
    """The stored payload as JSON text, for a caller that forwards it unparsed."""
    return (await db.execute(text("""
        SELECT payload::text FROM report_snapshots
        WHERE report = :report AND season = :season
    """), {"report": report, "season": season})).scalar_one_or_none()


async def upsert_snapshot(
    db: AsyncSession, report: str, season: int, payload: JsonObject, computed_at: datetime,
) -> None:
    await upsert_snapshot_text(db, report, season, json.dumps(payload), computed_at)


async def upsert_snapshot_text(
    db: AsyncSession, report: str, season: int, payload_json: str, computed_at: datetime,
) -> None:
    await db.execute(text("""
        INSERT INTO report_snapshots (report, season, payload, computed_at)
        VALUES (:report, :season, CAST(:payload AS jsonb), :computed_at)
        ON CONFLICT (report, season)
        DO UPDATE SET payload = EXCLUDED.payload, computed_at = EXCLUDED.computed_at
    """), {
        "report": report, "season": season,
        "payload": payload_json, "computed_at": computed_at,
    })
