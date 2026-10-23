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
