"""Freeze today's upcoming PrizePicks projections as pre-match predictions (26f).

Runs after the daily prediction job, so every input the props page uses is
fresh. Safe to re-run: a prop row already stored for this projection version is
skipped.

Each eligible line is stored twice: the page's `props-v3` row and the match
simulation's `props-v4` shadow row (48c), both from one load of the inputs.
v4 is never shown or picked until 48e adopts a slice.

Run from api/: python -m app.ingest.prop_snapshots [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import Counter
from datetime import UTC, datetime

from app.db.pool import SessionLocal
from app.repositories.prop_snapshots import insert_prop_projection_snapshots
from app.repositories.props import get_today_props
from app.routers.props import enrich_with
from app.services.tennis.prop_sim import load_sim_inputs, sim_prop_lines
from app.services.tennis.prop_snapshots import (
    PROJECTION_VERSION,
    SIM_PROJECTION_VERSION,
    PropProjectionSnapshot,
    skip_reason,
    to_snapshot,
)

logger = logging.getLogger(__name__)


async def snapshot_props(*, dry_run: bool = False) -> dict[str, int]:
    async with SessionLocal() as db:
        props = await get_today_props(db, source="prizepicks")
        inputs = await load_sim_inputs(db, props)
        v3_lines = enrich_with(
            props, inputs.opponent_ids, inputs.rolling_stats, inputs.prediction_probs,
            inputs.market_probs, inputs.market_totals,
        )
        v4_lines = sim_prop_lines(props, v3_lines, inputs)
        now = datetime.now(UTC)
        skipped: Counter[str] = Counter()
        by_version: dict[str, list[PropProjectionSnapshot]] = {PROJECTION_VERSION: [], SIM_PROJECTION_VERSION: []}
        for prop, v3, v4 in zip(props, v3_lines, v4_lines, strict=True):
            reason = skip_reason(prop, v3, now)
            if reason is not None:
                skipped[reason] += 1
                continue
            by_version[PROJECTION_VERSION].append(to_snapshot(prop, v3, now, PROJECTION_VERSION))
            by_version[SIM_PROJECTION_VERSION].append(to_snapshot(prop, v4, now, SIM_PROJECTION_VERSION))

        counts = {"loaded": len(props), "eligible": len(by_version[PROJECTION_VERSION])}
        for version, snapshots in by_version.items():
            counts[f"{version}_eligible"] = len(snapshots)
            if dry_run:
                continue
            result = await insert_prop_projection_snapshots(db, snapshots)
            counts[f"{version}_inserted"] = result.inserted
            counts[f"{version}_already_stored"] = result.already_stored
            counts[f"{version}_skipped_started_at_insert"] = result.rejected_started
        if not dry_run:
            await db.commit()

    counts.update({f"skipped_{reason}": n for reason, n in sorted(skipped.items())})
    return counts


async def _main(dry_run: bool) -> None:
    counts = await snapshot_props(dry_run=dry_run)
    label = "PrizePicks projection snapshots (dry run, nothing inserted)" if dry_run else "PrizePicks projection snapshots"
    logger.info("%s: %s", label, ", ".join(f"{k}={v}" for k, v in counts.items()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Freeze today's PrizePicks projections as pre-match predictions")
    parser.add_argument("--dry-run", action="store_true", help="build both versions and print counts; insert nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.dry_run))
