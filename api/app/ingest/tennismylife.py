"""Ingest TennisMyLife box scores for tracked players without changing model inputs."""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import StringIO

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.tennismylife import PlayerNameIndex, TmlBoxScore, parse_rows, resolve_name
from app.db.pool import SessionLocal
from app.ingest.log_config import configure_ingest_logging
from app.repositories.player_match_stats import PlayerMatchStat, upsert_player_match_stats
from app.repositories.players import get_player_name_index, normalize_name

logger = logging.getLogger("tennismylife_ingest")
BASE_URL = "https://stats.tennismylife.org/data/"
BATCH_SIZE = 500
FAMILIES = ("ATP", "CHALLENGER", "ATP_QUALI", "WTA")


@dataclass(frozen=True)
class SourceFile:
    family: str
    tour: str
    path: str


@dataclass
class Counts:
    rows_read: int = 0
    rows_kept: int = 0
    no_stats: int = 0
    unknown: int = 0
    bad_rows: int = 0
    duplicates: int = 0
    unique: int = 0
    stored: int = 0


def source_files(cutoff: date, today: date) -> list[SourceFile]:
    files = []
    for year in range(cutoff.year, today.year + 1):
        files.extend([
            SourceFile("ATP", "ATP", f"{year}.csv"),
            SourceFile("CHALLENGER", "ATP", f"{year}_challenger.csv"),
            SourceFile("ATP_QUALI", "ATP", f"atp_quali/{year}_atp_quali.csv"),
            SourceFile("WTA", "WTA", f"{year}_wta.csv"),
        ])
    files.extend([
        SourceFile("ATP", "ATP", "ongoing_tourneys.csv"),
        SourceFile("CHALLENGER", "ATP", "challenger_ongoing_tourneys.csv"),
        SourceFile("WTA", "WTA", "wta_ongoing_tourneys.csv"),
    ])
    return files


def _retryable(exc: BaseException) -> bool:
    return isinstance(exc, httpx.TransportError) or (
        isinstance(exc, httpx.HTTPStatusError) and (exc.response.status_code == 429 or exc.response.status_code >= 500)
    )


@retry(
    retry=retry_if_exception(_retryable), stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True,
)
async def _download(client: httpx.AsyncClient, path: str) -> str:
    response = await client.get(BASE_URL + path)
    response.raise_for_status()
    return response.text


def _to_stat(box: TmlBoxScore, player_id: int) -> PlayerMatchStat:
    return PlayerMatchStat(
        player_id=player_id, source_match_key=box.source_match_key,
        match_date=box.match_date, surface=box.surface, result=box.result,
        aces=box.aces, double_faults=box.double_faults, service_games=box.service_games,
        break_points_faced=box.break_points_faced, break_points_saved=box.break_points_saved,
        break_chances_created=box.break_chances_created, break_points_converted=box.break_points_converted,
        opponent_name=box.opponent_name, round=box.round, tournament=box.tournament, score=box.score,
    )


def collect_rows(
    contents: str, source: SourceFile, cutoff: date, index: PlayerNameIndex,
    pending: dict[tuple[int, str], tuple[str, PlayerMatchStat]], counts: Counts,
) -> None:
    for number, row in enumerate(csv.DictReader(StringIO(contents)), start=2):
        counts.rows_read += 1
        try:
            match_date = datetime.strptime(row.get("tourney_date") or "", "%Y%m%d").date()
            if match_date < cutoff:
                continue
            boxes = parse_rows([row], source.tour)
        except (ValueError, TypeError) as exc:
            counts.bad_rows += 1
            logger.warning("Skipping %s row %d: %s", source.path, number, exc)
            continue
        counts.rows_kept += 1
        counts.no_stats += 2 - len(boxes)
        for box in boxes:
            player_id = resolve_name(index, normalize_name(box.player_name), box.tour)
            if player_id is None:
                counts.unknown += 1
                logger.debug("Unknown player in %s: %s (%s)", source.path, box.player_name, box.tour)
                continue
            key = (player_id, box.source_match_key)
            # source_files puts yearly files first; ongoing copies never replace them.
            if key in pending:
                counts.duplicates += 1
                continue
            pending[key] = (source.family, _to_stat(box, player_id))
            counts.unique += 1


def _print_counts(counts: dict[str, Counts], cutoff: date, dry_run: bool) -> None:
    print(f"TennisMyLife {'dry run' if dry_run else 'ingest'} since {cutoff.isoformat()}")
    print("rows_read/rows_kept/bad_rows count CSV matches; other columns count player-matches.")
    print(f"{'family':<12} {'rows_read':>9} {'rows_kept':>9} {'no_stats':>9} {'unknown':>9} "
          f"{'bad_rows':>9} {'duplicates':>10} {'unique':>9} {'stored':>9}")
    for family, c in counts.items():
        print(f"{family:<12} {c.rows_read:>9} {c.rows_kept:>9} {c.no_stats:>9} {c.unknown:>9} "
              f"{c.bad_rows:>9} {c.duplicates:>10} {c.unique:>9} {c.stored:>9}")
    print(f"Total unique player-matches: {sum(c.unique for c in counts.values())}; "
          f"stored: {sum(c.stored for c in counts.values())}")


async def run(cutoff: date, *, dry_run: bool = False) -> dict[str, Counts]:
    async with SessionLocal() as db:
        index = await get_player_name_index(db)
    logger.info("Loaded %d canonical names and %d aliases", len(index.canonical), len(index.aliases))
    pending: dict[tuple[int, str], tuple[str, PlayerMatchStat]] = {}
    counts = {family: Counts() for family in FAMILIES}
    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        for source in source_files(cutoff, date.today()):
            contents = await _download(client, source.path)
            collect_rows(contents, source, cutoff, index, pending, counts[source.family])
            logger.info("Read %s", source.path)
    if not dry_run:
        rows = [stat for _, stat in pending.values()]
        async with SessionLocal() as db:
            for start in range(0, len(rows), BATCH_SIZE):
                await upsert_player_match_stats(db, rows[start:start + BATCH_SIZE], source="tennismylife")
            await db.commit()
        for family, _ in pending.values():
            counts[family].stored += 1
    _print_counts(counts, cutoff, dry_run)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest TennisMyLife box scores for tracked players")
    parser.add_argument("--days-back", type=int, default=21)
    parser.add_argument("--since", type=date.fromisoformat, help="inclusive cutoff (YYYY-MM-DD), overrides --days-back")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.days_back < 0:
        parser.error("--days-back must be nonnegative")
    try:
        cutoff = args.since or date.today() - timedelta(days=args.days_back)
    except OverflowError:
        parser.error("--days-back is too large")
    if cutoff > date.today():
        parser.error("--since cannot be in the future")
    configure_ingest_logging()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run(cutoff, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
