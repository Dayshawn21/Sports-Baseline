"""The NHL board cache shares one build per resolved date, serves an expired board while
rebuilding it, and serves the bytes the response model would have sent."""
import asyncio
import datetime as dt

import pytest

from app.repositories import nhl as nhl_repo
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
    ttls = (prop_board_cache.CACHE_TTL_SECONDS, prop_board_cache.FAILURE_TTL_SECONDS, prop_board_cache.MAX_ENTRIES, clock)
    boards: SerialBuildCache[bytes] = SerialBuildCache(*ttls, max_stale_seconds=prop_board_cache.MAX_STALE_SECONDS)
    monkeypatch.setattr(prop_board_cache, "_BOARDS", boards)
    monkeypatch.setattr(prop_board_cache, "_DEFAULT_DATES", SerialBuildCache[dt.date](*ttls))
    return clock


@pytest.fixture
def builds(monkeypatch: pytest.MonkeyPatch) -> list[tuple[dt.date | None, dt.date]]:
    builds: list[tuple[dt.date | None, dt.date]] = []

    async def build_prop_board(session, requested, today, *, as_of):
        assert isinstance(session, FakeSession)
        builds.append((requested, today))
        await asyncio.sleep(0.01)
        if requested == FAILING:
            raise RuntimeError("build failed")
        return _board(requested or today)

    monkeypatch.setattr(prop_board_cache, "build_prop_board", build_prop_board)
    monkeypatch.setattr(prop_board_cache, "SessionLocal", FakeSession)
    return builds


class FakeSession:
    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


@pytest.fixture
def date_reads(monkeypatch: pytest.MonkeyPatch) -> list[None]:
    """Game dates are TODAY and TOMORROW; a read through BROKEN_DB fails."""
    reads: list[None] = []

    async def get_game_dates(db):
        reads.append(None)
        if db is BROKEN_DB:
            raise RuntimeError("read failed")
        return [TODAY, TOMORROW]

    monkeypatch.setattr(nhl_repo, "get_game_dates", get_game_dates)
    return reads


BROKEN_DB = object()


def _get(requested: dt.date | None, today: dt.date = TODAY):
    return prop_board_cache.cached_prop_board_json(None, requested, today)


@pytest.mark.usefixtures("clock", "date_reads")
class TestCachedPropBoard:
    def test_a_burst_for_one_date_builds_once(self, builds):
        async def burst():
            return await asyncio.gather(*(_get(TODAY) for _ in range(10)))

        bodies = asyncio.run(burst())
        assert builds == [(TODAY, TODAY)]
        assert len(set(bodies)) == 1 and bodies[0] == prop_board_cache.board_json(_board(TODAY))

    def test_the_default_and_its_explicit_date_share_one_build(self, builds, date_reads):
        for requested, today in [(TODAY, TODAY), (None, TODAY), (None, TODAY), (TODAY, TODAY), (None, TOMORROW)]:
            asyncio.run(_get(requested, today))
        assert builds == [(TODAY, TODAY), (TOMORROW, TOMORROW)]
        assert len(date_reads) == 2

    def test_an_expired_board_is_served_while_one_rebuild_runs(self, builds, clock):
        async def scenario():
            first = await _get(TODAY)
            clock.now = prop_board_cache.CACHE_TTL_SECONDS - 1
            await _get(TODAY)
            assert len(builds) == 1
            clock.now = prop_board_cache.CACHE_TTL_SECONDS + 1
            assert await asyncio.gather(_get(TODAY), _get(TODAY)) == [first, first]
            await asyncio.sleep(0.05)
            assert len(builds) == 2

        asyncio.run(scenario())

    def test_a_failed_build_returns_none_then_retries(self, builds, clock):
        assert asyncio.run(_get(FAILING)) is None
        assert asyncio.run(_get(FAILING)) is None
        assert len(builds) == 1
        clock.now = prop_board_cache.FAILURE_TTL_SECONDS + 1
        assert asyncio.run(_get(FAILING)) is None
        assert len(builds) == 2

    def test_a_failed_date_read_returns_none_without_building(self, builds):
        assert asyncio.run(prop_board_cache.cached_prop_board_json(BROKEN_DB, None, TODAY)) is None
        assert builds == []


def test_the_cached_body_uses_the_camel_case_aliases() -> None:
    body = prop_board_cache.board_json(_board(TODAY))
    assert b'"previousDate"' in body and b'"overProbabilityVersion"' in body
