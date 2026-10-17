"""Ingest NFL sportsbook player-prop prices from The Odds API under a credit floor.

The event listing is free; each per-event odds request costs one credit per
market per region. The key is on the 500-credit free plan, so nothing is fetched
unless `--confirm-spend` is passed, and the run stops before a request that
would take the balance below `--min-credits`.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Mapping

import httpx

from app.config import settings
from app.core.nfl_odds import match_scheduled_game
from app.core.nfl_prop_odds import parse_yes_no_props
from app.core.nfl_resolution import (
    PlayerCandidate, Resolution, ResolutionResult, index_candidates, resolve_player,
)
from app.db.pool import SessionLocal
from app.ingest.log_config import configure_ingest_logging
from app.ingest.nfl_odds import BASE_URL, DEFAULT_SPORT, _provider_key, _remaining_requests
from app.nfl.markets import NFL_PROPS, NflPropMarket
from app.repositories import nfl as nfl_repo
from app.repositories import sport_props

logger = logging.getLogger("nfl_prop_odds_ingest")
configure_ingest_logging()

REGIONS = "us"
# The one place a provider market is enabled. Each entry costs a credit per game.
PROP_MARKETS: dict[str, NflPropMarket] = {"player_anytime_td": NflPropMarket.ANYTIME_TOUCHDOWN}
DEFAULT_HOURS_AHEAD = 96
DEFAULT_MIN_CREDITS = 50
DEFAULT_MAX_EVENTS = 16


def select_events(
    events: list[Mapping[str, object]], games: list[dict[str, object]], now: datetime, hours_ahead: int,
) -> list[tuple[Mapping[str, object], int]]:
    """Events that match a scheduled game and kick off within the window, soonest first."""
    selected: list[tuple[datetime, Mapping[str, object], int]] = []
    for event in events:
        try:
            kickoff = datetime.fromisoformat(str(event.get("commence_time") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if kickoff.tzinfo is None or not now < kickoff <= now + timedelta(hours=hours_ahead):
            continue
        matched = match_scheduled_game(event, games)
        if matched is not None:
            selected.append((kickoff, event, matched[0]))
    selected.sort(key=lambda item: item[0])
    return [(event, game_id) for _, event, game_id in selected]


def can_afford(remaining: int | None, cost: int, min_credits: int) -> bool:
    """An unknown balance is treated as unaffordable, never as plenty."""
    return remaining is not None and remaining - cost >= min_credits


def resolve_book_player(
    name: str, team_codes: tuple[str, str], candidate_index: Mapping[str, list[PlayerCandidate]], aliases: Mapping[str, int],
) -> ResolutionResult:
    """Books give no team per player, so a team only breaks a same-name tie."""
    result = resolve_player(name, None, None, candidate_index, aliases)
    if result.reason is not Resolution.AMBIGUOUS:
        return result
    by_team = [resolve_player(name, team, None, candidate_index, aliases) for team in team_codes]
    matched = [item for item in by_team if item.matched]
    return matched[0] if len(matched) == 1 else result


async def _get(client: httpx.AsyncClient, path: str, params: dict[str, str]) -> tuple[object, int | None]:
    response = await client.get(f"{BASE_URL}/sports/{DEFAULT_SPORT}{path}", params=params, timeout=30)
    response.raise_for_status()
    return response.json(), _remaining_requests(response.headers)


async def run(
    hours_ahead: int = DEFAULT_HOURS_AHEAD, min_credits: int = DEFAULT_MIN_CREDITS,
    max_events: int = DEFAULT_MAX_EVENTS, confirm_spend: bool = False, dry_run: bool = False,
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    cost = len(PROP_MARKETS) * len(REGIONS.split(","))
    api_key = _provider_key()
    async with SessionLocal() as db, httpx.AsyncClient() as client:
        games = await nfl_repo.get_upcoming_games(db, max(1, hours_ahead // 24 + 1))
        events, remaining = await _get(client, "/events", {"apiKey": api_key})
        selected = select_events(events if isinstance(events, list) else [], games, datetime.now(timezone.utc), hours_ahead)[:max_events]
        logger.info("%d events selected, estimated cost %d credits, %s credits remaining", len(selected), len(selected) * cost, remaining)
        if not confirm_spend:
            logger.warning("no credits spent: pass --confirm-spend to fetch prices")
            return dict(counts)

        candidate_index = index_candidates([PlayerCandidate(*row) for row in await nfl_repo.get_player_candidates(db)])
        aliases = await sport_props.get_player_aliases(db, NFL_PROPS.code)
        team_codes = {int(game["game_id"]): (str(game["home_team"]), str(game["away_team"])) for game in games}
        outcomes: Counter[str] = Counter()
        for event, game_id in selected:
            if not can_afford(remaining, cost, min_credits):
                logger.warning("stopping: %s credits remaining, floor is %d", remaining, min_credits)
                counts["stopped_at_floor"] = 1
                break
            try:
                payload, remaining = await _get(client, f"/events/{event['id']}/odds", {
                    "apiKey": api_key, "regions": REGIONS, "markets": ",".join(PROP_MARKETS), "oddsFormat": "american",
                })
            except httpx.HTTPError as exc:
                # Never retry a paid request; a retry loop is how a free quota disappears.
                logger.warning("event %s failed without retry: %s", event.get("id"), exc)
                counts["failed"] += 1
                continue
            counts["events"] += 1
            bookmakers = payload.get("bookmakers") if isinstance(payload, dict) else None
            for price in parse_yes_no_props(bookmakers, list(PROP_MARKETS)):
                resolution = resolve_book_player(price.player_name, team_codes[game_id], candidate_index, aliases)
                outcomes[resolution.reason] += 1
                if not dry_run:
                    await nfl_repo.insert_player_prop_odds_snapshot(
                        db, game_id, resolution.player_id, price.player_name, str(event["id"]),
                        PROP_MARKETS[price.market_key].value, price.book, None, price.yes_odds, price.no_odds,
                        price.market_prob, price.includes_margin, price.raw_market,
                    )
                counts["prices"] += 1
        if not dry_run:
            await db.commit()
    logger.info("prop odds: events=%d prices=%d failed=%d dry_run=%s credits remaining=%s",
                counts["events"], counts["prices"], counts["failed"], dry_run, remaining)
    for reason, count in outcomes.most_common():
        logger.info("  %-18s %4d", reason, count)
    return dict(counts)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Ingest NFL sportsbook player-prop prices from The Odds API")
    parser.add_argument("--hours-ahead", type=int, default=DEFAULT_HOURS_AHEAD)
    parser.add_argument("--min-credits", type=int, default=DEFAULT_MIN_CREDITS)
    parser.add_argument("--max-events", type=int, default=DEFAULT_MAX_EVENTS)
    parser.add_argument("--confirm-spend", action="store_true", help="required before any request that costs credits")
    parser.add_argument("--dry-run", action="store_true", help="fetch (if --confirm-spend) but write nothing")
    args = parser.parse_args()
    await run(args.hours_ahead, args.min_credits, args.max_events, args.confirm_spend, args.dry_run)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
