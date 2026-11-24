"""Serving a stale value while one background task rebuilds it (F-44)."""
import asyncio

from app.services.serial_build_cache import SerialBuildCache

TTL = 300.0
FAILURE_TTL = 10.0
MAX_STALE = 1800.0


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class Builder:
    """Returns `v1`, `v2`, ... and can be told to fail or to hold until released."""

    def __init__(self) -> None:
        self.calls = 0
        self.fail = False
        self.release = asyncio.Event()
        self.release.set()

    async def __call__(self) -> str:
        self.calls += 1
        await self.release.wait()
        if self.fail:
            raise RuntimeError("build failed")
        return f"v{self.calls}"


def _cache(clock: Clock, max_stale: float = MAX_STALE) -> SerialBuildCache[str]:
    return SerialBuildCache(TTL, FAILURE_TTL, 5, clock, max_stale_seconds=max_stale)


async def _settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


def test_an_expired_value_is_served_at_once_and_rebuilt_in_the_background() -> None:
    async def scenario() -> None:
        clock, build = Clock(), Builder()
        cache = _cache(clock)
        assert await cache.get("k", build) == "v1"
        clock.now = TTL + 1
        build.release.clear()

        assert await cache.get("k", build) == "v1"
        await _settle()
        assert build.calls == 2
        build.release.set()
        await _settle()
        assert await cache.get("k", build) == "v2"
        assert build.calls == 2

    asyncio.run(scenario())


def test_stale_hits_during_a_rebuild_start_only_one() -> None:
    async def scenario() -> None:
        clock, build = Clock(), Builder()
        cache = _cache(clock)
        await cache.get("k", build)
        clock.now = TTL + 1
        build.release.clear()

        assert await asyncio.gather(*(cache.get("k", build) for _ in range(4))) == ["v1"] * 4
        await _settle()
        assert build.calls == 2
        build.release.set()
        await _settle()

    asyncio.run(scenario())


def test_a_failed_rebuild_keeps_the_stale_value_and_waits_out_the_failure_ttl() -> None:
    async def scenario() -> None:
        clock, build = Clock(), Builder()
        cache = _cache(clock)
        await cache.get("k", build)
        clock.now = TTL + 1
        build.fail = True

        assert await cache.get("k", build) == "v1"
        await _settle()
        assert build.calls == 2
        assert await cache.get("k", build) == "v1"
        await _settle()
        assert build.calls == 2

        clock.now += FAILURE_TTL
        build.fail = False
        assert await cache.get("k", build) == "v1"
        await _settle()
        assert build.calls == 3
        assert await cache.get("k", build) == "v3"

    asyncio.run(scenario())


def test_past_the_stale_window_the_request_builds_inline() -> None:
    async def scenario() -> None:
        clock, build = Clock(), Builder()
        cache = _cache(clock)
        await cache.get("k", build)
        clock.now = TTL + MAX_STALE

        assert await cache.get("k", build) == "v2"

    asyncio.run(scenario())


def test_a_cached_failure_is_never_served_stale() -> None:
    async def scenario() -> None:
        clock, build = Clock(), Builder()
        cache = _cache(clock)
        build.fail = True
        assert await cache.get("k", build) is None
        clock.now = FAILURE_TTL + 1
        build.fail = False

        assert await cache.get("k", build) == "v2"

    asyncio.run(scenario())


def test_without_a_stale_window_an_expired_value_is_rebuilt_inline() -> None:
    async def scenario() -> None:
        clock, build = Clock(), Builder()
        cache = _cache(clock, max_stale=0)
        await cache.get("k", build)
        clock.now = TTL + 1

        assert await cache.get("k", build) == "v2"
        await _settle()
        assert build.calls == 2

    asyncio.run(scenario())
