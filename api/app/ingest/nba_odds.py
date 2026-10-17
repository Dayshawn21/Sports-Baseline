"""Ingest NBA game odds from The Odds API into `sport_game_odds` (item 20d).

One paid `/odds` call (moneyline, spread and total in region `us`: 3 credits)
per run, made only after a free `/sports` call shows the shared plan above the
NBA credit floor.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import httpx

from app.core.nba_odds import match_nba_game
from app.core.nfl_odds import parse_game_markets
from app.core.odds_providers import THE_ODDS_API_US
from app.db.pool import SessionLocal
from app.ingest.log_config import configure_ingest_logging
from app.ingest.nfl_odds import BASE_URL, _bookmaker_sets, _odds_params, _provider_key, _remaining_requests
from app.repositories import nba as nba_repo

logger = logging.getLogger("nba_odds_ingest")
configure_ingest_logging()

SPORT_KEY = "basketball_nba"
# NFL's anytime-TD runs stop at 50; stopping NBA at 100 leaves NFL room for its weekly runs.
DEFAULT_MIN_CREDITS = 100


def credit_gate(remaining: int | None, floor: int) -> bool:
    """Whether a paid call may run; an unknown balance never spends."""
    return remaining is not None and remaining >= floor


async def _free_remaining(client: httpx.AsyncClient, api_key: str) -> int | None:
    response = await client.get(f"{BASE_URL}/sports", params={"apiKey": api_key}, timeout=30)
    response.raise_for_status()
    return _remaining_requests(response.headers)


async def _fetch_odds(client: httpx.AsyncClient, api_key: str) -> tuple[list[dict[str, object]], int | None]:
    response = await client.get(f"{BASE_URL}/sports/{SPORT_KEY}/odds/", params=_odds_params(api_key), timeout=30)
    response.raise_for_status()
    payload = response.json()
    events = [event for event in payload if isinstance(event, dict)] if isinstance(payload, list) else []
    return events, _remaining_requests(response.headers)


async def run(days_ahead: int = 2, min_credits: int = DEFAULT_MIN_CREDITS, dry_run: bool = False) -> dict[str, int]:
    """Store every matched book's NBA game markets from one bounded The Odds API call."""
    counts = {"matched": 0, "unmatched": 0, "stored": 0}
    async with SessionLocal() as db, httpx.AsyncClient() as client:
        games = await nba_repo.get_upcoming_odds_games(db, days_ahead)
        if not games:
            logger.info("No scheduled NBA games in the next %d days, no provider call made", days_ahead)
            return counts
        api_key = _provider_key()
        remaining = await _free_remaining(client, api_key)
        if not credit_gate(remaining, min_credits):
            logger.warning("The Odds API credits remaining %s, below the NBA floor %d: skipping the paid call", remaining, min_credits)
            return counts
        events, remaining = await _fetch_odds(client, api_key)
        logger.info("The Odds API credits remaining after the NBA call: %s", remaining)
        for event in events:
            matched = match_nba_game(event, games)
            if matched is None:
                counts["unmatched"] += 1
                logger.debug("Unmatched NBA event: %s at %s, %s", event.get("away_team"), event.get("home_team"), event.get("commence_time"))
                continue
            game_id, provider_home_is_stored_home = matched
            counts["matched"] += 1
            for book, markets in _bookmaker_sets(event):
                for market in parse_game_markets(markets, provider_home_is_stored_home, str(event["home_team"]), str(event["away_team"])):
                    if not dry_run:
                        await nba_repo.insert_game_odds_snapshot(db, game_id, book, market.market, market.line, market.first_side, market.second_side, market.first_odds, market.second_odds, market.first_market_prob, market.second_market_prob, market.raw_market, provider=THE_ODDS_API_US)
                    counts["stored"] += 1
        if not dry_run:
            await db.commit()
    logger.info("NBA odds ingest: games=%d matched=%d unmatched=%d stored=%d dry_run=%s", len(games), counts["matched"], counts["unmatched"], counts["stored"], dry_run)
    return counts


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Ingest NBA game odds from The Odds API (3 credits a run)")
    parser.add_argument("--days-ahead", type=int, default=2)
    parser.add_argument("--min-credits", type=int, default=DEFAULT_MIN_CREDITS)
    parser.add_argument("--dry-run", action="store_true", help="still spends the 3 credits; writes nothing")
    args = parser.parse_args()
    await run(args.days_ahead, args.min_credits, args.dry_run)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
