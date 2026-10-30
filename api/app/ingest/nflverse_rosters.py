"""NFLverse weekly rosters: each player's team and roster status per week.

The current season's file is republished during the week, often before that
week's stats exist, so it is the freshest source for a player's upcoming team.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

import httpx

from app.ingest.nflverse import (
    NFLVERSE_RELEASE_BASE,
    SeasonNotPublished,
    current_nfl_season,
    franchise_code,
    get_release_asset,
)


@dataclass(frozen=True)
class NflverseRosterWeek:
    player_id: str
    season: int
    week: int
    team: str
    status: str


def _week(value: str | None) -> int | None:
    try:
        return int(value or "")
    except ValueError:
        return None


def parse_weekly_rosters(lines: Iterable[str], season: int) -> list[NflverseRosterWeek]:
    """Regular-season roster rows for `season`, one per player per week.

    A player listed twice in one week keeps the later row: the file is appended
    as transactions happen, so the later entry is the more current one.
    """
    by_player_week: dict[tuple[str, int], NflverseRosterWeek] = {}
    for row in csv.DictReader(lines):
        if row.get("season") != str(season) or row.get("game_type") != "REG":
            continue
        player_id, team, week = row.get("gsis_id"), row.get("team"), _week(row.get("week"))
        if not player_id or not team or week is None:
            continue
        by_player_week[(player_id, week)] = NflverseRosterWeek(
            player_id=player_id, season=season, week=week, team=franchise_code(team), status=row.get("status") or "",
        )
    return list(by_player_week.values())


def weekly_rosters_url(season: int) -> str:
    return f"{NFLVERSE_RELEASE_BASE}/weekly_rosters/roster_weekly_{season}.csv"


async def fetch_weekly_rosters(client: httpx.AsyncClient, season: int) -> list[NflverseRosterWeek]:
    response = await get_release_asset(client, weekly_rosters_url(season), timeout=120)
    if response.status_code == 404:
        raise SeasonNotPublished(season, "weekly rosters")
    response.raise_for_status()
    return parse_weekly_rosters(response.text.splitlines(), season)


async def run(season: int, dry_run: bool = False) -> str:
    """Fetch and parse the whole season, then replace its weeks in one transaction."""
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    async with httpx.AsyncClient(follow_redirects=True) as client:
        rosters = await fetch_weekly_rosters(client, season)
    weeks = sorted({item.week for item in rosters})
    parsed = f"{len(rosters)} roster rows for weeks {weeks[0]}-{weeks[-1]}" if weeks else "no roster rows"
    if dry_run:
        return f"NFLverse weekly rosters would load {parsed} of season {season}"
    async with SessionLocal() as db:
        try:
            result = await nfl_repo.replace_weekly_rosters(db, season, rosters)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return (
        f"NFLverse weekly rosters loaded {parsed} of season {season}: "
        f"{result.rows_deleted} replaced, {result.rows_inserted} stored, "
        f"{result.rows_skipped} skipped (player or team not stored)"
        + (f", unknown teams {result.unknown_teams}" if result.unknown_teams else "")
    )


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Load NFLverse weekly rosters (team and status per player-week)")
    parser.add_argument(
        "--season", type=int, default=None,
        help="season to load; defaults to the season in progress, so a scheduled run needs no year",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    season = args.season if args.season is not None else current_nfl_season(date.today())
    try:
        print(await run(season, args.dry_run))
    except SeasonNotPublished as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
