import asyncio

import httpx

from app.ingest.odds_api import (
    RateLimitState,
    _fetch_matched_odds,
    _fetch_odds_batch,
    _quota_stop_reason,
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


def test_the_quota_floor_stops_at_or_below_it():
    assert _quota_stop_reason(RateLimitState(remaining=5), min_remaining=5) == (
        "Odds-API.io quota at the floor: 5 request(s) remaining, floor 5"
    )
    assert _quota_stop_reason(RateLimitState(remaining=6), min_remaining=5) is None


def test_an_unknown_balance_stops_with_its_reason():
    assert _quota_stop_reason(RateLimitState(), min_remaining=5) == (
        "Odds-API.io request balance unknown (x-ratelimit-remaining missing or unreadable)"
    )


def test_an_out_of_range_balance_reads_as_unknown():
    assert _rate_limit_state({"x-ratelimit-remaining": "101"}).remaining is None
    assert _rate_limit_state({"x-ratelimit-remaining": "-1"}).remaining is None


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
        return httpx.Response(
            200, request=request, json={"data": [{"id": int(i)} for i in ids]}, headers={"x-ratelimit-remaining": "50"},
        )


KNOWN = RateLimitState(remaining=50)


def test_a_plan_refusal_on_the_first_batch_reports_blocked_with_no_odds():
    client = _StatusClient([403])
    odds, blocked = asyncio.run(_fetch_matched_odds(client, "k", list(range(15)), "DraftKings,FanDuel", 0, 0, KNOWN))
    assert (odds, blocked, client.calls) == ({}, True, 1)


def test_a_plan_refusal_after_a_good_batch_keeps_the_odds_already_fetched():
    client = _StatusClient([200, 402])
    odds, blocked = asyncio.run(_fetch_matched_odds(client, "k", list(range(15)), "DraftKings,FanDuel", 0, 0, KNOWN))
    assert blocked is True
    assert sorted(odds) == list(range(10))


def test_a_server_error_skips_only_its_batch():
    client = _StatusClient([500, 200])
    odds, blocked = asyncio.run(_fetch_matched_odds(client, "k", list(range(15)), "DraftKings,FanDuel", 0, 0, KNOWN))
    assert blocked is False
    assert sorted(odds) == list(range(10, 15))


class _QuotaClient(_StatusClient):
    def __init__(self, remaining):
        super().__init__([200] * 5)
        self.remaining = list(remaining)

    async def get(self, url, params, timeout):
        response = await super().get(url, params, timeout)
        response.headers["x-ratelimit-remaining"] = str(self.remaining.pop(0))
        return response


def test_a_run_that_starts_at_the_floor_sends_no_odds_batch():
    client = _QuotaClient([])
    odds, blocked = asyncio.run(_fetch_matched_odds(
        client, "k", list(range(15)), "DraftKings,FanDuel", 5, 0, RateLimitState(remaining=5),
    ))
    assert (odds, blocked, client.calls) == ({}, False, 0)


def test_the_floor_is_checked_before_each_batch():
    client = _QuotaClient([5])
    odds, blocked = asyncio.run(_fetch_matched_odds(
        client, "k", list(range(25)), "DraftKings,FanDuel", 5, 0, RateLimitState(remaining=6),
    ))
    assert (sorted(odds), blocked, client.calls) == (list(range(10)), False, 1)


def test_an_unknown_balance_sends_no_odds_batch_and_logs_why(caplog):
    client = _QuotaClient([])
    with caplog.at_level("WARNING"):
        odds, blocked = asyncio.run(_fetch_matched_odds(
            client, "k", list(range(15)), "DraftKings,FanDuel", 5, 0, RateLimitState(),
        ))
    assert (odds, blocked, client.calls) == ({}, False, 0)
    assert "request balance unknown" in caplog.text


def test_an_unreadable_balance_after_a_batch_stops_the_next():
    client = _QuotaClient(["bad"])
    odds, blocked = asyncio.run(_fetch_matched_odds(
        client, "k", list(range(25)), "DraftKings,FanDuel", 5, 0, KNOWN,
    ))
    assert (sorted(odds), blocked, client.calls) == (list(range(10)), False, 1)
