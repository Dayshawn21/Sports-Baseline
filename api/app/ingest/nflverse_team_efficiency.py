"""NFLverse play-by-play reduced to one offensive efficiency row per team per game.

Stores sums (plays, EPA, successful plays) rather than rates, so any later
window or season aggregates exactly. Raw plays are never stored.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import gzip
import io
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

import httpx

from app.ingest.nflverse import SeasonNotPublished, current_nfl_season, get_release_asset
from app.ingest.nflverse_pbp import play_by_play_url

# Sacks and scrambles arrive as `pass`. Kneels, spikes, special teams, and
# penalty-nullified snaps (`no_play`) all carry other play types.
EFFICIENCY_PLAY_TYPES = frozenset({"run", "pass"})


@dataclass(frozen=True)
class NflverseTeamEfficiency:
    game_id: str
    # The side comes from the play row's own home and away teams, so historical
    # codes (STL, SD, OAK) never need mapping to stored teams.
    is_home: bool
    plays: int
    epa: float
    successes: int


def _epa(row: dict[str, str]) -> float | None:
    try:
        return float(row.get("epa") or "")
    except ValueError:
        return None


def _offense_side(row: dict[str, str]) -> bool | None:
    """True for the home offense, False for the away offense, None when unknowable."""
    offense = row.get("posteam")
    if not offense:
        return None
    if offense == row.get("home_team"):
        return True
    if offense == row.get("away_team"):
        return False
    return None


def parse_team_efficiency(lines: Iterable[str], season: int) -> list[NflverseTeamEfficiency]:
    """Sum regular-season run and pass plays per (game, offense).

    Success is `epa > 0`, NFLverse's own definition, computed here so a blank
    `success` column cannot disagree with the EPA that was counted.
    """
    totals: dict[tuple[str, bool], list[float]] = {}
    for row in csv.DictReader(lines):
        if row.get("season") != str(season) or row.get("season_type") != "REG" or not row.get("game_id"):
            continue
        if row.get("play_type") not in EFFICIENCY_PLAY_TYPES or row.get("two_point_attempt") == "1":
            continue
        is_home = _offense_side(row)
        epa = _epa(row)
        if is_home is None or epa is None:
            continue
        tally = totals.setdefault((row["game_id"], is_home), [0, 0.0, 0])
        tally[0] += 1
        tally[1] += epa
        tally[2] += epa > 0
    return [
        NflverseTeamEfficiency(game_id, is_home, int(plays), epa, int(successes))
        for (game_id, is_home), (plays, epa, successes) in totals.items()
    ]


async def fetch_team_efficiency(client: httpx.AsyncClient, season: int) -> list[NflverseTeamEfficiency]:
    """Download one season and parse it while decompressing, as the red-zone ingest does."""
    response = await get_release_asset(client, play_by_play_url(season), timeout=120)
    if response.status_code == 404:
        raise SeasonNotPublished(season, "play-by-play")
    response.raise_for_status()
    with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as archive:
        return parse_team_efficiency(io.TextIOWrapper(archive, encoding="utf-8", newline=""), season)


async def run(seasons: range, dry_run: bool = False) -> list[str]:
    """Load each season in its own transaction, so a failed season keeps the ones before it."""
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    messages: list[str] = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for season in seasons:
            rows = await fetch_team_efficiency(client, season)
            parsed = f"{len(rows)} team-games from {len({row.game_id for row in rows})} games"
            if dry_run:
                messages.append(f"Team efficiency would load {parsed} for season {season}")
                continue
            async with SessionLocal() as db:
                try:
                    result = await nfl_repo.replace_team_efficiency(db, rows)
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
            messages.append(
                f"Team efficiency parsed {parsed} for season {season}: {result.rows_deleted} deleted, "
                f"{result.rows_inserted} inserted, {result.games_not_final} games not final, "
                f"{result.games_unknown} games not in sport_games"
            )
    return messages


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Load NFLverse per-team, per-game offensive efficiency")
    parser.add_argument(
        "--season", type=int, default=None,
        help="first season to load; defaults to the season in progress, so a scheduled run needs no year",
    )
    parser.add_argument("--through-season", type=int, default=None, help="last season of a backfill range")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    season = args.season if args.season is not None else current_nfl_season(date.today())
    through = args.through_season if args.through_season is not None else season
    try:
        for message in await run(range(season, through + 1), args.dry_run):
            print(message)
    except SeasonNotPublished as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
