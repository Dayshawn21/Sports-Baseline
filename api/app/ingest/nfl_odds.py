"""Ingest NFL game odds from The Odds API without using the tennis provider."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from typing import Mapping

import httpx

from app.config import settings
from app.core.nfl_odds import match_scheduled_game, parse_game_markets
from app.core.odds_providers import THE_ODDS_API_EU, THE_ODDS_API_US
from app.db.pool import SessionLocal
from app.ingest.log_config import configure_ingest_logging
from app.repositories import nfl as nfl_repo

logger = logging.getLogger("nfl_odds_ingest")
configure_ingest_logging()

BASE_URL = "https://api.the-odds-api.com/v4"
DEFAULT_SPORT = "americanfootball_nfl"
DEFAULT_REGIONS = "us"
DEFAULT_MARKETS = "h2h,spreads,totals"
PINNACLE = "pinnacle"
DEFAULT_MIN_REQUESTS_REMAINING = 5


def _provider_key() -> str:
    key = settings.the_odds_api_key.strip()
    if not key:
        raise RuntimeError("THE_ODDS_API_KEY is required - set it in api/app/.env")
    return key


def _odds_params(api_key: str, pinnacle: bool = False) -> dict[str, str]:
    # `bookmakers` replaces `regions`: Pinnacle is in the eu region, and naming it alone costs one region.
    scope = {"bookmakers": PINNACLE} if pinnacle else {"regions": DEFAULT_REGIONS}
    return {"apiKey": api_key, **scope, "markets": DEFAULT_MARKETS, "oddsFormat": "american", "dateFormat": "iso"}


def _remaining_requests(headers: object) -> int | None:
    getter = getattr(headers, "get", None)
    value = getter("x-requests-remaining") if callable(getter) else None
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def credit_gate(remaining: int | None, floor: int) -> bool:
    """Whether a paid call may run; an unknown balance never spends."""
    return remaining is not None and remaining >= floor


async def _free_remaining(client: httpx.AsyncClient, api_key: str) -> int | None:
    response = await client.get(f"{BASE_URL}/sports", params={"apiKey": api_key}, timeout=30)
    response.raise_for_status()
    return _remaining_requests(response.headers)


async def _fetch_odds(client: httpx.AsyncClient, api_key: str, pinnacle: bool = False) -> tuple[list[dict[str, object]], int | None]:
    response = await client.get(f"{BASE_URL}/sports/{DEFAULT_SPORT}/odds/", params=_odds_params(api_key, pinnacle), timeout=30)
    response.raise_for_status()
    payload = response.json()
    events = [event for event in payload if isinstance(event, dict)] if isinstance(payload, list) else []
    return events, _remaining_requests(response.headers)


def _bookmaker_sets(event: Mapping[str, object]) -> list[tuple[str, list[Mapping[str, object]]]]:
    bookmakers = event.get("bookmakers")
    if not isinstance(bookmakers, list):
        return []
    return [(str(bookmaker.get("key") or bookmaker.get("title") or ""), [market for market in bookmaker.get("markets", []) if isinstance(market, Mapping)]) for bookmaker in bookmakers if isinstance(bookmaker, Mapping) and isinstance(bookmaker.get("markets"), list)]


async def run(days_ahead: int = 14, min_requests_remaining: int = DEFAULT_MIN_REQUESTS_REMAINING, dry_run: bool = False, pinnacle: bool = False) -> dict[str, int]:
    """Refresh matched NFL markets from one bounded The Odds API request: the us region, or Pinnacle alone."""
    counts = {"matched": 0, "skipped": 0, "stored": 0}
    provider = THE_ODDS_API_EU if pinnacle else THE_ODDS_API_US
    async with SessionLocal() as db, httpx.AsyncClient() as client:
        games = await nfl_repo.get_upcoming_games(db, days_ahead)
        if not games:
            logger.info("No scheduled NFL games in the next %d days, no provider call made", days_ahead)
            return counts
        starts = {game["game_id"]: game.get("start_utc") for game in games}
        api_key = _provider_key()
        remaining = await _free_remaining(client, api_key)
        if not credit_gate(remaining, min_requests_remaining):
            logger.warning("The Odds API credits remaining %s, below the NFL floor %d: skipping the paid call", remaining, min_requests_remaining)
            return counts
        events, remaining = await _fetch_odds(client, api_key, pinnacle)
        logger.info("The Odds API credits remaining after the NFL call: %s", remaining)
        for event in events:
            matched = match_scheduled_game(event, games)
            if matched is None:
                counts["skipped"] += 1
                continue
            game_id, provider_home_is_nfl_home = matched
            start = starts.get(game_id)
            if start is not None and start <= datetime.now(timezone.utc):
                counts["skipped"] += 1
                continue
            counts["matched"] += 1
            for book, markets in _bookmaker_sets(event):
                for market in parse_game_markets(markets, provider_home_is_nfl_home, str(event["home_team"]), str(event["away_team"])):
                    if not dry_run:
                        await nfl_repo.insert_game_odds_snapshot(db, game_id, book, market.market, market.line, market.first_side, market.second_side, market.first_odds, market.second_odds, market.first_market_prob, market.second_market_prob, market.raw_market, provider=provider)
                    counts["stored"] += 1
        if not dry_run:
            await db.commit()
    logger.info("NFL odds ingest (%s): matched=%d skipped=%d stored=%d dry_run=%s", provider, counts["matched"], counts["skipped"], counts["stored"], dry_run)
    return counts


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Ingest NFL game odds from The Odds API")
    parser.add_argument("--days-ahead", type=int, default=14)
    parser.add_argument("--min-requests-remaining", type=int, default=DEFAULT_MIN_REQUESTS_REMAINING)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pinnacle", action="store_true", help="fetch Pinnacle alone (the fair-price reference), stored as the_odds_api_eu")
    args = parser.parse_args()
    await run(args.days_ahead, args.min_requests_remaining, args.dry_run, args.pinnacle)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
