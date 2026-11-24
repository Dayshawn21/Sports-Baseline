"""Ingest tennis total-games lines from The Odds API into `match_odds` (item 48b).

Free `/sports` and `/events` calls find the tour-level tennis keys with a stored
upcoming match; each such key then costs one paid `/odds` call (totals for the
preferred books: 1 credit). Challenger and WTA 125 have no keys, so their props
keep `no_market_total`.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import httpx

from app.core.tennis_totals import BOOK_PREFERENCE, TennisTotal, match_stored, preferred_total
from app.db.pool import SessionLocal
from app.ingest.log_config import configure_ingest_logging
from app.ingest.nba_odds import credit_gate
from app.ingest.nfl_odds import BASE_URL, _provider_key, _remaining_requests
from app.ingest.odds_api import _insert_odds, _load_upcoming

logger = logging.getLogger("tennis_totals_ingest")
configure_ingest_logging()

# Above NBA's 100 and NFL's floors, so tennis totals are the first to stop when
# the shared monthly credits run low.
DEFAULT_MIN_CREDITS = 150


@dataclass
class TotalsRun:
    totals: list[tuple[int, TennisTotal]] = field(default_factory=list)
    active_keys: int = 0
    paid_keys: list[str] = field(default_factory=list)
    unmatched: int = 0
    unpriced: int = 0
    stopped_at_floor: bool = False


def _odds_params(api_key: str) -> dict[str, str]:
    # Naming up to ten books costs one region, and returns only the books we rank.
    return {"apiKey": api_key, "bookmakers": ",".join(BOOK_PREFERENCE), "markets": "totals", "oddsFormat": "decimal"}


async def _get(client: httpx.AsyncClient, path: str, params: dict[str, str]) -> tuple[list[dict[str, object]], int | None]:
    response = await client.get(f"{BASE_URL}{path}", params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    rows = [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []
    return rows, _remaining_requests(response.headers)


def _failure(exc: httpx.HTTPError) -> str:
    # An httpx error's text carries the request URL, and the URL carries apiKey.
    return f"HTTP {exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__


async def _keys_with_matches(
    client: httpx.AsyncClient, api_key: str, matches: Sequence[Mapping[str, object]], tally: TotalsRun,
) -> tuple[list[str], int | None]:
    """Active tennis keys with at least one stored match, from free calls only."""
    try:
        sports, remaining = await _get(client, "/sports", {"apiKey": api_key})
    except httpx.HTTPError as exc:
        raise RuntimeError(f"The Odds API /sports listing failed ({_failure(exc)})") from None
    keys = [str(s["key"]) for s in sports if str(s.get("key", "")).startswith("tennis_") and s.get("active")]
    tally.active_keys = len(keys)
    kept: list[str] = []
    for key in keys:
        try:
            events, remaining = await _get(client, f"/sports/{key}/events", {"apiKey": api_key})
        except httpx.HTTPError as exc:
            logger.warning("Skipping %s: events listing failed (%s)", key, _failure(exc))
            continue
        if any(match_stored(event, matches) is not None for event in events):
            kept.append(key)
    return kept, remaining


async def collect_totals(
    client: httpx.AsyncClient, api_key: str, matches: Sequence[Mapping[str, object]], min_credits: int,
) -> TotalsRun:
    """The preferred book's total for every stored match a tour-level key prices."""
    tally = TotalsRun()
    keys, remaining = await _keys_with_matches(client, api_key, matches, tally)
    for key in keys:
        if not credit_gate(remaining, min_credits):
            logger.warning("The Odds API credits remaining %s, below the tennis floor %d: stopping", remaining, min_credits)
            tally.stopped_at_floor = True
            break
        try:
            events, remaining = await _get(client, f"/sports/{key}/odds", _odds_params(api_key))
        except httpx.HTTPError as exc:
            logger.warning("Odds call for %s failed (%s)", key, _failure(exc))
            continue
        tally.paid_keys.append(key)
        for event in events:
            match_id = match_stored(event, matches)
            total = preferred_total(event)
            if match_id is None:
                tally.unmatched += 1
            elif total is None:
                tally.unpriced += 1
            else:
                tally.totals.append((match_id, total))
    logger.info("The Odds API credits remaining after tennis totals: %s", remaining)
    return tally


async def run(hours_ahead: int = 24, min_credits: int = DEFAULT_MIN_CREDITS, dry_run: bool = False) -> TotalsRun:
    async with SessionLocal() as db:
        matches = await _load_upcoming(db, hours_ahead, limit=500)
        if not matches:
            logger.info("No upcoming tennis matches in the next %dh, no provider call made", hours_ahead)
            return TotalsRun()
        async with httpx.AsyncClient() as client:
            result = await collect_totals(client, _provider_key(), matches, min_credits)
        if not dry_run:
            for match_id, total in result.totals:
                await _insert_odds(db, match_id, total.book, "total_games", total.over, total.under, total.line)
            await db.commit()
    logger.info(
        "Tennis totals: matches=%d active_keys=%d paid_keys=%s totals=%d unmatched=%d unpriced=%d floor_stop=%s dry_run=%s",
        len(matches), result.active_keys, ",".join(result.paid_keys) or "-", len(result.totals),
        result.unmatched, result.unpriced, result.stopped_at_floor, dry_run,
    )
    return result


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Ingest tennis total-games lines from The Odds API (1 credit per priced key)")
    parser.add_argument("--hours-ahead", type=int, default=24)
    parser.add_argument("--min-credits", type=int, default=DEFAULT_MIN_CREDITS)
    parser.add_argument("--dry-run", action="store_true", help="still spends the credits; writes nothing")
    args = parser.parse_args()
    await run(args.hours_ahead, args.min_credits, args.dry_run)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
