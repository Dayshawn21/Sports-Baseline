"""A shared cache for heavy request-time builds, building one key at a time.

Moved from the NFL slate cache so other sports can use it without importing
NFL code.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from typing import Awaitable, Callable, Generic, Hashable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SerialBuildCache(Generic[T]):
    """Caches each key's result for a while, building at most one key at a time.

    A failure is cached as None for `failure_ttl_seconds`, except a `reraise`
    type, which reaches the caller uncached (an HTTPException that carries its
    own status). Beyond `max_entries` the least recently built key is dropped.

    With `max_stale_seconds`, a value that expired less than that long ago is
    returned at once while one background task rebuilds it, so no request waits
    on a routine refresh. The background fetch outlives the request, so it must
    not use the request's database session.
    """

    def __init__(
        self,
        ttl_seconds: float,
        failure_ttl_seconds: float,
        max_entries: int,
        clock: Callable[[], float] = time.monotonic,
        *,
        reraise: tuple[type[Exception], ...] = (),
        max_stale_seconds: float = 0,
    ) -> None:
        self._ttl = ttl_seconds
        self._failure_ttl = failure_ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._reraise = reraise
        self._max_stale = max_stale_seconds
        self._entries: OrderedDict[Hashable, tuple[float, Optional[T]]] = OrderedDict()
        self._build_lock = asyncio.Lock()
        self._refreshing: dict[Hashable, asyncio.Task[None]] = {}
        self._retry_after: dict[Hashable, float] = {}

    async def get(self, key: Hashable, fetch: Callable[[], Awaitable[T]]) -> Optional[T]:
        cached = self._fresh(key)
        if cached is not None:
            return cached[1]
        stale = self._stale(key)
        if stale is not None:
            self._start_refresh(key, fetch)
            return stale
        async with self._build_lock:
            cached = self._fresh(key)
            if cached is not None:
                return cached[1]
            try:
                value: Optional[T] = await fetch()
                ttl = self._ttl
            except self._reraise:
                raise
            except Exception:
                logger.exception("Build for %s failed; not retrying for %.0fs", key, self._failure_ttl)
                value = None
                ttl = self._failure_ttl
            self._store(key, value, ttl)
            return value

    def _store(self, key: Hashable, value: Optional[T], ttl: float) -> None:
        self._entries[key] = (self._clock() + ttl, value)
        self._entries.move_to_end(key)
        self._retry_after.pop(key, None)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def _fresh(self, key: Hashable) -> Optional[tuple[float, Optional[T]]]:
        entry = self._entries.get(key)
        if entry is None or entry[0] <= self._clock():
            return None
        return entry

    def _stale(self, key: Hashable) -> Optional[T]:
        """An expired value still young enough to serve; a cached failure never is."""
        entry = self._entries.get(key)
        if entry is None or entry[1] is None or self._clock() >= entry[0] + self._max_stale:
            return None
        return entry[1]

    def _start_refresh(self, key: Hashable, fetch: Callable[[], Awaitable[T]]) -> None:
        if key in self._refreshing or self._clock() < self._retry_after.get(key, float("-inf")):
            return
        task = asyncio.create_task(self._refresh(key, fetch))
        self._refreshing[key] = task
        task.add_done_callback(lambda _: self._refreshing.pop(key, None))

    async def _refresh(self, key: Hashable, fetch: Callable[[], Awaitable[T]]) -> None:
        async with self._build_lock:
            if self._fresh(key) is not None:
                return
            try:
                value = await fetch()
            except Exception:
                # The stale value stays served; a failure is never cached over it.
                logger.exception("Background rebuild for %s failed; not retrying for %.0fs", key, self._failure_ttl)
                self._retry_after[key] = self._clock() + self._failure_ttl
                return
            self._store(key, value, self._ttl)
