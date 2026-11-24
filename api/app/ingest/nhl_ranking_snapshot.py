"""Store the NHL model page's ranking check for the hosted demo.

The live build grades the whole season on the API's one shared CPU, so this
computes it in the daily `nhl-ingest.yml` run, after the box scores settle the
calls, and the API serves the stored copy.

Run from api/: python -m app.ingest.nhl_ranking_snapshot [--season N] [--dry-run]
The season defaults to the one `/nhl/model/ranking` serves with no season given.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime

from app.schemas.nhl import NhlModelRankingResponse


def headline(response: NhlModelRankingResponse) -> str:
    weeks = ", ".join(str(week) for week in response.finished_weeks) or "none"
    return (
        f"NHL ranking check {response.season} (model {response.model_version}): "
        f"{response.frozen_rows} frozen rows, {len(response.slices)} slices, finished weeks {weeks}"
    )


async def _main(season: int | None, dry_run: bool) -> None:
    from app.db.pool import SessionLocal, engine
    from app.repositories import report_snapshots
    from app.services.nhl import track_record
    from app.services.nhl.ranking_snapshot import RANKING_REPORT, build_ranking_response, to_payload

    async with SessionLocal() as db:
        if season is None:
            season = await track_record.nhl_season(db, datetime.now(UTC))
        if season is None:
            print("No NHL regular-season games are loaded: nothing to grade.")
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
    parser = argparse.ArgumentParser(description="Precompute the NHL model page's ranking check")
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true", help="compute and print, store nothing")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.season, args.dry_run))
