from __future__ import annotations

import argparse
import asyncio
from typing import Sequence

from sqlalchemy import text

from app.db.pool import SessionLocal


PREVIEW_SQL = text(
    """
    SELECT id, match_date, tour, tournament, round, surface, match_key
    FROM matches
    WHERE tournament ILIKE :tournament
      AND round ILIKE :round_name
      AND (CAST(:from_date AS date) IS NULL OR match_date >= CAST(:from_date AS date))
      AND (CAST(:to_date AS date) IS NULL OR match_date <= CAST(:to_date AS date))
    ORDER BY match_date, id
    """
)

UPDATE_SQL = text(
    """
    UPDATE matches
       SET surface = 'Clay',
           updated_at = now()
     WHERE tournament ILIKE :tournament
       AND round ILIKE :round_name
       AND (CAST(:from_date AS date) IS NULL OR match_date >= CAST(:from_date AS date))
       AND (CAST(:to_date AS date) IS NULL OR match_date <= CAST(:to_date AS date))
       AND surface IS DISTINCT FROM 'Clay'
    RETURNING id, match_date, tour, tournament, round, surface, match_key
    """
)


def _print_rows(rows: Sequence[tuple], heading: str) -> None:
    print(heading)
    if not rows:
        print("  no rows matched")
        return

    for row in rows:
        print(
            f"  id={row[0]} date={row[1]} tour={row[2]} "
            f"surface={row[5]} round={row[4]} tournament={row[3]} key={row[6]}"
        )


async def main_async(apply: bool, from_date: str | None, to_date: str | None) -> None:
    params = {
        "tournament": "%Linz%",
        "round_name": "%Qualification Round%",
        "from_date": from_date,
        "to_date": to_date,
    }

    async with SessionLocal() as db:
        preview = await db.execute(PREVIEW_SQL, params)
        preview_rows = preview.fetchall()
        _print_rows(preview_rows, "Matching Linz qualification rows:")

        if not apply:
            print("\nDry run only. Re-run with --apply to change surface to Clay.")
            return

        result = await db.execute(UPDATE_SQL, params)
        updated_rows = result.fetchall()
        await db.commit()
        _print_rows(updated_rows, "\nUpdated rows:")
        print(f"\nTotal updated: {len(updated_rows)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update Linz qualifying matches to Clay in the matches table."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write the update. Without this flag, the script only previews matches.",
    )
    parser.add_argument(
        "--from-date",
        type=str,
        default="2026-04-01",
        help="Inclusive lower match_date bound, default: 2026-04-01",
    )
    parser.add_argument(
        "--to-date",
        type=str,
        default=None,
        help="Inclusive upper match_date bound, optional",
    )
    args = parser.parse_args()

    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main_async(args.apply, args.from_date, args.to_date))


if __name__ == "__main__":
    main()
