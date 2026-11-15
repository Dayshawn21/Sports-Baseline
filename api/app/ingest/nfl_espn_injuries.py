"""Store ESPN's current NFL injury statuses for the current week (display only).

ESPN athletes map to our players through the `espn_id` column of the nflverse
weekly roster file, never by name. A failed or empty fetch leaves the stored
week as it was.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timezone

import httpx
from sqlalchemy.exc import SQLAlchemyError
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.nfl_espn_injuries import EspnNflInjury, parse_injury_feed
from app.ingest.nflverse import SeasonNotPublished, current_nfl_season, get_release_asset
from app.ingest.nflverse_rosters import weekly_rosters_url

ESPN_NFL_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"


@dataclass(frozen=True)
class EspnInjuryIngestSummary:
    season: int | None
    week: int | None
    teams: int
    entries: int
    mapped: int
    stored: int | None
    replaced: int | None

    def __str__(self) -> str:
        where = f"season {self.season} week {self.week}" if self.week is not None else "no current week"
        result = "dry run" if self.stored is None else f"{self.replaced} replaced, {self.stored} stored"
        return (
            f"ESPN NFL injuries for {where}: {self.teams} teams, {self.entries} statused entries, "
            f"{self.mapped} mapped to a gsis id, {self.entries - self.mapped} unmapped; {result}"
        )


def parse_espn_gsis_map(lines: Iterable[str]) -> dict[str, str]:
    """ESPN athlete id to gsis id from the nflverse weekly roster CSV; the latest row wins."""
    mapping: dict[str, str] = {}
    for row in csv.DictReader(lines):
        espn_id, gsis_id = (row.get("espn_id") or "").strip(), (row.get("gsis_id") or "").strip()
        if espn_id and espn_id != "NA" and gsis_id and gsis_id != "NA":
            mapping[espn_id.removesuffix(".0")] = gsis_id
    return mapping


def link_entries(entries: list[EspnNflInjury], gsis_by_espn: dict[str, str]) -> list[tuple[str, EspnNflInjury]]:
    return [(gsis_by_espn[e.espn_athlete_id], e) for e in entries if e.espn_athlete_id in gsis_by_espn]


def _retryable(exc: BaseException) -> bool:
    return isinstance(exc, httpx.TransportError) or (
        isinstance(exc, httpx.HTTPStatusError)
        and (exc.response.status_code == 429 or exc.response.status_code >= 500)
    )


async def fetch_feed(client: httpx.AsyncClient) -> tuple[int, list[EspnNflInjury]]:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10),
        retry=retry_if_exception(_retryable), reraise=True,
    ):
        with attempt:
            response = await client.get(ESPN_NFL_INJURIES_URL, timeout=30)
            response.raise_for_status()
            return parse_injury_feed(response.json())
    raise RuntimeError("unreachable")


async def fetch_gsis_map(client: httpx.AsyncClient, season: int) -> dict[str, str]:
    response = await get_release_asset(client, weekly_rosters_url(season), timeout=120)
    if response.status_code == 404:
        raise SeasonNotPublished(season, "weekly rosters")
    response.raise_for_status()
    return parse_espn_gsis_map(response.text.splitlines())


async def run(dry_run: bool = False) -> EspnInjuryIngestSummary:
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    fetched_at = datetime.now(timezone.utc)
    async with httpx.AsyncClient(follow_redirects=True) as client:
        teams, entries = await fetch_feed(client)
        gsis_by_espn = await fetch_gsis_map(client, current_nfl_season(date.today()))
    if teams == 0:
        raise ValueError("ESPN returned no injury groups; keeping the stored week")
    linked = link_entries(entries, gsis_by_espn)
    async with SessionLocal() as db:
        current = await nfl_repo.get_current_week(db, fetched_at)
        season, week = current if current is not None else (None, None)
        summary = EspnInjuryIngestSummary(season, week, teams, len(entries), len(linked), None, None)
        if dry_run or season is None or week is None:
            return summary
        try:
            replaced, stored = await nfl_repo.replace_espn_injuries(db, season, week, linked, fetched_at)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return EspnInjuryIngestSummary(season, week, teams, len(entries), len(linked), stored, replaced)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Store ESPN's current NFL injury statuses")
    parser.add_argument("--dry-run", action="store_true", help="fetch and map without writing")
    args = parser.parse_args()
    try:
        print(await run(args.dry_run))
    except (httpx.HTTPError, ValueError, SQLAlchemyError, SeasonNotPublished) as exc:
        print(f"ESPN NFL injury ingest failed ({type(exc).__name__}: {exc})", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
