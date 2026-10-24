"""Snapshot independent ESPN NHL injury and starting-goalie feeds for display."""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from time import monotonic

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nhl_context import EASTERN, NhlGoalieFeed, NhlInjuryFeed, parse_goalie_feed, parse_injury_feed
from app.core.nhl_context_resolution import (
    index_context_players, resolve_context_event, resolve_context_goalie, resolve_context_injury,
)
from app.repositories import nhl_context as repo

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl"
MAX_RETRY_WAIT = 30
FETCH_DEADLINE = 90


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FetchFailure(Exception):
    """Only safe category strings belong here; never include upstream bodies."""


def retry_after_seconds(value: str, now: datetime) -> float:
    try:
        if value.strip().isdigit():
            return float(value.strip())
        parsed = parsedate_to_datetime(value)
        if parsed.utcoffset() is None:
            raise ValueError("naive Retry-After")
        return max(0.0, (parsed - now).total_seconds())
    except (ValueError, TypeError, OverflowError) as exc:
        raise FetchFailure("invalid_retry_after") from exc


class EspnContextFetcher:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client
        self.cooldown_until = 0.0
        self.blocked = False

    async def _wait(self) -> None:
        if self.blocked:
            raise FetchFailure("provider_cooldown")
        remaining = self.cooldown_until - monotonic()
        if remaining > 0:
            await asyncio.sleep(remaining)
            self.cooldown_until = 0.0

    def _cooldown(self, response: httpx.Response) -> None:
        header = response.headers.get("Retry-After")
        if header is None:
            return
        try:
            delay = retry_after_seconds(header, _now())
        except FetchFailure:
            self.blocked = True
            raise
        if delay > MAX_RETRY_WAIT:
            self.blocked = True
            raise FetchFailure("retry_after_exceeds_bound")
        self.cooldown_until = monotonic() + delay

    async def get(self, path: str, params: dict[str, str] | None = None) -> tuple[object, datetime]:
        try:
            async with asyncio.timeout(FETCH_DEADLINE):
                return await self._get(path, params)
        except TimeoutError as exc:
            raise FetchFailure("fetch_deadline") from exc

    async def _get(self, path: str, params: dict[str, str] | None) -> tuple[object, datetime]:
        for attempt in range(3):
            await self._wait()
            try:
                async with asyncio.timeout(32):
                    response = await self.client.get(f"{BASE_URL}/{path}", params=params, timeout=30)
                fetched_at = _now()
            except (httpx.TransportError, TimeoutError) as exc:
                if attempt == 2:
                    raise FetchFailure("transport_error") from exc
                await asyncio.sleep(2 ** attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                self._cooldown(response)
                if attempt == 2:
                    raise FetchFailure(f"http_{response.status_code}")
                if "Retry-After" not in response.headers:
                    await asyncio.sleep(2 ** attempt)
                continue
            if not response.is_success:
                raise FetchFailure(f"http_{response.status_code}")
            return response.json(), fetched_at
        raise RuntimeError("unreachable")


@dataclass(frozen=True)
class ComponentSummary:
    kind: str
    scope_date: date | None
    fetched_at: datetime | None = None
    entries: int = 0
    linked_players: int = 0
    unresolved_ids: tuple[str, ...] = ()
    team_mismatches: int = 0
    unmatched_events: tuple[str, ...] = ()
    snapshot_id: int | None = None
    error: str | None = None

    def __str__(self) -> str:
        label = f"ESPN NHL {self.kind}" + (f" {self.scope_date}" if self.scope_date else " (current)")
        if self.error:
            return f"{label}: failed ({self.error})"
        action = f"stored snapshot {self.snapshot_id}" if self.snapshot_id is not None else "dry run"
        return (f"{label} {action}: {self.entries} entries, {self.linked_players} linked entries, "
                f"{len(self.unresolved_ids)} unresolved athlete IDs, {self.team_mismatches} team mismatches, "
                f"{len(self.unmatched_events)} unmatched events; fetched {self.fetched_at.isoformat()}"
                f"; unresolved={','.join(self.unresolved_ids) or '-'}"
                f"; unmatched={','.join(self.unmatched_events) or '-'}")


async def ingest_injuries(
    db: AsyncSession, feed: NhlInjuryFeed, fetched_at: datetime, dry_run: bool,
) -> ComponentSummary:
    candidates = index_context_players(await repo.get_context_players(db))
    links = {(row.espn_team_id, row.espn_athlete_id): resolve_context_injury(row, candidates)
             for row in feed.injuries}
    snapshot = None
    if not dry_run:
        try:
            snapshot = await repo.store_injury_snapshot(db, feed, fetched_at, links)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return ComponentSummary(
        "injuries", None, fetched_at, len(feed.injuries),
        sum(link.player_id is not None for link in links.values()),
        tuple(sorted({key[1] for key, link in links.items() if link.player_id is None})),
        sum(row.team_mismatch for row in feed.injuries), snapshot_id=snapshot,
    )


async def ingest_goalies(
    db: AsyncSession, feed: NhlGoalieFeed, fetched_at: datetime, dry_run: bool,
) -> ComponentSummary:
    candidates = index_context_players(await repo.get_context_players(db))
    games = await repo.get_context_games(db, feed.scope_date)
    links = {(row.espn_event_id, row.espn_team_id): resolve_context_goalie(row, candidates)
             for row in feed.observations}
    event_links = {row.espn_event_id: resolve_context_event(
        row.away_team, row.home_team, row.start_utc, games, time_valid=row.time_valid,
    ) for row in feed.observations}
    snapshot = None
    if not dry_run:
        try:
            snapshot = await repo.store_goalie_snapshot(db, feed, fetched_at, links, event_links)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return ComponentSummary(
        "goalies", feed.scope_date, fetched_at, len(feed.observations),
        sum(link.player_id is not None for link in links.values()),
        tuple(sorted({row.espn_athlete_id for row in feed.observations if row.espn_athlete_id is not None
                      and links[(row.espn_event_id, row.espn_team_id)].player_id is None})),
        sum(row.team_mismatch for row in feed.observations),
        tuple(sorted(key for key, link in event_links.items() if link.game_id is None)), snapshot,
    )


def selected_dates(now: datetime, explicit: date | None = None) -> tuple[date, ...]:
    if now.utcoffset() is None:
        raise ValueError("NHL context clock must be timezone-aware")
    today = now.astimezone(EASTERN).date()
    return (explicit,) if explicit is not None else (today, today + timedelta(days=1))


async def _component(
    fetcher: EspnContextFetcher, session_factory: Callable[[], AsyncSession],
    scope_date: date | None, dry_run: bool,
) -> ComponentSummary:
    params = {"dates": scope_date.strftime("%Y%m%d"), "limit": "100"} if scope_date else None
    payload, fetched = await fetcher.get("scoreboard" if scope_date else "injuries", params)
    feed = parse_goalie_feed(payload, scope_date) if scope_date else parse_injury_feed(payload)
    async with asyncio.timeout(30):
        async with session_factory() as db:
            if dry_run:
                await repo.prepare_dry_run(db)
            if isinstance(feed, NhlInjuryFeed):
                return await ingest_injuries(db, feed, fetched, dry_run)
            return await ingest_goalies(db, feed, fetched, dry_run)


async def run_components(
    fetcher: EspnContextFetcher, session_factory: Callable[[], AsyncSession],
    dates: tuple[date, ...], dry_run: bool,
) -> tuple[ComponentSummary, ...]:
    summaries = []
    for scope in (None, *dates):
        try:
            summaries.append(await _component(fetcher, session_factory, scope, dry_run))
        except Exception as exc:
            if isinstance(exc, FetchFailure):
                category = str(exc)
            elif isinstance(exc, SQLAlchemyError):
                category = "database_error"
            elif isinstance(exc, ValueError):
                category = "invalid_feed_or_links"
            else:
                category = "database_deadline" if isinstance(exc, TimeoutError) else "internal_error"
            summaries.append(ComponentSummary("goalies" if scope else "injuries", scope, error=category))
    return tuple(summaries)


async def run(dry_run: bool = False, scope_date: date | None = None) -> tuple[ComponentSummary, ...]:
    from app.db.pool import SessionLocal

    async with httpx.AsyncClient(follow_redirects=True) as client:
        return await run_components(EspnContextFetcher(client), SessionLocal, selected_dates(_now(), scope_date), dry_run)


def _date_argument(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError("noncanonical date")
        return parsed
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must be YYYY-MM-DD") from exc


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot current NHL injuries and dated goalie reports")
    parser.add_argument("--dry-run", action="store_true", help="fetch and check links in read-only transactions")
    parser.add_argument("--date", type=_date_argument, help="one goalie scoreboard date; injuries remain current")
    args = parser.parse_args()
    try:
        summaries = await run(args.dry_run, args.date)
    except Exception:
        print("ESPN NHL context failed (configuration_or_initialization)", file=sys.stderr)
        raise SystemExit(1) from None
    for summary in summaries:
        print(summary, file=sys.stderr if summary.error else sys.stdout)
    if any(summary.error for summary in summaries):
        raise SystemExit(1)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
