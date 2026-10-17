"""
One-time ELO seed from local TennisAbstract CSV snapshots.

Reads all CSV files from SportApp/api/data/elo/ and loads them
into the new players + player_elo tables.

Run from SportAppV2/api/:
    python -m app.scripts.seed_elo
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Path to existing ELO CSVs in old SportApp
OLD_ELO_DIR = Path(__file__).parent.parent.parent.parent.parent / "SportApp" / "api" / "data" / "elo"


async def main() -> None:
    from app.config import settings
    from app.db.pool import SessionLocal
    from app.ingest.elo import ingest_from_csv

    if not OLD_ELO_DIR.exists():
        logger.error("ELO directory not found: %s", OLD_ELO_DIR)
        sys.exit(1)

    csv_files = sorted(OLD_ELO_DIR.glob("tennisabstract_*.csv"))
    if not csv_files:
        logger.error("No CSV files found in %s", OLD_ELO_DIR)
        sys.exit(1)

    logger.info("Found %d ELO CSV files in %s", len(csv_files), OLD_ELO_DIR)

    async with SessionLocal() as db:
        for csv_path in csv_files:
            # Determine tour from filename: tennisabstract_atp_elo_*.csv or _wta_elo_*
            name = csv_path.stem.lower()
            if "_atp_" in name:
                tour = "ATP"
            elif "_wta_" in name:
                tour = "WTA"
            else:
                logger.warning("Cannot determine tour for %s — skipping", csv_path.name)
                continue

            try:
                n = await ingest_from_csv(db, csv_path, tour)
                logger.info("  ✓ %s: %d rows", csv_path.name, n)
            except Exception as e:
                logger.error("  ✗ %s: %s", csv_path.name, e)

    logger.info("ELO seed complete.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
