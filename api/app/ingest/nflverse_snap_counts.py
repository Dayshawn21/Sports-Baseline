"""NFLverse snap counts: offensive snaps and snap share per player per game.

The source is Pro Football Reference data keyed by PFR player id, while
`sport_players` stores gsis ids, so rows are matched through the PFR-to-gsis map in
NFLverse's `players.csv`. Unmapped players are skipped, never guessed.
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

# The file's position labels, not ours; `HB` appears alongside `RB` in 2024-2025.
OFFENSIVE_SKILL_POSITIONS = frozenset({"QB", "RB", "HB", "FB", "WR", "TE"})


@dataclass(frozen=True)
class NflverseSnapGame:
    pfr_player_id: str
    game_id: str
    season: int
    week: int
    team: str
    # None when the source left the value blank; 0 means no offensive snaps.
    offense_snaps: int | None
    # A fraction from 0 to 1, as published.
    offense_pct: float | None


@dataclass(frozen=True)
class NflverseSnapSeason:
    # Every regular-season game in the file, so a rerun replaces games whose rows all dropped out.
    game_ids: frozenset[str]
    games: list[NflverseSnapGame]


def _text(value: str | None) -> str | None:
    value = (value or "").strip()
    return value if value and value.upper() != "NA" else None


def _int(value: str | None) -> int | None:
    text = _text(value)
    try:
        return int(float(text)) if text is not None else None
    except ValueError:
        return None


def _float(value: str | None) -> float | None:
    text = _text(value)
    try:
        return float(text) if text is not None else None
    except ValueError:
        return None


def parse_pfr_gsis_map(lines: Iterable[str]) -> dict[str, str]:
    """PFR id to gsis id, dropping any PFR id that maps to more than one gsis id."""
    candidates: dict[str, set[str]] = {}
    for row in csv.DictReader(lines):
        pfr_id, gsis_id = _text(row.get("pfr_id")), _text(row.get("gsis_id"))
        if pfr_id and gsis_id:
            candidates.setdefault(pfr_id, set()).add(gsis_id)
    return {pfr_id: next(iter(ids)) for pfr_id, ids in candidates.items() if len(ids) == 1}


def parse_snap_counts(lines: Iterable[str], season: int) -> NflverseSnapSeason:
    """Regular-season offensive skill-player snap rows for `season`, one per player per game.

    A player listed twice in one game keeps the later row.
    """
    game_ids: set[str] = set()
    by_player_game: dict[tuple[str, str], NflverseSnapGame] = {}
    for row in csv.DictReader(lines):
        if row.get("season") != str(season) or row.get("game_type") != "REG":
            continue
        game_id, week = _text(row.get("game_id")), _int(row.get("week"))
        if game_id is None or week is None:
            continue
        game_ids.add(game_id)
        pfr_id, team = _text(row.get("pfr_player_id")), _text(row.get("team"))
        if pfr_id is None or team is None or row.get("position") not in OFFENSIVE_SKILL_POSITIONS:
            continue
        by_player_game[(pfr_id, game_id)] = NflverseSnapGame(
            pfr_player_id=pfr_id, game_id=game_id, season=season, week=week, team=franchise_code(team),
            offense_snaps=_int(row.get("offense_snaps")), offense_pct=_float(row.get("offense_pct")),
        )
    return NflverseSnapSeason(frozenset(game_ids), list(by_player_game.values()))


@dataclass(frozen=True)
class ResolvedSnapGames:
    # (gsis id, row) pairs, at most one per gsis id per game.
    rows: list[tuple[str, NflverseSnapGame]]
    unmapped: int


def resolve_gsis_ids(snaps: NflverseSnapSeason, pfr_to_gsis: dict[str, str]) -> ResolvedSnapGames:
    """Attach gsis ids, counting rows whose PFR id has no mapping.

    Two PFR ids resolving to one gsis id in the same game keep the later row, so
    the insert never trips the (player, game) unique key.
    """
    by_player_game: dict[tuple[str, str], tuple[str, NflverseSnapGame]] = {}
    unmapped = 0
    for game in snaps.games:
        gsis_id = pfr_to_gsis.get(game.pfr_player_id)
        if gsis_id is None:
            unmapped += 1
            continue
        by_player_game[(gsis_id, game.game_id)] = (gsis_id, game)
    return ResolvedSnapGames(list(by_player_game.values()), unmapped)


def snap_counts_url(season: int) -> str:
    return f"{NFLVERSE_RELEASE_BASE}/snap_counts/snap_counts_{season}.csv"


def players_url() -> str:
    return f"{NFLVERSE_RELEASE_BASE}/players/players.csv"


async def fetch_snap_counts(client: httpx.AsyncClient, season: int) -> NflverseSnapSeason:
    response = await get_release_asset(client, snap_counts_url(season), timeout=120)
    if response.status_code == 404:
        raise SeasonNotPublished(season, "snap counts")
    response.raise_for_status()
    return parse_snap_counts(response.text.splitlines(), season)


async def fetch_pfr_gsis_map(client: httpx.AsyncClient) -> dict[str, str]:
    response = await get_release_asset(client, players_url(), timeout=120)
    response.raise_for_status()
    return parse_pfr_gsis_map(response.text.splitlines())


async def run(season: int, dry_run: bool = False) -> str:
    """Fetch, parse, and resolve the whole season, then replace its games in one transaction."""
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    async with httpx.AsyncClient(follow_redirects=True) as client:
        snaps = await fetch_snap_counts(client, season)
        resolved = resolve_gsis_ids(snaps, await fetch_pfr_gsis_map(client))
    parsed = (
        f"{len(snaps.games)} snap rows in {len(snaps.game_ids)} games of season {season} "
        f"({resolved.unmapped} with no PFR-to-gsis mapping)"
    )
    if dry_run:
        return f"NFLverse snap counts would load {parsed}"
    async with SessionLocal() as db:
        try:
            result = await nfl_repo.replace_snap_counts(db, snaps.game_ids, resolved.rows)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return (
        f"NFLverse snap counts loaded {parsed}: {result.rows_deleted} replaced, {result.rows_inserted} stored, "
        f"{result.rows_skipped_player} skipped (player not stored), "
        f"{result.rows_skipped_game} skipped (game not stored)"
        + (f", unknown teams {result.unknown_teams}" if result.unknown_teams else "")
    )


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Load NFLverse snap counts (offensive snaps and share per player-game)")
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
