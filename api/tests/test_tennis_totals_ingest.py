import asyncio
import datetime as dt
import json
from pathlib import Path

import httpx

from app.core.tennis_totals import TennisTotal
from app.ingest import tennis_totals

EVENTS = json.loads((Path(__file__).parent / "fixtures" / "the_odds_api_tennis_totals.json").read_text())
BASEL = "tennis_atp_swiss_indoors"
TOKYO = "tennis_wta_pan_pacific_open"
SPORTS = [
    {"key": BASEL, "active": True},
    {"key": TOKYO, "active": True},
    {"key": "tennis_atp_paris_masters", "active": False},
    {"key": "basketball_nba", "active": True},
]
STORED = [
    {"match_id": 1, "p1_name": "Arthur Fils", "p2_name": "Alex Michelsen",
     "start_utc": dt.datetime(2026, 10, 29, 13, tzinfo=dt.timezone.utc)},
    {"match_id": 2, "p1_name": "Taylor Fritz", "p2_name": "Denis Shapovalov",
     "start_utc": dt.datetime(2026, 10, 29, 14, 10, tzinfo=dt.timezone.utc)},
]
TOKYO_EVENTS = [{"home_team": "Naomi Osaka", "away_team": "Coco Gauff", "commence_time": "2026-10-29T01:30:00Z"}]


def _collect(remaining_after_free: int, min_credits: int = 150):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path.endswith("/sports"):
            body: object = SPORTS
        elif path.endswith(f"/{BASEL}/events"):
            body = [{k: v for k, v in e.items() if k != "bookmakers"} for e in EVENTS]
        elif path.endswith(f"/{TOKYO}/events"):
            body = TOKYO_EVENTS
        elif path.endswith(f"/{BASEL}/odds"):
            return httpx.Response(200, json=EVENTS, headers={"x-requests-remaining": str(remaining_after_free - 1)})
        else:
            return httpx.Response(404)
        return httpx.Response(200, json=body, headers={"x-requests-remaining": str(remaining_after_free)})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await tennis_totals.collect_totals(client, "k", STORED, min_credits)

    return asyncio.run(go()), requests


def _paid(requests: list[httpx.Request]) -> list[str]:
    return [r.url.path for r in requests if r.url.path.endswith("/odds")]


def test_only_keys_with_a_stored_match_get_a_paid_call():
    result, requests = _collect(200)
    assert result.active_keys == 2
    assert _paid(requests) == [f"/v4/sports/{BASEL}/odds"]
    assert result.paid_keys == [BASEL]


def test_paid_call_asks_for_totals_from_the_preferred_books_only():
    _, requests = _collect(200)
    params = next(r for r in requests if r.url.path.endswith("/odds")).url.params
    assert params["markets"] == "totals"
    assert params["bookmakers"] == "pinnacle,marathonbet,betsson,nordicbet,onexbet,coolbet"
    assert "regions" not in params


def test_totals_land_on_their_stored_matches():
    result, _ = _collect(200)
    assert result.totals == [
        (1, TennisTotal("pinnacle", 22.5, -111, -103)),
        (2, TennisTotal("marathonbet", 22.5, -109, -122)),
    ]
    assert result.unmatched == 1 and result.unpriced == 0
    assert not result.stopped_at_floor


def test_the_floor_stops_before_any_paid_call():
    result, requests = _collect(149)
    assert _paid(requests) == []
    assert result.stopped_at_floor and result.totals == []


def _collect_with(handler):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await tennis_totals.collect_totals(client, "secret-key", STORED, 150)

    return asyncio.run(go())


def test_a_failed_events_listing_skips_only_that_key_without_logging_the_key(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/sports"):
            return httpx.Response(200, json=SPORTS, headers={"x-requests-remaining": "200"})
        return httpx.Response(422)

    result = _collect_with(handler)
    assert result.paid_keys == [] and result.totals == []
    assert "HTTP 422" in caplog.text and "secret-key" not in caplog.text


def test_a_failed_sports_listing_fails_the_run_without_the_key():
    try:
        _collect_with(lambda request: httpx.Response(401))
    except RuntimeError as exc:
        assert "HTTP 401" in str(exc) and "secret-key" not in str(exc)
        assert exc.__cause__ is None and exc.__suppress_context__
    else:
        raise AssertionError("a failed /sports listing must fail the run")


def test_stored_rows_follow_the_match_odds_total_contract(monkeypatch):
    inserted: list[tuple[object, ...]] = []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def commit(self):
            inserted.append(("commit",))

    async def upcoming(*_args, **_kwargs):
        return STORED

    async def collect(*_args):
        return tennis_totals.TotalsRun(totals=[(1, TennisTotal("pinnacle", 22.5, -111, -103))])

    async def insert(_db, *row):
        inserted.append(row)

    monkeypatch.setattr(tennis_totals, "SessionLocal", _Session)
    monkeypatch.setattr(tennis_totals, "_load_upcoming", upcoming)
    monkeypatch.setattr(tennis_totals, "collect_totals", collect)
    monkeypatch.setattr(tennis_totals, "_insert_odds", insert)
    monkeypatch.setattr(tennis_totals, "_provider_key", lambda: "k")

    asyncio.run(tennis_totals.run())
    assert inserted == [(1, "pinnacle", "total_games", -111, -103, 22.5), ("commit",)]

    inserted.clear()
    asyncio.run(tennis_totals.run(dry_run=True))
    assert inserted == []
