import asyncio

import httpx

from app.ingest.odds_api import (
    RateLimitState,
    _fetch_matched_odds,
    _fetch_odds_batch,
    _quota_too_low,
    _rate_limit_state,
)


class _Response:
    headers = {
        "x-ratelimit-limit": "500",
        "x-ratelimit-remaining": "4",
        "x-ratelimit-reset": "2026-09-01T00:00:00Z",
    }

    def raise_for_status(self):
        return None

    def json(self):
        return {"data": [{"id": 10}]}


class _Client:
    def __init__(self):
        self.params = None

    async def get(self, _url, params, timeout):
        self.params = params
        return _Response()


def test_rate_limit_state_parses_known_headers():
    state = _rate_limit_state(
        {
            "x-ratelimit-limit": "500",
            "x-ratelimit-remaining": "17",
            "x-ratelimit-reset": "2026-09-01T00:00:00Z",
        }
    )

    assert state.limit == 500
    assert state.remaining == 17
    assert state.reset == "2026-09-01T00:00:00Z"
    assert state.present is True


def test_rate_limit_state_tolerates_missing_headers():
    state = _rate_limit_state({})

    assert state.limit is None
    assert state.remaining is None
    assert state.reset is None
    assert state.present is False


def test_rate_limit_state_ignores_invalid_integer_headers():
    state = _rate_limit_state(
        {
            "x-ratelimit-limit": "free",
            "x-ratelimit-remaining": "unknown",
            "x-ratelimit-reset": "soon",
        }
    )

    assert state.limit is None
    assert state.remaining is None
    assert state.reset == "soon"
    assert state.present is True


def test_quota_too_low_uses_safety_floor():
    assert _quota_too_low(RateLimitState(remaining=5), min_remaining=5) is True
    assert _quota_too_low(RateLimitState(remaining=6), min_remaining=5) is False


def test_quota_too_low_does_not_block_when_header_is_absent():
    assert _quota_too_low(RateLimitState(), min_remaining=5) is False


def test_fetch_odds_batch_returns_events_and_rate_limit_state():
    client = _Client()

    events, state = asyncio.run(
        _fetch_odds_batch(client, "secret", [10, 11], "DraftKings,FanDuel")
    )

    assert client.params == {
        "eventIds": "10,11",
        "bookmakers": "DraftKings,FanDuel",
        "apiKey": "secret",
    }
    assert events == [{"id": 10}]
    assert state.remaining == 4


class _StatusClient:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.calls = 0

    async def get(self, url, params, timeout):
        self.calls += 1
        status = self.statuses.pop(0)
        request = httpx.Request("GET", url)
        if status != 200:
            return httpx.Response(status, request=request, text="plan")
        ids = params["eventIds"].split(",")
        return httpx.Response(200, request=request, json={"data": [{"id": int(i)} for i in ids]})


def test_a_plan_refusal_on_the_first_batch_reports_blocked_with_no_odds():
    client = _StatusClient([403])
    odds, blocked = asyncio.run(_fetch_matched_odds(client, "k", list(range(15)), "DraftKings,FanDuel", 0, 0))
    assert (odds, blocked, client.calls) == ({}, True, 1)


def test_a_plan_refusal_after_a_good_batch_keeps_the_odds_already_fetched():
    client = _StatusClient([200, 402])
    odds, blocked = asyncio.run(_fetch_matched_odds(client, "k", list(range(15)), "DraftKings,FanDuel", 0, 0))
    assert blocked is True
    assert sorted(odds) == list(range(10))


def test_a_server_error_skips_only_its_batch():
    client = _StatusClient([500, 200])
    odds, blocked = asyncio.run(_fetch_matched_odds(client, "k", list(range(15)), "DraftKings,FanDuel", 0, 0))
    assert blocked is False
    assert sorted(odds) == list(range(10, 15))
