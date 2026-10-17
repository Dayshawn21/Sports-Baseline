"""Freeze a sport's current-period predictions for every line not yet started (17c, from 27i).

Safe to re-run: a line already stored for its model and P(over) version is skipped.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prop_predictions import PropPredictionRow, freeze_rows
from app.repositories import sport_props
from app.services.sport_props import SportPropSource


@dataclass(frozen=True)
class FreezeRun:
    season: int
    period: int
    rows: list[PropPredictionRow]
    counts: Counter[str]
    # None on a dry run, when nothing is written.
    inserted: int | None


async def freeze_current_period(
    db: AsyncSession, source: SportPropSource, now: datetime, dry_run: bool,
) -> FreezeRun | None:
    """None when the sport has no current period loaded."""
    current = await source.current_period(db, now)
    if current is None:
        return None
    season, period = current
    rows, counts = freeze_rows(await source.freezable_games(db, season, period, now), now)
    inserted = None
    if not dry_run:
        inserted = await sport_props.insert_prop_predictions(db, source.config.code, rows)
        await db.commit()
    return FreezeRun(season, period, rows, counts, inserted)
