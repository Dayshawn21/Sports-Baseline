"""The NBA board cache shares one build per date, keys the default date by
today, and serves the bytes the response model would have sent."""
import asyncio
import datetime as dt

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from app.schemas.nba import NbaPropBoardResponse
from app.services.nba import prop_board_cache
from app.services.nba.prop_board import prop_board_response
from app.services.serial_build_cache import SerialBuildCache
from tests.test_nba_prop_board import DATE, NEXT, PREVIOUS, _box, _game, _line, _prior

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
    cache: SerialBuildCache[bytes] = SerialBuildCache(
        prop_board_cache.CACHE_TTL_SECONDS, prop_board_cache.FAILURE_TTL_SECONDS, prop_board_cache.MAX_ENTRIES, clock,
    )
    monkeypatch.setattr(prop_board_cache, "_BOARDS", cache)
    return clock


@pytest.fixture
def builds(monkeypatch: pytest.MonkeyPatch) -> list[tuple[dt.date | None, dt.date]]:
    builds: list[tuple[dt.date | None, dt.date]] = []

    async def build_prop_board(_db, requested, today):
        builds.append((requested, today))
        await asyncio.sleep(0.01)
        if requested == dt.date(1999, 1, 1):
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
            return await asyncio.gather(*(_get(DATE) for _ in range(10)))

        bodies = asyncio.run(burst())
        assert builds == [(DATE, TODAY)]
        assert len(set(bodies)) == 1 and bodies[0] == prop_board_cache.board_json(_board(DATE))

    def test_explicit_dates_and_the_default_are_separate_keys(self, builds):
        for requested, today in [(DATE, TODAY), (None, TODAY), (DATE, TODAY), (None, TODAY), (None, TOMORROW)]:
            asyncio.run(_get(requested, today))
        assert builds == [(DATE, TODAY), (None, TODAY), (None, TOMORROW)]

    def test_a_board_is_rebuilt_only_after_it_expires(self, builds, clock):
        asyncio.run(_get(DATE))
        clock.now = prop_board_cache.CACHE_TTL_SECONDS - 1
        asyncio.run(_get(DATE))
        assert len(builds) == 1
        clock.now = prop_board_cache.CACHE_TTL_SECONDS + 1
        asyncio.run(_get(DATE))
        assert len(builds) == 2

    def test_a_failed_build_returns_none_then_retries(self, builds, clock):
        failing = dt.date(1999, 1, 1)
        assert asyncio.run(_get(failing)) is None
        assert asyncio.run(_get(failing)) is None
        assert len(builds) == 1
        clock.now = prop_board_cache.FAILURE_TTL_SECONDS + 1
        assert asyncio.run(_get(failing)) is None
        assert len(builds) == 2


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
