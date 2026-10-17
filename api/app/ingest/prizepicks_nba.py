"""PrizePicks NBA prop-line ingest, run through the shared pipeline in `prizepicks_props` (item 20c).

Every NBA market is line-only until 20g: lines are stored and linked for line
history, never projected or graded.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from app.ingest import prizepicks_props
from app.ingest.prizepicks_props import PrizePicksRateLimited
from app.services.nba.prop_source import NbaPropSource


async def run(dry_run: bool = False) -> int:
    return await prizepicks_props.run(NbaPropSource(), dry_run)


async def relink() -> int:
    """Re-resolve stored NBA lines to players and games without a provider request."""
    return await prizepicks_props.relink(NbaPropSource())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Snapshot PrizePicks NBA prop lines")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--relink",
        action="store_true",
        help="re-resolve stored lines to players and games without fetching from the provider",
    )
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if args.relink:
        print(asyncio.run(relink()))
        raise SystemExit(0)
    try:
        print(asyncio.run(run(args.dry_run)))
    except PrizePicksRateLimited as exc:
        print(exc)
        raise SystemExit(75)
