"""The NBA and NHL slate caches: one build per (requested, today) within the TTL,
and a failed build still reaches the client as an error."""
import asyncio
import datetime as dt
from types import ModuleType

import pytest
from fastapi import HTTPException

from app.schemas.nba import NbaSlateResponse
from app.schemas.nhl import NhlSlateResponse
from app.services.nba import slate as nba_slate
from app.services.nhl import slate as nhl_slate
from app.services.serial_build_cache import SerialBuildCache

TODAY = dt.date(2026, 11, 11)
TOMORROW = TODAY + dt.timedelta(days=1)
AS_OF = dt.datetime(2026, 11, 11, 18, 0, tzinfo=dt.timezone.utc)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _install(monkeypatch: pytest.MonkeyPatch, module: ModuleType, clock: Clock, reraise: tuple[type[Exception], ...]) -> None:
    cache: SerialBuildCache[object] = SerialBuildCache(
        module.CACHE_TTL_SECONDS, module.FAILURE_TTL_SECONDS, module.MAX_ENTRIES, clock, reraise=reraise,
    )
    monkeypatch.setattr(module, "_SLATES", cache)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    _install(monkeypatch, nba_slate, clock, ())
    _install(monkeypatch, nhl_slate, clock, (HTTPException,))
    return clock


def _nba_builds(monkeypatch: pytest.MonkeyPatch) -> list[tuple[dt.date | None, dt.date]]:
    builds: list[tuple[dt.date | None, dt.date]] = []

    async def build(_db, requested, today):
        builds.append((requested, today))
        return NbaSlateResponse(date=requested or today, previous_date=None, next_date=None, games=[])

    monkeypatch.setattr(nba_slate, "build_slate", build)
    return builds


def _nhl_builds(monkeypatch: pytest.MonkeyPatch) -> list[tuple[dt.date | None, dt.date, dt.datetime | None]]:
    builds: list[tuple[dt.date | None, dt.date, dt.datetime | None]] = []

    async def build(_db, requested, today, *, as_of=None):
        builds.append((requested, today, as_of))
        return NhlSlateResponse(date=requested or today, previous_date=None, next_date=None, games=[])

    monkeypatch.setattr(nhl_slate, "build_slate", build)
    return builds


def test_nba_repeats_within_the_ttl_share_one_build(monkeypatch, clock) -> None:
    builds = _nba_builds(monkeypatch)

    first = asyncio.run(nba_slate.cached_slate(None, None, TODAY))
    clock.now = nba_slate.CACHE_TTL_SECONDS - 1
    assert asyncio.run(nba_slate.cached_slate(None, None, TODAY)) == first
    clock.now = nba_slate.CACHE_TTL_SECONDS + 1
    asyncio.run(nba_slate.cached_slate(None, None, TODAY))

    assert builds == [(None, TODAY), (None, TODAY)]


def test_nba_keys_build_separately(monkeypatch, clock) -> None:
    builds = _nba_builds(monkeypatch)

    asyncio.run(nba_slate.cached_slate(None, None, TODAY))
    asyncio.run(nba_slate.cached_slate(None, TOMORROW, TODAY))
    asyncio.run(nba_slate.cached_slate(None, None, TOMORROW))

    assert builds == [(None, TODAY), (TOMORROW, TODAY), (None, TOMORROW)]


def test_nba_failed_build_is_a_503(monkeypatch, clock) -> None:
    async def fail(_db, _requested, _today):
        raise RuntimeError("db down")

    monkeypatch.setattr(nba_slate, "build_slate", fail)
    with pytest.raises(HTTPException) as raised:
        asyncio.run(nba_slate.cached_slate(None, None, TODAY))
    assert raised.value.status_code == 503


def test_nhl_repeats_share_one_build_and_forward_the_clock(monkeypatch, clock) -> None:
    builds = _nhl_builds(monkeypatch)

    first = asyncio.run(nhl_slate.cached_slate(None, None, TODAY, as_of=AS_OF))
    later = asyncio.run(nhl_slate.cached_slate(None, None, TODAY, as_of=AS_OF + dt.timedelta(minutes=1)))
    asyncio.run(nhl_slate.cached_slate(None, TOMORROW, TODAY, as_of=AS_OF))

    assert later == first
    assert builds == [(None, TODAY, AS_OF), (TOMORROW, TODAY, AS_OF)]


def test_nhl_missing_migration_message_passes_through_uncached(monkeypatch, clock) -> None:
    calls: list[int] = []

    async def missing(_db, _requested, _today, *, as_of=None):
        calls.append(1)
        raise HTTPException(503, "NHL context storage is unavailable; apply migration 0050.")

    monkeypatch.setattr(nhl_slate, "build_slate", missing)
    for _ in range(2):
        with pytest.raises(HTTPException) as raised:
            asyncio.run(nhl_slate.cached_slate(None, None, TODAY, as_of=AS_OF))
        assert raised.value.detail == "NHL context storage is unavailable; apply migration 0050."
    assert len(calls) == 2


def test_nhl_other_failures_are_a_503(monkeypatch, clock) -> None:
    async def fail(_db, _requested, _today, *, as_of=None):
        raise RuntimeError("db down")

    monkeypatch.setattr(nhl_slate, "build_slate", fail)
    with pytest.raises(HTTPException) as raised:
        asyncio.run(nhl_slate.cached_slate(None, None, TODAY, as_of=AS_OF))
    assert raised.value.status_code == 503
    assert raised.value.detail == "The NHL slate is unavailable; try again shortly"
