"""NFLverse depth charts reduced to one pre-game order per team-week.

The source is a daily ESPN snapshot (twice a day in season) since March, about
50 MB a season. A week's depth order is the latest snapshot taken on or before
that team's game day; snapshots land around 06:00 and 12:00 UTC, before any
kickoff, so a game-day snapshot still describes the pre-game chart.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import io
import sys
import tempfile
from bisect import bisect_left
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

import httpx

from app.ingest.nflverse import NFLVERSE_RELEASE_BASE, SeasonNotPublished, current_nfl_season, retry_release_download

SKILL_POSITIONS = frozenset({"QB", "RB", "WR", "TE"})


@dataclass(frozen=True)
class NflverseDepthWeek:
    player_id: str
    season: int
    week: int
    team: str
    position: str
    depth_rank: int
    snapshot_at: datetime


@dataclass
class _TeamWeek:
    snapshot_at: datetime
    # gsis id -> (position, rank); a player listed twice keeps the better rank.
    players: dict[str, tuple[str, int]]


def _snapshot_time(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def _rank(value: str | None) -> int | None:
    try:
        return int(value or "")
    except ValueError:
        return None


def _game_week(schedule: Sequence[tuple[int, date]], snapshot_day: date) -> int | None:
    """The week of the team's first game on or after the snapshot's day."""
    index = bisect_left([game_day for _, game_day in schedule], snapshot_day)
    return schedule[index][0] if index < len(schedule) else None


def reduce_depth_charts(
    lines: Iterable[str],
    season: int,
    schedule: Mapping[str, Sequence[tuple[int, date]]],
) -> list[NflverseDepthWeek]:
    """One skill-position depth row per player per team-week, from its pre-game snapshot.

    `schedule` maps team code to its (week, game date) pairs sorted by date. Rows
    after a team's last scheduled game, for unscheduled teams, outside QB/RB/WR/TE,
    or without an id or rank are dropped.
    """
    best: dict[tuple[str, int], _TeamWeek] = {}
    for row in csv.DictReader(lines):
        position, team, player_id = row.get("pos_abb"), row.get("team") or "", row.get("gsis_id")
        snapshot_at, rank = _snapshot_time(row.get("dt")), _rank(row.get("pos_rank"))
        if position not in SKILL_POSITIONS or not player_id or snapshot_at is None or rank is None:
            continue
        week = _game_week(schedule.get(team, ()), snapshot_at.date())
        if week is None:
            continue
        current = best.get((team, week))
        if current is None or snapshot_at > current.snapshot_at:
            current = best[(team, week)] = _TeamWeek(snapshot_at, {})
        elif snapshot_at < current.snapshot_at:
            continue
        listed = current.players.get(player_id)
        if listed is None or rank < listed[1]:
            current.players[player_id] = (position, rank)
    return [
        NflverseDepthWeek(player_id, season, week, team, position, rank, team_week.snapshot_at)
        for (team, week), team_week in sorted(best.items())
        for player_id, (position, rank) in team_week.players.items()
    ]


def depth_charts_url(season: int) -> str:
    return f"{NFLVERSE_RELEASE_BASE}/depth_charts/depth_charts_{season}.csv"


async def fetch_depth_charts(
    client: httpx.AsyncClient, season: int, schedule: Mapping[str, Sequence[tuple[int, date]]],
) -> list[NflverseDepthWeek]:
    """Stream the season file to disk, then reduce it a line at a time."""
    url = depth_charts_url(season)
    with tempfile.TemporaryFile() as spool:

        async def download() -> httpx.Response:
            # A failed attempt may have spooled part of a body; never parse it.
            spool.seek(0)
            spool.truncate()
            async with client.stream("GET", url, timeout=300) as response:
                if response.is_success:
                    async for chunk in response.aiter_bytes():
                        spool.write(chunk)
                return response

        response = await retry_release_download(url, download)
        if response.status_code == 404:
            raise SeasonNotPublished(season, "depth charts")
        response.raise_for_status()
        spool.seek(0)
        return reduce_depth_charts(io.TextIOWrapper(spool, encoding="utf-8", newline=""), season, schedule)


async def run(season: int, dry_run: bool = False) -> str:
    """Reduce the whole season against the stored schedule, then replace its weeks in one transaction."""
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    async with SessionLocal() as db:
        schedule = await nfl_repo.get_team_schedule(db, season)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            depth = await fetch_depth_charts(client, season, schedule)
        weeks = sorted({item.week for item in depth})
        parsed = f"{len(depth)} depth rows for weeks {weeks[0]}-{weeks[-1]}" if weeks else "no depth rows"
        if dry_run:
            return f"NFLverse depth charts would load {parsed} of season {season}"
        try:
            result = await nfl_repo.replace_weekly_depth_charts(db, season, depth)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return (
        f"NFLverse depth charts loaded {parsed} of season {season}: "
        f"{result.rows_deleted} replaced, {result.rows_inserted} stored, "
        f"{result.rows_skipped} skipped (player or team not stored)"
        + (f", unknown teams {result.unknown_teams}" if result.unknown_teams else "")
    )


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Load NFLverse pre-game depth charts (QB/RB/WR/TE)")
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
