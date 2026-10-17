"""A short-lived, single-flight cache for live Odds-API.io lookups.

The best-picks overlay used to call the live API on every request. The Tennis page
asks for two dates per load, so each load cost about ten of the plan's hundred
hourly requests, and on 2026-09-25 page loads alone exhausted the quota.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable, Generic, Hashable, Optional, TypeVar

from fastapi import HTTPException

logger = logging.getLogger(__name__)

T = TypeVar("T")


class LiveOddsRateLimited(HTTPException):
    """Odds-API.io answered 429; `reset` is its raw `x-ratelimit-reset` header."""

    def __init__(self, reset: str | None, detail: str) -> None:
        super().__init__(status_code=429, detail=detail)
        self.reset = reset


class TimedSingleFlight(Generic[T]):
    """Caches each key's result, success or failure, for `ttl_seconds`.

    Callers that arrive while a fetch is in flight wait for it rather than
    starting their own. A failure is cached as None for `failure_ttl_seconds`
    (by default the same window), so a rate-limited API is not hit again on
    every request.
    """

    def __init__(
        self,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        failure_ttl_seconds: float | None = None,
    ) -> None:
        self._ttl = ttl_seconds
        self._failure_ttl = ttl_seconds if failure_ttl_seconds is None else failure_ttl_seconds
        self._clock = clock
        self._entries: dict[Hashable, tuple[float, Optional[T]]] = {}
        self._locks: dict[Hashable, asyncio.Lock] = {}

    async def get(self, key: Hashable, fetch: Callable[[], Awaitable[T]]) -> Optional[T]:
        cached = self._fresh(key)
        if cached is not None:
            return cached[1]
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            cached = self._fresh(key)
            if cached is not None:
                return cached[1]
            try:
                value: Optional[T] = await fetch()
                ttl = self._ttl
            except Exception as exc:
                logger.warning("Cached lookup %s failed; not retrying for %.0fs: %s", key, self._failure_ttl, exc)
                value = None
                ttl = self._failure_ttl
            self._entries[key] = (self._clock() + ttl, value)
            return value

    def _fresh(self, key: Hashable) -> Optional[tuple[float, Optional[T]]]:
        entry = self._entries.get(key)
        if entry is None or entry[0] <= self._clock():
            return None
        return entry
