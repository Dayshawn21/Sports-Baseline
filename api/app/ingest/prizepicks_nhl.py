"""Snapshot and relink NHL prop lines through the shared pipeline (45c)."""
from __future__ import annotations

import argparse
import asyncio
import sys

from app.ingest import prizepicks_props
from app.ingest.prizepicks_props import PrizePicksRateLimited
from app.services.nhl.prop_source import NhlPropSource


async def run(dry_run: bool = False) -> int:
    return await prizepicks_props.run(NhlPropSource(), dry_run)


async def relink() -> int:
    return await prizepicks_props.relink(NhlPropSource())


def main() -> int:
    parser = argparse.ArgumentParser(description="Snapshot PrizePicks NHL prop lines")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--relink", action="store_true",
        help="re-resolve stored lines to players and games without fetching from the provider",
    )
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if args.relink:
        print(asyncio.run(relink()))
        return 0
    try:
        print(asyncio.run(run(args.dry_run)))
    except PrizePicksRateLimited as exc:
        print(exc)
        return 75
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
