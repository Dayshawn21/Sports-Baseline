"""Ingest NFL DraftKings and FanDuel game odds from Odds-API.io (item 36a).

The free plan allows two books across every sport (Bet365 went paid-only on
2026-10-26, so FanDuel replaced it) and 100 requests an
hour, shared with tennis, so a refresh is one `/events` call plus one
`/odds/multi` call per 10 games, and stops before the hour runs low. Rows are
stored as provider `odds_api_io`, which no pre-36a reader sees.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.core.nfl_odds import match_scheduled_game
from app.core.nfl_odds_io import parse_io_game_markets
from app.core.odds_providers import ODDS_API_IO
from app.db.pool import SessionLocal
from app.ingest.log_config import configure_ingest_logging
from app.repositories import nfl as nfl_repo

logger = logging.getLogger("nfl_odds_io_ingest")
configure_ingest_logging()

BASE_URL = "https://api.odds-api.io/v3"
BOOKMAKERS = "DraftKings,FanDuel"
NFL_LEAGUE = "usa-nfl"
MAX_EVENTS_PER_REQUEST = 10
DEFAULT_DAYS_AHEAD = 7
DEFAULT_MIN_REQUESTS_REMAINING = 20


def batches(event_ids: Sequence[int], size: int = MAX_EVENTS_PER_REQUEST) -> list[list[int]]:
    return [list(event_ids[start:start + size]) for start in range(0, len(event_ids), size)]


def can_request(remaining: int | None, min_remaining: int) -> bool:
    """An unknown balance stops the run: tennis shares the hour, so never assume plenty."""
    return remaining is not None and remaining - 1 >= min_remaining


def select_events(
    events: Sequence[Mapping[str, object]], games: list[dict[str, object]], now: datetime,
) -> tuple[dict[int, tuple[int, bool]], Counter[str]]:
    """Pending NFL events matched to a stored game that has not kicked off: event id -> (game id, homes agree)."""
    selected: dict[int, tuple[int, bool]] = {}
    skipped: Counter[str] = Counter()
    starts = {int(game["game_id"]): game.get("start_utc") for game in games}
    for event in events:
        league = event.get("league")
        if not isinstance(league, Mapping) or league.get("slug") != NFL_LEAGUE:
            continue
        if event.get("status") != "pending":
            skipped["not_pending"] += 1
            continue
        matched = match_scheduled_game({"home_team": event.get("home"), "away_team": event.get("away"), "commence_time": event.get("date")}, games)
        if matched is None:
            skipped["unmatched"] += 1
            continue
        start = starts.get(matched[0])
        if isinstance(start, datetime) and start <= now:
            skipped["started"] += 1
            continue
        selected[int(str(event["id"]))] = matched
    return selected, skipped


def _remaining(headers: Mapping[str, str]) -> int | None:
    try:
        return int(headers.get("x-ratelimit-remaining", ""))
    except ValueError:
        return None


async def _get(client: httpx.AsyncClient, path: str, params: dict[str, str]) -> tuple[object, int | None]:
    response = await client.get(f"{BASE_URL}{path}", params={**params, "apiKey": _api_key()}, timeout=30)
    response.raise_for_status()
    return response.json(), _remaining(response.headers)


def _api_key() -> str:
    key = settings.odds_api_key.strip()
    if not key:
        raise RuntimeError("ODDS_API_KEY is required for Odds-API.io NFL odds")
    return key


async def run(
    days_ahead: int = DEFAULT_DAYS_AHEAD, min_requests_remaining: int = DEFAULT_MIN_REQUESTS_REMAINING, dry_run: bool = False,
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    async with SessionLocal() as db, httpx.AsyncClient() as client:
        games = await nfl_repo.get_upcoming_games(db, days_ahead)
        events, remaining = await _get(client, "/events", {"sport": "american-football"})
        counts["requests"] += 1
        selected, skipped = select_events(events if isinstance(events, list) else [], games, datetime.now(timezone.utc))
        counts.update(skipped)
        counts["matched"] = len(selected)
        for event_ids in batches(list(selected)):
            if not can_request(remaining, min_requests_remaining):
                logger.warning("stopping: %s Odds-API.io requests left this hour, floor is %d", remaining, min_requests_remaining)
                counts["stopped_at_floor"] = 1
                break
            try:
                payload, remaining = await _get(client, "/odds/multi", {"eventIds": ",".join(map(str, event_ids)), "bookmakers": BOOKMAKERS})
            except httpx.HTTPError as exc:
                # Never retry: the hour is shared with tennis.
                logger.warning("odds batch %s failed without retry: %s", event_ids, exc)
                counts["failed"] += 1
                continue
            counts["requests"] += 1
            for event in payload if isinstance(payload, list) else []:
                match = selected.get(int(str(event.get("id"))))
                if match is None:
                    counts["unrequested_event"] += 1
                    continue
                game_id, home_is_stored_home = match
                for book, markets in (event.get("bookmakers") or {}).items():
                    for market in parse_io_game_markets(markets if isinstance(markets, list) else [], home_is_stored_home):
                        if not dry_run:
                            await nfl_repo.insert_game_odds_snapshot(
                                db, game_id, book.lower(), market.market, market.line, market.first_side, market.second_side,
                                market.first_odds, market.second_odds, market.first_market_prob, market.second_market_prob,
                                market.raw_market, provider=ODDS_API_IO,
                            )
                        counts["stored"] += 1
        if not dry_run:
            await db.commit()
    logger.info("NFL Odds-API.io ingest: %s dry_run=%s requests left this hour=%s", dict(counts), dry_run, remaining)
    return dict(counts)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Ingest NFL DraftKings and FanDuel game odds from Odds-API.io")
    parser.add_argument("--days-ahead", type=int, default=DEFAULT_DAYS_AHEAD)
    parser.add_argument("--min-requests-remaining", type=int, default=DEFAULT_MIN_REQUESTS_REMAINING)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    await run(args.days_ahead, args.min_requests_remaining, args.dry_run)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
