"""NFLverse play-by-play reduced to per-player, per-game red-zone opportunities.

Raw plays are never stored: the season file is hundreds of columns wide, and the
anytime-TD model only needs how often a player got the ball near the goal line.
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

from app.ingest.nflverse import NFLVERSE_RELEASE_BASE, SeasonNotPublished, current_nfl_season, get_release_asset

RED_ZONE_YARDS = 20
GOAL_LINE_YARDS = 5
# Kneels and spikes carry rush or pass flags but are never scoring chances, and
# penalty-nullified snaps arrive as `no_play`; filtering on play type drops all three.
OPPORTUNITY_PLAY_TYPES = frozenset({"run", "pass"})


@dataclass(frozen=True)
class NflverseRedZoneGame:
    player_id: str
    game_id: str
    rz20_carries: int
    rz20_targets: int
    rz5_carries: int
    rz5_targets: int
    # Kept alongside the red-zone counts because it comes from the same file and
    # uses the same game-level zeroing contract in the writer.
    end_zone_targets: int = 0
    # The punter's punts (item 34b): same file, same zeroing contract.
    punts: int = 0


def _flag(row: dict[str, str], column: str) -> bool:
    return row.get(column) == "1"


def _yardline(row: dict[str, str]) -> int | None:
    try:
        return int(float(row.get("yardline_100") or ""))
    except ValueError:
        return None


def _opportunity(row: dict[str, str]) -> tuple[str, str] | None:
    """(player id, "carries" | "targets") for a counted play, else None."""
    if row.get("play_type") not in OPPORTUNITY_PLAY_TYPES or _flag(row, "two_point_attempt"):
        return None
    if _flag(row, "rush_attempt") and row.get("rusher_player_id"):
        return row["rusher_player_id"], "carries"
    if _flag(row, "pass_attempt") and not _flag(row, "sack") and row.get("receiver_player_id"):
        return row["receiver_player_id"], "targets"
    return None


def _end_zone_target(row: dict[str, str]) -> str | None:
    """Return the receiver for a target thrown into the end zone, if any."""
    if not _flag(row, "pass_attempt") or _flag(row, "sack"):
        return None
    receiver = row.get("receiver_player_id")
    yardline = _yardline(row)
    try:
        air_yards = float(row.get("air_yards") or "")
    except ValueError:
        return None
    if not receiver or yardline is None or air_yards < yardline:
        return None
    return receiver


@dataclass(frozen=True)
class NflverseRedZoneSeason:
    # Every regular-season game in the file, including any with no red-zone plays,
    # so the writer knows which games to reset to zero.
    game_ids: frozenset[str]
    games: list[NflverseRedZoneGame]


def _empty_tally() -> dict[str, int]:
    return {"rz20_carries": 0, "rz20_targets": 0, "rz5_carries": 0, "rz5_targets": 0, "end_zone_targets": 0, "punts": 0}


def parse_red_zone_usage(lines: Iterable[str], season: int) -> NflverseRedZoneSeason:
    """Count regular-season carries and targets inside the 20 and inside the 5, and punts.

    Inside-5 is a subset of inside-20, not a separate band. Players with no red-zone
    plays or punts produce no entry; the writer turns that absence into a stored zero.
    """
    game_ids: set[str] = set()
    counts: dict[tuple[str, str], dict[str, int]] = {}
    for row in csv.DictReader(lines):
        if row.get("season") != str(season) or row.get("season_type") != "REG" or not row.get("game_id"):
            continue
        game_ids.add(row["game_id"])
        yardline = _yardline(row)
        if yardline is not None and yardline <= RED_ZONE_YARDS:
            opportunity = _opportunity(row)
            if opportunity is not None:
                player_id, kind = opportunity
                tally = counts.setdefault((player_id, row["game_id"]), _empty_tally())
                tally[f"rz20_{kind}"] += 1
                if yardline <= GOAL_LINE_YARDS:
                    tally[f"rz5_{kind}"] += 1
        receiver = _end_zone_target(row)
        if receiver:
            counts.setdefault((receiver, row["game_id"]), _empty_tally())["end_zone_targets"] += 1
        # Only plays typed "punt" carry punt_attempt = 1; a penalty-nullified punt is no_play.
        if _flag(row, "punt_attempt") and row.get("punter_player_id"):
            counts.setdefault((row["punter_player_id"], row["game_id"]), _empty_tally())["punts"] += 1
    return NflverseRedZoneSeason(
        game_ids=frozenset(game_ids),
        games=[
            NflverseRedZoneGame(player_id=player_id, game_id=game_id, **tally)
            for (player_id, game_id), tally in counts.items()
        ],
    )


def play_by_play_url(season: int) -> str:
    return f"{NFLVERSE_RELEASE_BASE}/pbp/play_by_play_{season}.csv.gz"


async def fetch_red_zone_usage(client: httpx.AsyncClient, season: int) -> NflverseRedZoneSeason:
    """Download one season and parse it while decompressing.

    The ~19 MB archive is held in memory, but the ~100 MB CSV inside it is read a
    line at a time rather than decoded into one string.
    """
    response = await get_release_asset(client, play_by_play_url(season), timeout=120)
    if response.status_code == 404:
        raise SeasonNotPublished(season, "play-by-play")
    response.raise_for_status()
    with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as archive:
        return parse_red_zone_usage(io.TextIOWrapper(archive, encoding="utf-8", newline=""), season)


async def run(season: int, dry_run: bool = False) -> str:
    """Fetch and parse the whole season, then write it in one transaction."""
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    async with httpx.AsyncClient(follow_redirects=True) as client:
        usage = await fetch_red_zone_usage(client, season)
    parsed = f"{len(usage.game_ids)} games, {len(usage.games)} player-games with red-zone, end-zone or punt counts"
    if dry_run:
        return f"NFLverse play-by-play would load {parsed} for season {season}"
    async with SessionLocal() as db:
        try:
            result = await nfl_repo.write_red_zone_usage(db, usage)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return (
        f"NFLverse play-by-play loaded {parsed} for season {season}: "
        f"{result.rows_reset} weekly rows reset, {result.rows_applied} counted, "
        f"{result.players_skipped} player-games skipped (no weekly-stat row), "
        f"{result.games_skipped} games skipped (not in sport_games)"
    )


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Load NFLverse red-zone and end-zone usage per player-game")
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
