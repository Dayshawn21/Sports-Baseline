"""Store the NFL model page's PrizePicks line grading for the hosted demo (37d).

The live replay peaks above the demo's 512 MB, so this computes it where memory
is plentiful (the Tuesday `nfl-ingest.yml` run, after the stats load) and the
API serves the stored copy.

Run from api/: python -m app.ingest.nfl_model_snapshot [--season 2026] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from app.schemas.nfl import NflModelPropLinesResponse


def headline(response: NflModelPropLinesResponse) -> str:
    calls = response.calls
    rate = "n/a" if calls.hit_rate is None else f"{calls.hit_rate:.1%}"
    weeks = ", ".join(str(row.week) for row in response.by_week) or "none"
    return (
        f"NFL prop-line grading {response.season} (model {response.model_version}): "
        f"{calls.calls} calls, hit rate {rate}, weeks {weeks}"
    )


async def _main(season: int, dry_run: bool) -> None:
    from app.db.pool import SessionLocal, engine
    from app.repositories import report_snapshots
    from app.services.nfl.prop_lines_snapshot import PROP_LINES_REPORT, build_prop_lines_response, to_payload

    async with SessionLocal() as db:
        response = await build_prop_lines_response(db, season)
        print(headline(response))
        if dry_run:
            print("Dry run: nothing stored.")
        else:
            await report_snapshots.upsert_snapshot(
                db, PROP_LINES_REPORT, season, to_payload(response), response.graded_at,
            )
            await db.commit()
            print(f"Stored {PROP_LINES_REPORT} for {season}.")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Precompute the NFL model page's line grading")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--dry-run", action="store_true", help="compute and print, store nothing")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.season, args.dry_run))
