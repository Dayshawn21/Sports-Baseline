"""Store the NBA model page's ranking check for the hosted demo.

The live build peaks about 100 MB above the API's idle footprint, so this
computes it where memory is plentiful (the daily `nba-ingest.yml` run, after the
box scores settle the calls) and the API serves the stored copy.

Run from api/: python -m app.ingest.nba_ranking_snapshot [--season N] [--dry-run]
The season defaults to the one `/nba/model/ranking` serves with no season given.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime

from app.schemas.nba import NbaModelRankingResponse


def headline(response: NbaModelRankingResponse) -> str:
    weeks = ", ".join(str(week) for week in response.finished_weeks) or "none"
    return (
        f"NBA ranking check {response.season} (model {response.model_version}): "
        f"{response.frozen_rows} frozen rows, {len(response.slices)} slices, finished weeks {weeks}"
    )


async def _main(season: int | None, dry_run: bool) -> None:
    from app.db.pool import SessionLocal, engine
    from app.repositories import report_snapshots
    from app.services.nba import track_record
    from app.services.nba.ranking_snapshot import RANKING_REPORT, build_ranking_response, to_payload

    async with SessionLocal() as db:
        if season is None:
            season = await track_record.nba_season(db, datetime.now(UTC))
        if season is None:
            print("No NBA regular-season games are loaded: nothing to grade.")
        else:
            response = await build_ranking_response(db, season)
            print(headline(response))
            if dry_run:
                print("Dry run: nothing stored.")
            else:
                await report_snapshots.upsert_snapshot(db, RANKING_REPORT, season, to_payload(response), response.graded_at)
                await db.commit()
                print(f"Stored {RANKING_REPORT} for {season}.")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Precompute the NBA model page's ranking check")
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true", help="compute and print, store nothing")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.season, args.dry_run))
