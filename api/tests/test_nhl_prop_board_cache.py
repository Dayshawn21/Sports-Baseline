"""The NHL board cache shares one build per date, keys the default date by today, and serves
the bytes the response model would have sent."""
import asyncio
import datetime as dt

import pytest

from app.schemas.nhl import NhlPropBoardResponse
from app.services.nhl import prop_board_cache
from app.services.serial_build_cache import SerialBuildCache

TODAY = dt.date(2026, 10, 24)
TOMORROW = TODAY + dt.timedelta(days=1)
FAILING = dt.date(1999, 1, 1)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _board(date: dt.date) -> NhlPropBoardResponse:
    return NhlPropBoardResponse(date=date, previous_date=None, next_date=None, games=[])


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    cache: SerialBuildCache[bytes] = SerialBuildCache(
        prop_board_cache.CACHE_TTL_SECONDS, prop_board_cache.FAILURE_TTL_SECONDS, prop_board_cache.MAX_ENTRIES, clock,
    )
    monkeypatch.setattr(prop_board_cache, "_BOARDS", cache)
    return clock


@pytest.fixture
def builds(monkeypatch: pytest.MonkeyPatch) -> list[tuple[dt.date | None, dt.date]]:
    builds: list[tuple[dt.date | None, dt.date]] = []

    async def build_prop_board(_db, requested, today, *, as_of):
        builds.append((requested, today))
        await asyncio.sleep(0.01)
        if requested == FAILING:
            raise RuntimeError("build failed")
        return _board(requested or today)

    monkeypatch.setattr(prop_board_cache, "build_prop_board", build_prop_board)
    return builds


def _get(requested: dt.date | None, today: dt.date = TODAY):
    return prop_board_cache.cached_prop_board_json(None, requested, today)


@pytest.mark.usefixtures("clock")
class TestCachedPropBoard:
    def test_a_burst_for_one_date_builds_once(self, builds):
        async def burst():
            return await asyncio.gather(*(_get(TODAY) for _ in range(10)))

        bodies = asyncio.run(burst())
        assert builds == [(TODAY, TODAY)]
        assert len(set(bodies)) == 1 and bodies[0] == prop_board_cache.board_json(_board(TODAY))

    def test_explicit_dates_and_the_default_are_separate_keys(self, builds):
        for requested, today in [(TODAY, TODAY), (None, TODAY), (TODAY, TODAY), (None, TODAY), (None, TOMORROW)]:
            asyncio.run(_get(requested, today))
        assert builds == [(TODAY, TODAY), (None, TODAY), (None, TOMORROW)]

    def test_a_board_is_rebuilt_only_after_it_expires(self, builds, clock):
        asyncio.run(_get(TODAY))
        clock.now = prop_board_cache.CACHE_TTL_SECONDS - 1
        asyncio.run(_get(TODAY))
        assert len(builds) == 1
        clock.now = prop_board_cache.CACHE_TTL_SECONDS + 1
        asyncio.run(_get(TODAY))
        assert len(builds) == 2

    def test_a_failed_build_returns_none_then_retries(self, builds, clock):
        assert asyncio.run(_get(FAILING)) is None
        assert asyncio.run(_get(FAILING)) is None
        assert len(builds) == 1
        clock.now = prop_board_cache.FAILURE_TTL_SECONDS + 1
        assert asyncio.run(_get(FAILING)) is None
        assert len(builds) == 2


def test_the_cached_body_uses_the_camel_case_aliases() -> None:
    body = prop_board_cache.board_json(_board(TODAY))
    assert b'"previousDate"' in body and b'"overProbabilityVersion"' in body
