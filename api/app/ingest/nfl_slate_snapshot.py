"""Store NFL slates for the hosted demo, which never builds one (37d).

A cold build peaks near 470 MB, so the NFL crons build here, where memory is
plentiful, after each run that changes a slate input; `/nfl/slate` serves the
stored copy.

Run from api/: python -m app.ingest.nfl_slate_snapshot [--season 2026]
    [--weeks current | all | 5,6] [--dry-run]

`current` stores the previous, current and next regular-season week, so the
week that just ended picks up final scores and the upcoming week is refreshed
before rollover.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime

from app.schemas.nfl import NflSlateResponse

REGULAR_SEASON_WEEKS = 18


def parse_weeks(value: str, current_week: int | None) -> list[int]:
    """The weeks `--weeks` names, in order, each within the regular season."""
    if value == "all":
        return list(range(1, REGULAR_SEASON_WEEKS + 1))
    if value == "current":
        if current_week is None:
            raise ValueError("No current NFL week: no regular-season game is loaded")
        return [
            week for week in (current_week - 1, current_week, current_week + 1)
            if 1 <= week <= REGULAR_SEASON_WEEKS
        ]
    weeks = sorted({int(part) for part in value.split(",") if part.strip()})
    if not weeks or weeks[0] < 1 or weeks[-1] > REGULAR_SEASON_WEEKS:
        raise ValueError(f"Weeks must be 1 to {REGULAR_SEASON_WEEKS}: {value!r}")
    return weeks


def summary(slate: NflSlateResponse, size_bytes: int) -> str:
    return (
        f"NFL slate {slate.season} week {slate.week}: {slate.game_count} games, "
        f"{slate.line_count} lines, {size_bytes / 1_000_000:.1f} MB"
    )


async def _main(season: int | None, weeks_arg: str, dry_run: bool) -> None:
    from app.db.pool import SessionLocal, engine
    from app.repositories import nfl as nfl_repo
    from app.repositories import report_snapshots
    from app.services.nfl.slate import build_slate
    from app.services.nfl.slate_cache import slate_json, slate_report

    async with SessionLocal() as db:
        current = await nfl_repo.get_current_week(db, datetime.now(UTC))
        if weeks_arg == "current" and current is not None and season not in (None, current[0]):
            raise SystemExit(f"--weeks current is {current[0]}'s week; omit --season or name the weeks")
        target_season = season if season is not None else (current[0] if current else None)
        if target_season is None:
            raise SystemExit("No NFL regular-season game is loaded; pass --season")
        weeks = parse_weeks(weeks_arg, current[1] if current else None)
        for week in weeks:
            built_at = datetime.now(UTC)
            slate = await build_slate(db, target_season, week, built_at)
            body = slate_json(slate)
            print(summary(slate, len(body)))
            if not dry_run:
                await report_snapshots.upsert_snapshot_text(
                    db, slate_report(week), target_season, body.decode(), built_at,
                )
                await db.commit()
            del slate, body
        print("Dry run: nothing stored." if dry_run else f"Stored {len(weeks)} week(s) for {target_season}.")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Precompute NFL slates for the hosted demo")
    parser.add_argument("--season", type=int, default=None, help="default: the current week's season")
    parser.add_argument("--weeks", default="current", help="current, all, or a comma list such as 5,6")
    parser.add_argument("--dry-run", action="store_true", help="build and print, store nothing")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.season, args.weeks, args.dry_run))
