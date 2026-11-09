"""Where the `/nfl/slate` route's body comes from, and a shared cache for it.

One week's build peaked at 381 to 466 MB locally, and a second cold build in
the same process ran the hosted demo out of its 512 MB (37d). So production
serves the copy `nfl_slate_snapshot` stores and never builds; dev builds live
when no copy is stored. Loads run one at a time across every week, and each
result is shared until it expires. The body is the compact wire shape
(`app.core.nfl_slate_wire`), which the web expands.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_slate_wire import compact_slate
from app.core.report_snapshot_source import ReportSource, report_source
from app.repositories import report_snapshots
from app.schemas.nfl import NflSlateResponse
from app.services.nfl.slate import build_slate
from app.services.serial_build_cache import SerialBuildCache

# Short, so a cron's refreshed copy shows within minutes.
CACHE_TTL_SECONDS = 5 * 60
FAILURE_TTL_SECONDS = 10
# A stored week grew to 27 MB by week 9 of 2026, so only the current week and one
# neighbour stay cached; production reads any other week's stored copy on demand.
MAX_ENTRIES = 2

SLATE_REPORT_PREFIX = "nfl_slate_week_"

_SLATES: SerialBuildCache[Optional[bytes]] = SerialBuildCache(
    CACHE_TTL_SECONDS, FAILURE_TTL_SECONDS, MAX_ENTRIES
)


def slate_report(week: int) -> str:
    """`report_snapshots` is keyed by report and season, so the week is in the name."""
    return f"{SLATE_REPORT_PREFIX}{week}"


def slate_json(slate: NflSlateResponse) -> bytes:
    """The camelCase body of `slate`, with each history sample written once."""
    body = compact_slate(slate.model_dump(mode="json", by_alias=True))
    return json.dumps(body, separators=(",", ":"), allow_nan=False).encode()


async def load_slate_json(db: AsyncSession, season: int, week: int, production: bool) -> Optional[bytes]:
    """The stored copy, a live build in dev, or None when production has no copy."""
    stored = await report_snapshots.get_snapshot_text(db, slate_report(week), season)
    source = report_source(stored is not None, production)
    if source is ReportSource.SNAPSHOT and stored is not None:
        return stored.encode()
    if source is ReportSource.UNAVAILABLE:
        return None
    return slate_json(await build_slate(db, season, week, datetime.now(UTC)))


async def cached_slate_json(db: AsyncSession, season: int, week: int, production: bool) -> Optional[bytes]:
    """The week's slate as JSON, or None when it is unavailable or failed to load.

    Only the serialized body is kept: the response object held about 90 MB more,
    and re-serializing its 10.7 MB per request pushed concurrent visitors toward
    the demo's 512 MB (37d, 2026-10-16).
    """
    return await _SLATES.get((season, week), lambda: load_slate_json(db, season, week, production))
