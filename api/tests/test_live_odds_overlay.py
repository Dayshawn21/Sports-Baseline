"""The live moneyline overlay must not spend quota per request, and must attach
odds only to the event that is this match, the right way round."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest

from app.routers import props as props_router
from app.services.tennis import best_picks_response
from app.services.tennis.live_odds_cache import LiveOddsRateLimited, TimedSingleFlight

START = datetime(2026, 9, 26, 8, 30, tzinfo=timezone.utc)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class TestTimedSingleFlight:
    def test_a_result_is_reused_until_it_expires(self):
        clock, calls = Clock(), []

        async def fetch():
            calls.append(clock.now)
            return {"n": len(calls)}

        cache = TimedSingleFlight(900, clock)

        async def run():
            first = await cache.get("k", fetch)
            clock.now = 899
            second = await cache.get("k", fetch)
            clock.now = 901
            third = await cache.get("k", fetch)
            return first, second, third

        assert asyncio.run(run()) == ({"n": 1}, {"n": 1}, {"n": 2})
        assert len(calls) == 2

    def test_concurrent_callers_share_one_fetch(self):
        calls = []

        async def fetch():
            calls.append(1)
            await asyncio.sleep(0.01)
            return "odds"

        cache = TimedSingleFlight(900, Clock())

        async def run():
            return await asyncio.gather(cache.get("k", fetch), cache.get("k", fetch))

        assert asyncio.run(run()) == ["odds", "odds"]
        assert len(calls) == 1

    def test_a_failure_is_cached_rather_than_retried_per_call(self):
        calls = []

        async def fetch():
            calls.append(1)
            raise RuntimeError("429: rate limit")

        cache = TimedSingleFlight(900, Clock())

        async def run():
            return await cache.get("k", fetch), await cache.get("k", fetch)

        assert asyncio.run(run()) == (None, None)
        assert len(calls) == 1

    def test_max_entries_drops_the_least_recently_stored_key_and_its_lock(self):
        calls = []

        async def fetch():
            calls.append(1)
            return len(calls)

        cache = TimedSingleFlight(900, Clock(), max_entries=2)

        async def run():
            for key in (2024, 2025, 2026):
                await cache.get(key, fetch)
            return await cache.get(2025, fetch), await cache.get(2024, fetch)

        assert asyncio.run(run()) == (2, 4)
        assert list(cache._entries) == [2026, 2024]
        assert set(cache._locks) == {2026, 2024}

    def test_a_lock_held_by_a_build_survives_eviction(self):
        release = asyncio.Event()

        async def slow():
            await release.wait()
            return "slow"

        async def fast():
            return "fast"

        cache = TimedSingleFlight(900, Clock(), max_entries=1)

        async def run():
            await cache.get("a", fast)
            # Expire "a" so a rebuild takes its lock, then evict it while that build is open.
            cache._clock.now = 1000
            rebuild = asyncio.create_task(cache.get("a", slow))
            await asyncio.sleep(0)
            held = cache._locks["a"]
            await cache.get("b", fast)
            assert cache._locks.get("a") is held
            release.set()
            return await rebuild

        assert asyncio.run(run()) == "slow"

    def test_without_max_entries_nothing_is_dropped(self):
        async def fetch():
            return "x"

        cache = TimedSingleFlight(900, Clock())

        async def run():
            for key in range(50):
                await cache.get(key, fetch)

        asyncio.run(run())
        assert len(cache._entries) == 50


def _pred(**over):
    base = dict(p1_name="Valentin Vacherot", p2_name="Lloyd Harris", start_utc=START,
                p1_odds_american=None, p2_odds_american=None)
    base.update(over)
    return SimpleNamespace(**base)


def _event(home: str, away: str, start: datetime, home_dec: str, away_dec: str) -> dict:
    return {
        "home": home, "away": away, "start": start.isoformat(),
        "bookmakers": [{"bookmaker": "DraftKings", "markets": [
            {"name": "ML", "selections": [{"home": home_dec, "away": away_dec}]},
        ]}],
    }


@pytest.fixture
def live(monkeypatch):
    """Serve fixed live events through a fresh cache, counting API calls."""
    calls = []
    payload: dict = {"events": []}

    async def fake_fetch(bookmakers: str, hours_ahead: int) -> dict:
        calls.append((bookmakers, hours_ahead))
        return payload

    monkeypatch.setattr(props_router, "_fetch_live_tennis_odds", fake_fetch)
    monkeypatch.setattr(best_picks_response, "_LIVE_ODDS", TimedSingleFlight(900, Clock()))
    return SimpleNamespace(calls=calls, payload=payload)


class TestOverlay:
    def test_reversed_home_away_fills_odds_the_right_way_round(self, live):
        live.payload["events"] = [_event("Harris, Lloyd", "Vacherot, Valentin", START, "2.60", "1.50")]
        pred = _pred()
        asyncio.run(best_picks_response.overlay_live_moneyline([pred]))
        assert (pred.p1_odds_american, pred.p2_odds_american) == (-200, 160)

    def test_an_event_thirteen_hours_away_is_not_this_match(self, live):
        live.payload["events"] = [_event("Vacherot, Valentin", "Harris, Lloyd", START + timedelta(hours=13), "1.80", "2.00")]
        pred = _pred()
        asyncio.run(best_picks_response.overlay_live_moneyline([pred]))
        assert pred.p1_odds_american is None

    def test_two_requests_in_the_window_cost_one_lookup(self, live):
        live.payload["events"] = [_event("Vacherot, Valentin", "Harris, Lloyd", START, "1.80", "2.00")]

        async def two_page_requests():
            await best_picks_response.overlay_live_moneyline([_pred()])
            await best_picks_response.overlay_live_moneyline([_pred()])

        asyncio.run(two_page_requests())
        assert len(live.calls) == 1

    def test_predictions_with_stored_odds_never_call_the_api(self, live):
        asyncio.run(best_picks_response.overlay_live_moneyline([_pred(p1_odds_american=-150, p2_odds_american=130)]))
        assert live.calls == []


def test_a_provider_429_becomes_a_rate_limit_error():
    request = httpx.Request("GET", "https://api.odds-api.io/v3/events")
    response = httpx.Response(429, headers={"x-ratelimit-reset": "1790000000"}, text="{}", request=request)
    error = props_router._provider_status_error(
        httpx.HTTPStatusError("429", request=request, response=response), "Events fetch failed"
    )
    assert isinstance(error, LiveOddsRateLimited)
    assert error.status_code == 429
    assert error.reset == "1790000000"
