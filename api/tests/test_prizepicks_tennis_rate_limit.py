import asyncio

import httpx
import pytest

from app.ingest import prizepicks
from app.ingest.prizepicks import PrizePicksRateLimited

REQUEST = httpx.Request("GET", f"{prizepicks.PRIZEPICKS_BASE}/leagues")
CATALOG = {"data": [{"id": 7, "attributes": {"name": "TENNIS"}}]}


class _Client:
    """Answers each get with the next queued response, recording every call."""

    def __init__(self, responses: list[httpx.Response]):
        self.responses = responses
        self.calls = 0

    async def get(self, *_args, **_kwargs):
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


def _throttled() -> httpx.Response:
    return httpx.Response(429, headers={"Retry-After": "0"}, request=REQUEST)


def _ok(body: dict) -> httpx.Response:
    return httpx.Response(200, json=body, request=REQUEST)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def instant(_seconds):
        return None

    monkeypatch.setattr(prizepicks.asyncio, "sleep", instant)


def test_a_catalog_throttled_past_every_retry_raises():
    client = _Client([_throttled()])

    with pytest.raises(PrizePicksRateLimited):
        asyncio.run(prizepicks._fetch_leagues(client))

    assert client.calls == prizepicks.RATE_LIMIT_ATTEMPTS


def test_a_catalog_that_recovers_returns_its_leagues():
    client = _Client([_throttled(), _ok(CATALOG)])

    assert asyncio.run(prizepicks._fetch_leagues(client)) == CATALOG["data"]


def test_an_empty_catalog_without_a_429_is_a_quiet_day():
    assert asyncio.run(prizepicks._fetch_leagues(_Client([_ok({"data": []})]))) == []


def test_a_catalog_server_error_keeps_returning_empty():
    client = _Client([httpx.Response(500, request=REQUEST)])

    assert asyncio.run(prizepicks._fetch_leagues(client)) == []


def test_every_league_throttled_raises():
    with pytest.raises(PrizePicksRateLimited):
        asyncio.run(prizepicks._fetch_league_props(_Client([_throttled()]), [1, 2]))


def test_one_throttled_league_keeps_the_others(monkeypatch):
    async def projections(_client, league_id):
        if league_id == 1:
            raise httpx.HTTPStatusError("throttled", request=REQUEST, response=_throttled())
        return {"league": league_id}

    monkeypatch.setattr(prizepicks, "_fetch_projections", projections)
    monkeypatch.setattr(prizepicks, "_parse_projections", lambda _raw, league_id: [{"league": league_id}])

    props, failed = asyncio.run(prizepicks._fetch_league_props(object(), [1, 2]))

    assert props == [{"league": 2}]
    assert failed == 1
