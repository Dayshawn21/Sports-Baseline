"""A burst of slate loads computes predictions once, never shares a mutable
result, and recovers from a failure within seconds."""
import asyncio
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import tennis as tennis_router
from app.schemas.tennis import BestPicksResponse, MatchBestPicksSchema
from app.services.tennis import best_picks_response
from app.services.tennis import prediction_cache
from app.services.tennis.live_odds_cache import TimedSingleFlight

TODAY = date(2026, 10, 15)
TOMORROW = date(2026, 10, 16)
REQUEST = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(registry=None)))


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    cache = TimedSingleFlight(
        prediction_cache.CACHE_TTL_SECONDS, clock, prediction_cache.FAILURE_TTL_SECONDS
    )
    monkeypatch.setattr(prediction_cache, "_PREDICTIONS", cache)
    return clock


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[list[date]]:
    calls: list[list[date]] = []

    async def predict_today(_db, _registry, dates):
        calls.append(dates)
        await asyncio.sleep(0.01)
        return [SimpleNamespace(match_id=1, tour="ATP", p1_odds_american=None)]

    monkeypatch.setattr(prediction_cache, "predict_today", predict_today)
    return calls


def _get(dates: list[date]):
    return prediction_cache.cached_predictions(None, None, dates, TODAY)


class TestCacheKey:
    def test_dates_are_sorted_and_deduplicated(self):
        assert prediction_cache.cache_key([TOMORROW, TODAY, TODAY], TODAY) == (TODAY, TOMORROW)

    def test_the_window_runs_from_yesterday_to_two_days_ahead(self):
        assert prediction_cache.cache_key([date(2026, 10, 14), date(2026, 10, 17)], TODAY)
        assert prediction_cache.cache_key([date(2026, 10, 13)], TODAY) is None
        assert prediction_cache.cache_key([TODAY, date(2026, 10, 18)], TODAY) is None


@pytest.mark.usefixtures("clock")
class TestCachedPredictions:
    def test_a_burst_of_twenty_computes_once(self, calls):
        async def run():
            return await asyncio.gather(*(_get([TODAY, TOMORROW]) for _ in range(20)))

        results = asyncio.run(run())
        assert len(calls) == 1
        assert all(r[0].match_id == 1 for r in results)

    def test_date_order_shares_one_entry(self, calls):
        async def run():
            await _get([TODAY, TOMORROW])
            await _get([TOMORROW, TODAY])

        asyncio.run(run())
        assert calls == [[TODAY, TOMORROW]]

    def test_a_caller_mutating_its_result_leaves_the_cache_unchanged(self, calls):
        async def run():
            first = await _get([TODAY])
            first[0].p1_odds_american = -150
            first.clear()
            return await _get([TODAY])

        second = asyncio.run(run())
        assert len(calls) == 1
        assert second[0].p1_odds_american is None

    def test_a_result_expires_after_five_minutes(self, clock, calls):
        async def run():
            await _get([TODAY])
            clock.now = prediction_cache.CACHE_TTL_SECONDS - 1
            await _get([TODAY])
            clock.now = prediction_cache.CACHE_TTL_SECONDS + 1
            await _get([TODAY])

        asyncio.run(run())
        assert len(calls) == 2

    def test_an_out_of_window_date_is_never_cached(self, calls):
        far = date(2026, 12, 25)

        async def run():
            await _get([far])
            await _get([far])

        asyncio.run(run())
        assert calls == [[far], [far]]


def test_a_failure_is_retried_after_ten_seconds(clock, monkeypatch):
    attempts: list[float] = []

    async def failing(_db, _registry, _dates):
        attempts.append(clock.now)
        if len(attempts) == 1:
            raise RuntimeError("database went away")
        return []

    monkeypatch.setattr(prediction_cache, "predict_today", failing)

    async def run():
        first = await _get([TODAY])
        clock.now = prediction_cache.FAILURE_TTL_SECONDS - 1
        during = await _get([TODAY])
        clock.now = prediction_cache.FAILURE_TTL_SECONDS + 1
        after = await _get([TODAY])
        return first, during, after

    assert asyncio.run(run()) == (None, None, [])
    assert len(attempts) == 2


def test_the_default_failure_window_is_the_success_window():
    clock, attempts = Clock(), []

    async def failing():
        attempts.append(1)
        raise RuntimeError("429")

    cache = TimedSingleFlight(900, clock)

    async def run():
        await cache.get("k", failing)
        clock.now = 899
        await cache.get("k", failing)
        clock.now = 901
        await cache.get("k", failing)

    asyncio.run(run())
    assert len(attempts) == 2


def test_the_slate_returns_503_when_predictions_fail(monkeypatch):
    async def unavailable(_db, _registry, _dates, _today):
        return None

    monkeypatch.setattr(best_picks_response, "cached_predictions", unavailable)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(registry=None)))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(tennis_router._slate_predictions(None, request, None, TODAY))
    assert exc.value.status_code == 503
    assert exc.value.detail == tennis_router.PREDICTIONS_UNAVAILABLE


def _match(match_id: int, tour: str):
    return MatchBestPicksSchema.model_construct(match_id=match_id, tour=tour, picks=[])


def test_best_picks_build_once_for_every_tour(clock, monkeypatch):
    builds: list[int] = []
    monkeypatch.setattr(
        prediction_cache,
        "_BEST_PICKS",
        TimedSingleFlight(prediction_cache.CACHE_TTL_SECONDS, clock, prediction_cache.FAILURE_TTL_SECONDS),
    )

    async def build(_db, _registry, match_date, today):
        builds.append(1)
        matches = [_match(1, "ATP"), _match(2, "WTA"), _match(3, "atp")]
        return BestPicksResponse(date=match_date or today, count=3, matches=matches)

    monkeypatch.setattr(best_picks_response, "build_best_picks_response", build)

    async def run():
        atp = await tennis_router.get_best_picks(None, "ATP", REQUEST, None)
        wta = await tennis_router.get_best_picks(None, "wta", REQUEST, None)
        every = await tennis_router.get_best_picks(None, None, REQUEST, None)
        return atp, wta, every

    atp, wta, every = asyncio.run(run())
    assert len(builds) == 1
    assert [m.match_id for m in atp.matches] == [1, 3] and atp.count == 2
    assert [m.match_id for m in wta.matches] == [2] and wta.count == 1
    assert every.count == 3


def test_best_picks_return_503_when_the_build_fails(clock, monkeypatch):
    monkeypatch.setattr(
        prediction_cache,
        "_BEST_PICKS",
        TimedSingleFlight(prediction_cache.CACHE_TTL_SECONDS, clock, prediction_cache.FAILURE_TTL_SECONDS),
    )

    async def build(*_args):
        raise HTTPException(status_code=503, detail=tennis_router.PREDICTIONS_UNAVAILABLE)

    monkeypatch.setattr(best_picks_response, "build_best_picks_response", build)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(tennis_router.get_best_picks(None, None, REQUEST, None))
    assert exc.value.status_code == 503
