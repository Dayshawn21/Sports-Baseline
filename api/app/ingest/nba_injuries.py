"""Snapshot ESPN NBA injury reports; display context only (42c)."""
from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.nba_injuries import NbaInjuryFeed, parse_injury_feed
from app.repositories import nba_injuries as repo

ESPN_NBA_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"


@dataclass(frozen=True)
class InjuryIngestSummary:
    fetched_at: datetime
    teams: int
    entries: int
    unresolved_ids: tuple[str, ...]
    team_mismatches: int
    snapshot_id: int | None
    dry_run: bool

    def __str__(self) -> str:
        action = "dry run" if self.dry_run else f"stored snapshot {self.snapshot_id}"
        return (
            f"ESPN NBA injuries {action}: {self.teams} teams with reports, {self.entries} entries, "
            f"{len(self.unresolved_ids)} unresolved athlete IDs, {self.team_mismatches} team mismatches; "
            f"fetched {self.fetched_at.isoformat()}"
        )


def _retryable(exc: BaseException) -> bool:
    return isinstance(exc, httpx.TransportError) or (
        isinstance(exc, httpx.HTTPStatusError)
        and (exc.response.status_code == 429 or exc.response.status_code >= 500)
    )


async def fetch_injuries(client: httpx.AsyncClient) -> NbaInjuryFeed:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10),
        retry=retry_if_exception(_retryable), reraise=True,
    ):
        with attempt:
            response = await client.get(ESPN_NBA_INJURIES_URL, timeout=30)
            response.raise_for_status()
            return parse_injury_feed(response.json())
    raise RuntimeError("unreachable")


async def ingest_feed(
    db: AsyncSession, feed: NbaInjuryFeed, fetched_at: datetime, dry_run: bool = False,
) -> InjuryIngestSummary:
    """Resolve for reporting only; commit the batch and entries together."""
    try:
        unresolved = await repo.unresolved_athletes(db, feed)
        snapshot_id = None if dry_run else await repo.store_snapshot(db, feed, fetched_at)
        if not dry_run:
            await db.commit()
    except Exception:
        await db.rollback()
        raise
    return InjuryIngestSummary(
        fetched_at=fetched_at, teams=len({row.espn_team_id for row in feed.injuries}),
        entries=len(feed.injuries), unresolved_ids=unresolved,
        team_mismatches=sum(row.team_mismatch for row in feed.injuries),
        snapshot_id=snapshot_id, dry_run=dry_run,
    )


async def run(dry_run: bool = False) -> InjuryIngestSummary:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        feed = await fetch_injuries(client)
    fetched_at = datetime.now(timezone.utc)
    from app.db.pool import SessionLocal

    async with SessionLocal() as db:
        return await ingest_feed(db, feed, fetched_at, dry_run)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot ESPN NBA injuries for display")
    parser.add_argument("--dry-run", action="store_true", help="fetch and check player IDs without writing")
    args = parser.parse_args()
    try:
        print(await run(args.dry_run))
    except (httpx.HTTPError, ValueError, SQLAlchemyError) as exc:
        print(f"ESPN NBA injury ingest failed ({type(exc).__name__})", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
