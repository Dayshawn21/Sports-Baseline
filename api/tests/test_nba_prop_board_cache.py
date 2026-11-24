"""The NBA board cache shares one build per resolved date, serves an expired
board while rebuilding it, and serves the bytes the response model would have sent."""
import asyncio
import datetime as dt

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from app.repositories import nba as nba_repo
from app.schemas.nba import NbaPropBoardResponse
from app.services.nba import prop_board_cache
from app.services.nba.prop_board import prop_board_response
from app.services.serial_build_cache import SerialBuildCache
from tests.helpers.nba_prop_board import DATE, NEXT, PREVIOUS, _box, _game, _line, _prior

TODAY = dt.date(2026, 10, 23)
TOMORROW = TODAY + dt.timedelta(days=1)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _board(date: dt.date) -> NbaPropBoardResponse:
    return prop_board_response(date, None, None, [_game(10)], {10: [_line(1, "Amy", "assists", 4.5)]}, {}, {}, [])


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

    async def build_prop_board(session, requested, today):
        assert isinstance(session, FakeSession)
        builds.append((requested, today))
        await asyncio.sleep(0.01)
        if requested == dt.date(1999, 1, 1):
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

    monkeypatch.setattr(nba_repo, "get_game_dates", get_game_dates)
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
        failing = dt.date(1999, 1, 1)
        assert asyncio.run(_get(failing)) is None
        assert asyncio.run(_get(failing)) is None
        assert len(builds) == 1
        clock.now = prop_board_cache.FAILURE_TTL_SECONDS + 1
        assert asyncio.run(_get(failing)) is None
        assert len(builds) == 2

    def test_a_failed_date_read_returns_none_without_building(self, builds):
        assert asyncio.run(prop_board_cache.cached_prop_board_json(BROKEN_DB, None, TODAY)) is None
        assert builds == []


def test_cached_bytes_match_what_the_response_model_sent():
    board = prop_board_response(
        DATE, PREVIOUS, NEXT, [_game(20, "completed"), _game(10, "postponed", None)],
        {20: [_line(1, "Amy", "assists", 4.5), _line(2, "Zed", "points", 20.5)]},
        {20: [_line(2, "Zed", "double_double", 0.5)]}, {1: _prior()}, [_box(1, 20), _box(2, None)],
    )
    app = FastAPI()

    @app.get("/model", response_model=NbaPropBoardResponse)
    def through_model() -> NbaPropBoardResponse:
        return board

    @app.get("/bytes", response_model=NbaPropBoardResponse)
    def through_bytes() -> Response:
        return Response(content=prop_board_cache.board_json(board), media_type="application/json")

    client = TestClient(app)
    expected, served = client.get("/model"), client.get("/bytes")

    assert served.headers["content-type"] == "application/json"
    assert served.content == expected.content
    assert any(line["pOver"] is not None for line in served.json()["games"][0]["lines"])
