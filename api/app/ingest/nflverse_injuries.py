"""NFLverse weekly injury reports: game status and practice participation per player.

A player absent from a week's file is not on that report (or it is not published
yet); absence is never stored as a "healthy" status.
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

from app.ingest.nflverse import NFLVERSE_RELEASE_BASE, SeasonNotPublished, current_nfl_season, get_release_asset


@dataclass(frozen=True)
class NflverseInjuryWeek:
    player_id: str
    season: int
    week: int
    team: str
    # Out, Doubtful, or Questionable; None when the player is on the practice report only.
    report_status: str | None
    practice_status: str | None
    primary_injury: str | None


def _text(value: str | None) -> str | None:
    value = (value or "").strip()
    return value if value and value.upper() != "NA" else None


def _week(value: str | None) -> int | None:
    try:
        return int(value or "")
    except ValueError:
        return None


def parse_injuries(lines: Iterable[str], season: int) -> list[NflverseInjuryWeek]:
    """Regular-season injury rows for `season`, one per player per week.

    Filters on `game_type` because older files (2024) have no `season_type`.
    """
    by_player_week: dict[tuple[str, int], NflverseInjuryWeek] = {}
    for row in csv.DictReader(lines):
        if row.get("season") != str(season) or row.get("game_type") != "REG":
            continue
        player_id, team, week = _text(row.get("gsis_id")), _text(row.get("team")), _week(row.get("week"))
        if player_id is None or team is None or week is None:
            continue
        by_player_week[(player_id, week)] = NflverseInjuryWeek(
            player_id=player_id, season=season, week=week, team=team,
            report_status=_text(row.get("report_status")),
            practice_status=_text(row.get("practice_status")),
            # The game report names the injury that matters for availability; a
            # practice-only row (often "resting player") still explains a DNP.
            primary_injury=_text(row.get("report_primary_injury")) or _text(row.get("practice_primary_injury")),
        )
    return list(by_player_week.values())


def injuries_url(season: int) -> str:
    return f"{NFLVERSE_RELEASE_BASE}/injuries/injuries_{season}.csv"


async def fetch_injuries(client: httpx.AsyncClient, season: int) -> list[NflverseInjuryWeek]:
    response = await get_release_asset(client, injuries_url(season), timeout=120)
    if response.status_code == 404:
        raise SeasonNotPublished(season, "injury reports")
    response.raise_for_status()
    return parse_injuries(response.text.splitlines(), season)


async def run(season: int, dry_run: bool = False) -> str:
    """Fetch and parse the whole season, then replace its weeks in one transaction."""
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    async with httpx.AsyncClient(follow_redirects=True) as client:
        injuries = await fetch_injuries(client, season)
    weeks = sorted({item.week for item in injuries})
    parsed = f"{len(injuries)} injury rows for weeks {weeks[0]}-{weeks[-1]}" if weeks else "no injury rows"
    if dry_run:
        return f"NFLverse injuries would load {parsed} of season {season}"
    async with SessionLocal() as db:
        try:
            result = await nfl_repo.replace_weekly_injuries(db, season, injuries)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return (
        f"NFLverse injuries loaded {parsed} of season {season}: "
        f"{result.rows_deleted} replaced, {result.rows_inserted} stored, "
        f"{result.rows_skipped} skipped (player or team not stored)"
        + (f", unknown teams {result.unknown_teams}" if result.unknown_teams else "")
    )


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Load NFLverse weekly injury reports")
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
