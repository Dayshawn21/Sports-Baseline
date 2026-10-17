"""Freeze today's upcoming PrizePicks projections as pre-match predictions (26f).

Runs after the daily prediction job, so every input the props page uses is
fresh. Safe to re-run: a prop row already stored for this projection version is
skipped.

Run from api/: python -m app.ingest.prop_snapshots
"""
from __future__ import annotations

import asyncio
import logging
import sys
from collections import Counter
from datetime import UTC, datetime

from app.db.pool import SessionLocal
from app.repositories.prop_snapshots import insert_prop_projection_snapshots
from app.repositories.props import get_today_props
from app.routers.props import enrich_props
from app.services.tennis.prop_snapshots import skip_reason, to_snapshot

logger = logging.getLogger(__name__)


async def snapshot_props() -> dict[str, int]:
    async with SessionLocal() as db:
        props = await get_today_props(db, source="prizepicks")
        lines = {line.id: line for line in await enrich_props(db, props)}
        now = datetime.now(UTC)
        skipped: Counter[str] = Counter()
        snapshots = []
        for prop in props:
            line = lines[prop.id]
            reason = skip_reason(prop, line, now)
            if reason is None:
                snapshots.append(to_snapshot(line))
            else:
                skipped[reason] += 1
        inserted = await insert_prop_projection_snapshots(db, snapshots)
        await db.commit()

    counts = {
        "loaded": len(props),
        "eligible": len(snapshots),
        "inserted": inserted,
        "already_stored": len(snapshots) - inserted,
    }
    counts.update({f"skipped_{reason}": n for reason, n in sorted(skipped.items())})
    return counts


async def _main() -> None:
    counts = await snapshot_props()
    logger.info("PrizePicks projection snapshots: %s", ", ".join(f"{k}={v}" for k, v in counts.items()))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
