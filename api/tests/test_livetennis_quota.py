"""Daily exhaustion must stop requests without discarding fetched matches."""
import datetime as dt
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from app.ingest import livetennis as lt


DETAIL = (
    "daily request allowance of 1,000 spent for the BASIC tier; "
    "it resets at 2026-10-21T21:00:00Z. The PRO tier allows 10,000/day"
)


@pytest.mark.anyio
async def test_daily_exhaustion_stops_other_endpoints_but_allows_usage(monkeypatch, caplog):
    requests = []

    def respond(request):
        requests.append(request.url.path)
        if request.url.path.endswith("/usage"):
            return httpx.Response(200, json={"today": {"remaining_day": 0}})
        return httpx.Response(429, json={"error": "rate_limited", "detail": DETAIL},
                              headers={"Retry-After": "60"})

    sleep = AsyncMock()
    monkeypatch.setattr(lt.asyncio, "sleep", sleep)
    async with lt.LiveTennisClient(transport=httpx.MockTransport(respond)) as client:
        for path in ("/h2h", "/h2h", "/matches", "/history/matches"):
            with pytest.raises(lt.DailyQuotaExhausted):
                await lt._get(client, path)
        assert await lt.fetch_usage(client) == {"today": {"remaining_day": 0}}
    assert len(requests) == 2
    sleep.assert_not_awaited()
    assert caplog.text.count("daily quota exhausted") == 1
    assert "2026-10-21T21:00:00Z" in caplog.text


@pytest.mark.anyio
@pytest.mark.parametrize("body", ["not json", '[]', '{"detail": 3}',
                                 '{"detail": "minute rate limit"}'])
async def test_unrecognized_429_has_bounded_retries(monkeypatch, body):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(429, text=body)

    sleep = AsyncMock()
    monkeypatch.setattr(lt.asyncio, "sleep", sleep)
    async with lt.LiveTennisClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(lt.FatalStatus):
            await lt._get(client, "/h2h")
        assert client.daily_quota_detail is None
    assert len(requests) == 3
    assert sleep.await_count == 2


@pytest.mark.anyio
async def test_temporary_rate_limit_recovers_and_403_still_skips(monkeypatch):
    responses = iter([httpx.Response(429, json={"detail": "minute limit"},
                                   headers={"Retry-After": "59"}),
                      httpx.Response(200, json={"data": []}),
                      httpx.Response(403, json={"error": "upgrade_required"})])
    sleep = AsyncMock()
    monkeypatch.setattr(lt.asyncio, "sleep", sleep)
    async with lt.LiveTennisClient(
        transport=httpx.MockTransport(lambda request: next(responses))
    ) as client:
        assert await lt._get(client, "/matches") == {"data": []}
        with pytest.raises(lt.TierBlocked):
            await lt._get(client, "/h2h")
        assert client.daily_quota_detail is None
    sleep.assert_awaited_once_with(59.0)


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/matches", "/history/matches"])
async def test_exhaustion_keeps_match_pages_but_never_partial_h2h(path):
    responses = iter([
        httpx.Response(200, json={"data": [{"id": 1}], "meta": {"has_more": True}}),
        httpx.Response(429, json={"detail": DETAIL}),
    ])
    async with lt.LiveTennisClient(
        transport=httpx.MockTransport(lambda request: next(responses))
    ) as client:
        if path == "/matches":
            assert await lt._get_paginated(client, path, {}) == [{"id": 1}]
        else:
            with pytest.raises(lt.DailyQuotaExhausted):
                await lt._get_paginated(client, path, {})


@pytest.mark.anyio
@pytest.mark.parametrize("exhaust_during", ["matches", "h2h"])
async def test_run_commits_fetched_matches_and_skips_later_windows(
    monkeypatch, caplog, exhaust_during,
):
    from app.config import settings
    from app.db import retry
    from app.repositories import matches

    raw = json.loads((Path(__file__).parent / "fixtures" / "livetennis_matches.json")
                     .read_text(encoding="utf-8"))["data"]
    records = [r for r in raw if lt.normalize_match(r) is not None][:2]
    assert len(records) == 2
    calls = []

    def respond(request):
        path = request.url.path.rsplit("/", 1)[-1]
        calls.append(path)
        if path == "usage":
            return httpx.Response(200, json={})
        if path == "matches" and calls.count("matches") == 1:
            return httpx.Response(200, json={
                "data": records, "meta": {"has_more": exhaust_during == "matches"},
            })
        if path == "matches" and exhaust_during == "h2h":
            return httpx.Response(200, json={"data": []})
        return httpx.Response(429, json={"detail": DETAIL})

    # Use the real client class for isinstance checks, supplying only its transport.
    monkeypatch.setattr(lt.LiveTennisClient, "__init__", lambda self, **kwargs: httpx.AsyncClient.__init__(
        self, transport=httpx.MockTransport(respond), **kwargs,
    ))
    monkeypatch.setattr(settings, "livetennis_api_key", "test-key")
    resolve = AsyncMock(side_effect=[1, 2, 3, 4])
    monkeypatch.setattr(lt, "_resolve_or_create", resolve)
    upsert = AsyncMock()
    monkeypatch.setattr(matches, "upsert_match", upsert)
    db = AsyncMock()

    async def write_in_session(write, **kwargs):
        return await write(db)

    monkeypatch.setattr(retry, "run_in_session_with_retry", write_in_session)
    sleep = AsyncMock()
    monkeypatch.setattr(lt.asyncio, "sleep", sleep)
    await lt.run(date_from_arg=dt.date(2025, 1, 1), date_to_arg=dt.date(2025, 1, 3),
                 tours=["atp"], chunk_days=1)
    assert upsert.await_count == 2
    db.commit.assert_awaited_once()
    assert calls == (["usage", "matches", "matches"] if exhaust_during == "matches"
                     else ["usage", "matches", "h2h"])
    sleep.assert_not_awaited()
    assert "Ingest incomplete" in caplog.text
    assert "Done." not in caplog.text
