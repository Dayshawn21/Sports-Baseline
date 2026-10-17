"""Where the `/nfl/slate` route's body comes from, and a shared cache for it.

One week's build peaked at 381 to 466 MB locally, and a second cold build in
the same process ran the hosted demo out of its 512 MB (37d). So production
serves the copy `nfl_slate_snapshot` stores and never builds; dev builds live
when no copy is stored. Loads run one at a time across every week, and each
result is shared until it expires.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Awaitable, Callable, Generic, Hashable, Optional, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.report_snapshot_source import ReportSource, report_source
from app.repositories import report_snapshots
from app.schemas.nfl import NflSlateResponse
from app.services.nfl.slate import build_slate

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Short, so a cron's refreshed copy shows within minutes.
CACHE_TTL_SECONDS = 5 * 60
FAILURE_TTL_SECONDS = 10
# The current week and its neighbours; older weeks rebuild on demand.
MAX_ENTRIES = 4


class SerialBuildCache(Generic[T]):
    """Caches each key's result for a while, building at most one key at a time.

    A failure is cached as None for `failure_ttl_seconds`. Beyond `max_entries`
    the least recently built key is dropped.
    """

    def __init__(
        self,
        ttl_seconds: float,
        failure_ttl_seconds: float,
        max_entries: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._failure_ttl = failure_ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[Hashable, tuple[float, Optional[T]]] = OrderedDict()
        self._build_lock = asyncio.Lock()

    async def get(self, key: Hashable, fetch: Callable[[], Awaitable[T]]) -> Optional[T]:
        cached = self._fresh(key)
        if cached is not None:
            return cached[1]
        async with self._build_lock:
            cached = self._fresh(key)
            if cached is not None:
                return cached[1]
            try:
                value: Optional[T] = await fetch()
                ttl = self._ttl
            except Exception:
                logger.exception("Build for %s failed; not retrying for %.0fs", key, self._failure_ttl)
                value = None
                ttl = self._failure_ttl
            self._entries[key] = (self._clock() + ttl, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
            return value

    def _fresh(self, key: Hashable) -> Optional[tuple[float, Optional[T]]]:
        entry = self._entries.get(key)
        if entry is None or entry[0] <= self._clock():
            return None
        return entry


SLATE_REPORT_PREFIX = "nfl_slate_week_"

_SLATES: SerialBuildCache[Optional[bytes]] = SerialBuildCache(
    CACHE_TTL_SECONDS, FAILURE_TTL_SECONDS, MAX_ENTRIES
)


def slate_report(week: int) -> str:
    """`report_snapshots` is keyed by report and season, so the week is in the name."""
    return f"{SLATE_REPORT_PREFIX}{week}"


def slate_json(slate: NflSlateResponse) -> bytes:
    """The body FastAPI would send for `slate` under its camelCase response model."""
    return slate.model_dump_json(by_alias=True).encode()


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
