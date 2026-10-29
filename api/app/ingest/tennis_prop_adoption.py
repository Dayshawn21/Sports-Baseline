"""Store which tennis prop slices 48e's rule adopts, for the props page to read (48g).

Grading reads every frozen snapshot and its box-score join, too heavy for the
hosted API's 512 MB, so it runs here and the page reads the small stored row.
Every real run reads settled outcomes, so the first one needs the owner's yes.

Run from api/: python -m app.ingest.tennis_prop_adoption [--version props-v3] [--as-of YYYY-MM-DD] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, date, datetime

from app.core.tennis_prop_adoption import JsonObject, adoption_report
from app.services.tennis.prop_snapshots import PROJECTION_VERSION


def summary(payload: JsonObject) -> str:
    adopted = payload["adopted"]
    keys = adopted if isinstance(adopted, list) else []
    lines = [
        f"Tennis prop adoption - {payload['rule']} on {payload['projectionVersion']} (as of {payload['asOf']})",
        f"  finished weeks {payload['finishedWeeks']} | decided slices {payload['decidedSlices']}"
        f" | adopted {len(keys)}",
    ]
    for key in keys:
        if isinstance(key, dict):
            lines.append(f"  adopt {key['stat']} / {key['tour']} / {key['anchor']} / {key['oddsType']} / {key['side']}")
    if not keys:
        lines.append("  nothing adopted: every line stays gray")
    return "\n".join(lines)


async def _main(version: str, as_of: date, dry_run: bool) -> None:
    from app.backtest.tennis_prop_check import to_frozen_lines
    from app.core.tennis_prop_adoption import ADOPTION_SEASON, to_payload
    from app.core.tennis_prop_check import check
    from app.db.pool import SessionLocal, engine
    from app.repositories import report_snapshots
    from app.repositories.player_match_stats import get_box_score_candidates
    from app.repositories.prop_snapshots import get_prop_check_snapshots

    async with SessionLocal() as db:
        rows = await get_prop_check_snapshots(db, version)
        contexts = await get_box_score_candidates(db, sorted({(row.player_id, row.match_id) for row in rows}))
        joins = {pair: context.join() for pair, context in contexts.items()}
        computed_at = datetime.now(UTC)
        payload = to_payload(check(to_frozen_lines(rows, joins), as_of), version, as_of, computed_at)
        print(summary(payload))
        if dry_run:
            print("Dry run: nothing stored.")
        else:
            await report_snapshots.upsert_snapshot(db, adoption_report(version), ADOPTION_SEASON, payload, computed_at)
            await db.commit()
            print(f"Stored {adoption_report(version)}.")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Store the tennis prop slices 48e's rule adopts")
    parser.add_argument("--version", default=PROJECTION_VERSION, help="projection version; never pooled")
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(UTC).date())
    parser.add_argument("--dry-run", action="store_true", help="grade and print, store nothing")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.version, args.as_of, args.dry_run))
