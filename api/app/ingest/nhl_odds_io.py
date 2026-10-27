"""Bounded NHL Odds-API.io snapshots using the hourly quota shared with tennis/NFL."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.nhl_odds import event_start, match_nhl_game, parse_nhl_game_markets, provider_team_code
from app.db.pool import SessionLocal
from app.ingest.log_config import configure_ingest_logging
from app.repositories import nhl as nhl_repo

logger = logging.getLogger("nhl_odds_io_ingest")
configure_ingest_logging()

BASE_URL = "https://api.odds-api.io/v3"
BOOKMAKERS = {"DraftKings": "draftkings", "FanDuel": "fanduel"}
DEFAULT_DAYS_AHEAD = 2
DEFAULT_MIN_REQUESTS_REMAINING = 20


@dataclass(frozen=True)
class SelectedEvent:
    game_id: int
    homes_agree: bool
    provider_start: datetime
    stored_start: datetime
    home: str
    away: str


class FetchFailure(Exception):
    """Contains only a safe category, never a credential-bearing HTTP error."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _event_id(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    try:
        number = int(value)
    except ValueError:
        return None
    return number if number > 0 else None


def _unique_events(events: Sequence[object], counts: Counter[str]) -> dict[int, Mapping[str, object]]:
    unique: dict[int, Mapping[str, object]] = {}
    conflicts: set[int] = set()
    for event in events:
        event_id = _event_id(event.get("id")) if isinstance(event, Mapping) else None
        if event_id is None:
            counts["malformed_event"] += 1
        elif event_id in unique and unique[event_id] != event:
            conflicts.add(event_id)
        else:
            unique[event_id] = event
    counts["conflicting_event"] += len(conflicts)
    return {key: value for key, value in unique.items() if key not in conflicts}


def select_events(
    events: Sequence[object], games: Sequence[Mapping[str, object]], now: datetime,
) -> tuple[dict[int, SelectedEvent], Counter[str]]:
    counts: Counter[str] = Counter()
    selected: dict[int, SelectedEvent] = {}
    starts = {game["game_id"]: game["start_utc"] for game in games}
    for event_id, event in _unique_events(events, counts).items():
        match = match_nhl_game(event, games)
        start = event_start(event.get("date"))
        if match is None:
            counts["unmatched"] += 1
        elif event.get("status") != "pending":
            counts["not_pending"] += 1
        elif start <= now or starts[match[0]] <= now:
            counts["started"] += 1
        else:
            selected[event_id] = SelectedEvent(
                *match, start, starts[match[0]],
                provider_team_code(event.get("home")), provider_team_code(event.get("away")),
            )
    game_counts = Counter(event.game_id for event in selected.values())
    conflicts = {key for key, event in selected.items() if game_counts[event.game_id] > 1}
    counts["conflicting_game"] += len(conflicts)
    return {key: value for key, value in selected.items() if key not in conflicts}, counts


def _remaining(headers: Mapping[str, str]) -> int | None:
    try:
        value = int(headers.get("x-ratelimit-remaining", ""))
    except ValueError:
        return None
    return value if 0 <= value <= 100 else None


def can_request(remaining: int | None, floor: int) -> bool:
    return remaining is not None and remaining - 1 >= floor


