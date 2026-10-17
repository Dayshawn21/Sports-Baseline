"""
Standalone script: ingest WTA matches for today and tomorrow only.

A thin wrapper over the livetennisapi ingest with the tour filter pinned — the
provider applies it server-side, so unlike the old Sofascore path this fetches
only WTA rather than scraping everything and discarding the rest.

Usage:
    python ingest_wta.py
    python ingest_wta.py --no-h2h   # skip H2H fetching (faster)
    python ingest_wta.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from app.ingest.livetennis import run

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("ingest_wta")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest WTA for today and tomorrow")
    parser.add_argument("--no-h2h", action="store_true", help="Skip H2H fetching (faster)")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and resolve but write nothing")
    args = parser.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(
        run(
            days_back=0,
            days_ahead=1,
            tours=["wta"],
            ingest_h2h=not args.no_h2h,
            dry_run=args.dry_run,
        )
    )
