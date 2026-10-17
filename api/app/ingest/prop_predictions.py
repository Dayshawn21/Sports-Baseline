"""Freeze a sport's current-week predictions for every line not yet started (27i, shared since 20g3).

Runs straight after each PrizePicks line snapshot, so the newest line rows get
the projection and P(over) the sport's page served at that moment. Safe to
re-run: a line already stored for this model and P(over) version is skipped.
Both sports' period is the week.

Run from api/: python -m app.ingest.prop_predictions --sport nfl|nba [--dry-run]
(or each sport's own entry point, `python -m app.ingest.<sport>_prop_predictions`)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import Counter
from datetime import UTC, datetime

from app.core.prop_predictions import PropPredictionRow
from app.db.pool import SessionLocal
from app.services.prop_predictions import freeze_current_period
from app.services.sport_registry import PROP_SOURCES, prop_source

logger = logging.getLogger(__name__)


def _with_p_over(rows: list[PropPredictionRow]) -> Counter[str]:
    return Counter(str(row.feature_snapshot["odds_type"]) for row in rows if row.p_over is not None)


async def freeze_current_week(sport: str, dry_run: bool) -> dict[str, int | str]:
    async with SessionLocal() as db:
        run = await freeze_current_period(db, prop_source(sport), datetime.now(UTC), dry_run)
    if run is None:
        return {"week": "none loaded"}

    summary: dict[str, int | str] = {"week": f"{run.season} week {run.period}", **run.counts}
    if run.inserted is not None:
        summary |= {"inserted": run.inserted, "already_stored": len(run.rows) - run.inserted}
    summary |= {f"with_p_over_{odds_type}": n for odds_type, n in sorted(_with_p_over(run.rows).items())}
    return summary


async def _main(sport: str, dry_run: bool) -> None:
    summary = await freeze_current_week(sport, dry_run)
    label = f"{sport.upper()} prop predictions"
    if dry_run:
        label += " (dry run, nothing written)"
    logger.info("%s: %s", label, ", ".join(f"{k}={v}" for k, v in summary.items()))


def main(sport: str | None = None) -> None:
    """Command line entry; a per-sport entry point passes its sport and omits `--sport`."""
    parser = argparse.ArgumentParser(description="Freeze a sport's pre-start prop predictions")
    if sport is None:
        parser.add_argument("--sport", required=True, choices=sorted(PROP_SOURCES))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(sport or args.sport, args.dry_run))


if __name__ == "__main__":
    main()
