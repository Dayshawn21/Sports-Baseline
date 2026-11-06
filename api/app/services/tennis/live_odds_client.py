"""The Odds-API.io client for live tennis moneylines, read by the best-picks
overlay when the stored odds are missing."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Optional, TypedDict

import httpx
from fastapi import HTTPException

from app.config import settings
from app.core.tennis_odds_events import odds_event_tour
from app.services.tennis.live_odds_cache import LiveOddsRateLimited

logger = logging.getLogger(__name__)

ODDS_API_BASE = "https://api.odds-api.io/v3"

JsonObject = dict[str, object]


class LiveOddsMarket(TypedDict):
    name: object
    selections: list[object]


class LiveOddsBook(TypedDict):
    bookmaker: str
    marketCount: int
    markets: list[LiveOddsMarket]


class LiveOddsEvent(TypedDict):
    eventId: int
    home: object
    away: object
    start: str
    tour: str
    league: str
    bookmakers: list[LiveOddsBook]


class LiveOdds(TypedDict):
    bookmakers: str
    count: int
    events: list[LiveOddsEvent]


class _UpcomingEvent(TypedDict):
    id: int
    home: object
    away: object
    start: str
    tour: str
    league: str


def _parse_dt(value: object) -> Optional[datetime]:
    if not value:
        return None
    txt = str(value).strip()
    if not txt:
        return None
    if txt.endswith("Z"):
        txt = txt.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _extract_bookmakers(event: JsonObject) -> list[tuple[str, list[object]]]:
    out: list[tuple[str, list[object]]] = []
    books = event.get("bookmakers") or {}
    if isinstance(books, dict):
        for name, markets in books.items():
            if isinstance(markets, list):
                out.append((str(name), markets))
        return out
    if isinstance(books, list):
        for b in books:
            if not isinstance(b, dict):
                continue
            name = str(b.get("name") or b.get("key") or "").strip()
            markets = b.get("markets")
            if name and isinstance(markets, list):
                out.append((name, markets))
    return out


def _normalize_market(market: JsonObject) -> LiveOddsMarket:
    odds = market.get("odds")
    return {
        "name": market.get("name"),
        "selections": odds if isinstance(odds, list) else [],
    }


def _as_int(value: object) -> int:
    if isinstance(value, (int, float, str)):
        return int(value)
    raise TypeError(f"not an event id: {value!r}")


def _event_list(payload: object) -> list[object]:
    if isinstance(payload, dict):
        events = payload.get("data") or payload.get("events") or []
    else:
        events = payload or []
    return events if isinstance(events, list) else []


# Raised `from None`: an httpx error's message holds the request URL, and with it
# the apiKey parameter, which a logged traceback would otherwise print.
def _provider_status_error(error: httpx.HTTPStatusError, label: str) -> HTTPException:
    # The body is the provider's text, so it goes to the log, not the client.
    logger.warning("%s: HTTP %s %s", label, error.response.status_code, (error.response.text or "")[:260])
    if error.response.status_code == 429:
        return LiveOddsRateLimited(error.response.headers.get("x-ratelimit-reset"), label)
    return HTTPException(status_code=error.response.status_code, detail=label)


def _upcoming_events(events: list[object], now: datetime, cutoff: datetime) -> list[_UpcomingEvent]:
    upcoming: list[_UpcomingEvent] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        league = ev.get("league")
        league_name = str((league.get("name") if isinstance(league, dict) else None) or "")
        tour = odds_event_tour(league_name)
        if tour is None:
            continue
        start = _parse_dt(ev.get("start") or ev.get("date") or ev.get("commenceTime"))
        if start is None or start < now or start > cutoff:
            continue
        ev_id = ev.get("id")
        if ev_id is None:
            continue
        upcoming.append({
            "id": _as_int(ev_id),
            "home": ev.get("home"),
            "away": ev.get("away"),
            "start": start.isoformat(),
            "tour": tour,
            "league": league_name,
        })
    return upcoming


async def _fetch_odds_batches(
    client: httpx.AsyncClient, events: list[_UpcomingEvent], bookmakers: str, api_key: str
) -> list[object]:
    """The odds for `events`, ten event ids a request (the API limit), with a small delay between."""
    odds_events: list[object] = []
    for i in range(0, len(events), 10):
        if i > 0:
            await asyncio.sleep(0.2)
        batch_ids = ",".join(str(e["id"]) for e in events[i:i + 10])
        odds_params = {"eventIds": batch_ids, "bookmakers": bookmakers, "apiKey": api_key}
        try:
            odds_resp = await client.get(f"{ODDS_API_BASE}/odds/multi", params=odds_params)
            odds_resp.raise_for_status()
            odds_events.extend(_event_list(odds_resp.json()))
        except httpx.HTTPStatusError as e:
            raise _provider_status_error(e, "Odds fetch failed") from None
        except httpx.HTTPError as e:
            logger.warning("Odds-API.io odds fetch failed: %s", type(e).__name__)
            raise HTTPException(status_code=502, detail="Odds fetch failed") from None
    return odds_events


def _merge(events: list[_UpcomingEvent], odds_events: list[object]) -> list[LiveOddsEvent]:
    odds_by_id: dict[int, JsonObject] = {}
    for ev in odds_events:
        if isinstance(ev, dict) and ev.get("id") is not None:
            odds_by_id[_as_int(ev["id"])] = ev

    merged: list[LiveOddsEvent] = []
    for ev in events:
        raw = odds_by_id.get(ev["id"])
        if not raw:
            continue
        books: list[LiveOddsBook] = []
        for book_name, markets in _extract_bookmakers(raw):
            books.append({
                "bookmaker": book_name,
                "marketCount": len(markets),
                "markets": [_normalize_market(m) for m in markets if isinstance(m, dict)],
            })
        merged.append({
            "eventId": ev["id"],
            "home": ev["home"],
            "away": ev["away"],
            "start": ev["start"],
            "tour": ev["tour"],
            "league": ev["league"],
            "bookmakers": books,
        })
    return merged


async def fetch_live_tennis_odds(bookmakers: str, hours_ahead: int) -> LiveOdds:
    api_key = (settings.odds_api_key or "").strip()
    if not api_key:
        raise HTTPException(status_code=500, detail="ODDS_API_KEY is missing in backend config.")

    params = {"sport": "tennis", "apiKey": api_key}
    now = datetime.now(UTC)
    cutoff = now + timedelta(hours=hours_ahead)

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            events_resp = await client.get(f"{ODDS_API_BASE}/events", params=params)
            events_resp.raise_for_status()
            events_data = events_resp.json()
        except httpx.HTTPStatusError as e:
            raise _provider_status_error(e, "Events fetch failed") from None
        except httpx.HTTPError as e:
            logger.warning("Odds-API.io events fetch failed: %s", type(e).__name__)
            raise HTTPException(status_code=502, detail="Events fetch failed") from None

        upcoming = _upcoming_events(_event_list(events_data), now, cutoff)
        if not upcoming:
            return {"bookmakers": bookmakers, "count": 0, "events": []}
        odds_events = await _fetch_odds_batches(client, upcoming, bookmakers, api_key)

    merged = _merge(upcoming, odds_events)
    return {"bookmakers": bookmakers, "count": len(merged), "events": merged}
