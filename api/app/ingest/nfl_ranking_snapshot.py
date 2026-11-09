"""Store the NFL model page's ranking checks, one per model version, for the hosted demo.

The live v4 build peaks about 90 MB above the API's idle footprint, and the page
requests all three versions at once, so this computes them where memory is
plentiful (the Tuesday `nfl-ingest.yml` run) and the API serves the stored copies.

Run from api/: python -m app.ingest.nfl_ranking_snapshot [--season 2026] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from app.schemas.nfl import NflModelRankingResponse


def headline(response: NflModelRankingResponse) -> str:
    weeks = ", ".join(str(week) for week in response.finished_weeks) or "none"
    return (
        f"NFL ranking check {response.season} (model {response.model_version}): "
        f"{response.frozen_rows} frozen rows, {len(response.slices)} slices, finished weeks {weeks}"
    )


async def _main(season: int, dry_run: bool) -> None:
    from app.db.pool import SessionLocal, engine
    from app.repositories import report_snapshots
    from app.services.nfl.ranking_snapshot import (
        RANKING_MODEL_VERSIONS, build_ranking_response, ranking_report, to_payload,
    )

    async with SessionLocal() as db:
        for model_version in RANKING_MODEL_VERSIONS:
            response = await build_ranking_response(db, season, model_version)
            print(headline(response))
            if dry_run:
                continue
            report = ranking_report(model_version)
            await report_snapshots.upsert_snapshot(db, report, season, to_payload(response), response.graded_at)
            await db.commit()
            print(f"Stored {report} for {season}.")
        if dry_run:
            print("Dry run: nothing stored.")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Precompute the NFL model page's ranking checks")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--dry-run", action="store_true", help="compute and print, store nothing")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.season, args.dry_run))
