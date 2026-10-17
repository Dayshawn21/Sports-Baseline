"""The NFL slate cache shares one build per week, never builds two weeks at
once, and stays bounded."""
import asyncio
from datetime import timedelta

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from app.schemas.nfl import NflSlateResponse
from app.services.nfl.slate_cache import SerialBuildCache, slate_json
from tests.test_nfl_prop_predictions import NOW, _game, _line, _slate

TTL = 900
FAILURE_TTL = 10


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class Builds:
    """Records each build and the most builds ever running at once."""

    def __init__(self) -> None:
        self.keys: list[tuple[int, int]] = []
        self.running = 0
        self.peak = 0

    def fetch(self, key: tuple[int, int], fail: bool = False):
        async def build() -> str:
            self.keys.append(key)
            self.running += 1
            self.peak = max(self.peak, self.running)
            await asyncio.sleep(0.01)
            self.running -= 1
            if fail:
                raise RuntimeError("build failed")
            return f"slate {key}"

        return build


@pytest.fixture
def clock() -> Clock:
    return Clock()


def _cache(clock: Clock, max_entries: int = 4) -> SerialBuildCache[str]:
    return SerialBuildCache(TTL, FAILURE_TTL, max_entries, clock)


def test_concurrent_requests_for_one_week_share_one_build(clock):
    cache, builds = _cache(clock), Builds()

    async def burst():
        return await asyncio.gather(*(cache.get((2026, 6), builds.fetch((2026, 6))) for _ in range(5)))

    assert asyncio.run(burst()) == ["slate (2026, 6)"] * 5
    assert builds.keys == [(2026, 6)]


def test_two_weeks_never_build_at_once(clock):
    cache, builds = _cache(clock), Builds()

    async def burst():
        return await asyncio.gather(
            cache.get((2026, 5), builds.fetch((2026, 5))),
            cache.get((2026, 6), builds.fetch((2026, 6))),
        )

    assert asyncio.run(burst()) == ["slate (2026, 5)", "slate (2026, 6)"]
    assert sorted(builds.keys) == [(2026, 5), (2026, 6)]
    assert builds.peak == 1


def test_a_result_is_rebuilt_only_after_it_expires(clock):
    cache, builds = _cache(clock), Builds()
    key = (2026, 6)

    async def get():
        return await cache.get(key, builds.fetch(key))

    asyncio.run(get())
    clock.now = TTL - 1
    asyncio.run(get())
    assert len(builds.keys) == 1
    clock.now = TTL + 1
    asyncio.run(get())
    assert len(builds.keys) == 2


def test_a_failure_is_shared_briefly_then_retried(clock):
    cache, builds = _cache(clock), Builds()
    key = (2026, 6)

    assert asyncio.run(cache.get(key, builds.fetch(key, fail=True))) is None
    assert asyncio.run(cache.get(key, builds.fetch(key))) is None
    assert len(builds.keys) == 1
    clock.now = FAILURE_TTL + 1
    assert asyncio.run(cache.get(key, builds.fetch(key))) == "slate (2026, 6)"


def test_the_oldest_week_is_dropped_past_the_limit(clock):
    cache, builds = _cache(clock, max_entries=2), Builds()

    for week in (4, 5, 6):
        asyncio.run(cache.get((2026, week), builds.fetch((2026, week))))
    asyncio.run(cache.get((2026, 6), builds.fetch((2026, 6))))
    asyncio.run(cache.get((2026, 4), builds.fetch((2026, 4))))
    assert builds.keys == [(2026, 4), (2026, 5), (2026, 6), (2026, 4)]


def test_cached_bytes_match_what_the_response_model_sent():
    slate = _slate(
        _game(1, NOW + timedelta(hours=2), [_line(10), _line(11, p_over=None)]),
        _game(2, None, []),
    )
    app = FastAPI()

    @app.get("/model", response_model=NflSlateResponse)
    def through_model() -> NflSlateResponse:
        return slate

    @app.get("/bytes", response_model=NflSlateResponse)
    def through_bytes() -> Response:
        return Response(content=slate_json(slate), media_type="application/json")

    client = TestClient(app)
    expected, served = client.get("/model"), client.get("/bytes")

    assert served.headers["content-type"] == "application/json"
    assert served.json() == expected.json()
    assert "lineCount" in served.json()