async def _get(client: httpx.AsyncClient, path: str, params: dict[str, str]) -> tuple[list[object], int | None]:
    try:
        response = await client.get(
            f"{BASE_URL}{path}", params={**params, "apiKey": settings.odds_api_key.strip()}, timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise FetchFailure(f"http_{exc.response.status_code}") from None
    except httpx.HTTPError:
        raise FetchFailure("network_error") from None
    except ValueError:
        raise FetchFailure("invalid_json") from None
    if not isinstance(payload, list):
        raise FetchFailure("invalid_payload")
    return payload, _remaining(response.headers)


def _response_agrees(event: Mapping[str, object], selected: SelectedEvent) -> bool:
    for field, expected in (("home", selected.home), ("away", selected.away)):
        if field in event and provider_team_code(event[field]) != expected:
            return False
    if "date" in event and event_start(event["date"]) != selected.provider_start:
        return False
    if "status" in event and event["status"] != "pending":
        return False
    league = event.get("league")
    return "league" not in event or isinstance(league, Mapping) and league.get("slug") == "usa-nhl"


async def _store_batch(
    db: AsyncSession, payload: Sequence[object], selected: Mapping[int, SelectedEvent],
    dry_run: bool, counts: Counter[str],
) -> None:
    events = _unique_events(payload, counts)
    counts["missing_event"] += len(set(selected) - events.keys())
    for event_id, event in events.items():
        match = selected.get(event_id)
        if match is None or not _response_agrees(event, match):
            counts["unrequested_or_changed_event"] += 1
            continue
        books = event.get("bookmakers")
        if not isinstance(books, Mapping):
            counts["malformed_books"] += 1
            continue
        for expected in BOOKMAKERS:
            if expected not in books:
                counts[f"missing_book_{BOOKMAKERS[expected]}"] += 1
        for book, markets in books.items():
            if book not in BOOKMAKERS or not isinstance(markets, list):
                counts["unsupported_or_malformed_book"] += 1
                continue
            parsed = parse_nhl_game_markets(markets, match.homes_agree)
            for missing in {"moneyline", "spread", "total"} - {row.market for row in parsed}:
                counts[f"missing_{BOOKMAKERS[book]}_{missing}"] += 1
            for market in parsed:
                if min(match.provider_start, match.stored_start) <= _now():
                    counts["started_before_write"] += 1
                    continue
                counts["candidates"] += 1
                counts[f"candidate_{BOOKMAKERS[book]}_{market.market}"] += 1
                if not dry_run:
                    row_id = await nhl_repo.insert_game_odds_snapshot(
                        db, match.game_id, BOOKMAKERS[book], market, event_id=event_id,
                    )
                    counts["written" if row_id is not None else "ineligible_at_write"] += 1


async def _refresh(
    db: AsyncSession, games: list[dict[str, object]], floor: int, dry_run: bool, counts: Counter[str],
) -> None:
    async with httpx.AsyncClient() as client:
        counts["requests"] += 1
        events, remaining = await _get(client, "/events", {"sport": "ice-hockey"})
        counts["requests_remaining"] = remaining if remaining is not None else -1
        selected, skips = select_events(events, games, _now())
        counts.update(skips)
        counts["matched"] = len(selected)
        event_ids = sorted(selected, key=lambda key: selected[key].stored_start)
        for offset in range(0, len(event_ids), 10):
            if not can_request(remaining, floor):
                counts["stopped_at_floor"] = 1
                break
            batch = event_ids[offset:offset + 10]
            counts["requests"] += 1
            payload, remaining = await _get(client, "/odds/multi", {
                "eventIds": ",".join(map(str, batch)), "bookmakers": ",".join(BOOKMAKERS),
            })
            counts["requests_remaining"] = remaining if remaining is not None else -1
            await _store_batch(db, payload, {key: selected[key] for key in batch}, dry_run, counts)


async def run(
    days_ahead: int = DEFAULT_DAYS_AHEAD,
    min_requests_remaining: int = DEFAULT_MIN_REQUESTS_REMAINING, dry_run: bool = False,
) -> dict[str, int]:
    if isinstance(days_ahead, bool) or not isinstance(days_ahead, int) or not 1 <= days_ahead <= 14:
        raise ValueError("days_ahead must be an integer from 1 to 14")
    if isinstance(min_requests_remaining, bool) or not isinstance(min_requests_remaining, int) or not 0 <= min_requests_remaining < 100:
        raise ValueError("min_requests_remaining must be an integer from 0 to 99")
    counts: Counter[str] = Counter(requests=0, matched=0, candidates=0, written=0)
    async with SessionLocal() as db:
        games = await nhl_repo.get_upcoming_games(db, days_ahead)
        if games:
            if not settings.odds_api_key.strip():
                raise ValueError("ODDS_API_KEY is required for NHL Odds-API.io ingest")
            try:
                await _refresh(db, games, min_requests_remaining, dry_run, counts)
            except FetchFailure as exc:
                counts["failed"] = 1
                counts["requests_remaining"] = -1
                logger.error("NHL odds stopped without retry: %s", exc)
            if not dry_run and counts["written"]:
                await db.commit()
    logger.info("NHL Odds-API.io ingest: %s dry_run=%s", dict(counts), dry_run)
    return dict(counts)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Ingest NHL DraftKings/FanDuel full-game odds from Odds-API.io")
    parser.add_argument("--days-ahead", type=int, default=DEFAULT_DAYS_AHEAD)
    parser.add_argument("--min-requests-remaining", type=int, default=DEFAULT_MIN_REQUESTS_REMAINING)
    parser.add_argument("--dry-run", action="store_true", help="Fetch and parse hourly-quota data without writes")
    args = parser.parse_args()
    try:
        counts = await run(args.days_ahead, args.min_requests_remaining, args.dry_run)
    except ValueError as exc:
        parser.error(str(exc))
    except SQLAlchemyError:
        logger.error("NHL odds database operation failed")
        raise SystemExit(1) from None
    if counts.get("failed"):
        raise SystemExit(1)
    if counts.get("stopped_at_floor"):
        raise SystemExit(75)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
