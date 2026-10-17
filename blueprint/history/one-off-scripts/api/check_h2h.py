"""Diagnostic: check whether the h2h table is populated and whether predictions
return non-zero H2H values. Temporary — safe to delete once verified."""
import asyncio
import sys
from sqlalchemy import text

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.db.pool import SessionLocal


async def main():
    async with SessionLocal() as db:
        total = (await db.execute(text("SELECT COUNT(*) FROM h2h"))).scalar()
        no_surface = (await db.execute(text("SELECT COUNT(*) FROM h2h WHERE surface IS NULL"))).scalar()
        with_wins = (await db.execute(text("SELECT COUNT(*) FROM h2h WHERE p1_wins + p2_wins > 0"))).scalar()
        print(f"h2h total rows           : {total}")
        print(f"  surface IS NULL        : {no_surface}")
        print(f"  with p1_wins+p2_wins>0 : {with_wins}")
        print()

        rows = (await db.execute(text(
            "SELECT p1_id, p2_id, surface, p1_wins, p2_wins, updated_at "
            "FROM h2h ORDER BY updated_at DESC NULLS LAST LIMIT 10"
        ))).all()
        print("Last 10 h2h rows (most recent updated_at):")
        for r in rows:
            print(f"  p1={r.p1_id} p2={r.p2_id} surface={r.surface!r} {r.p1_wins}-{r.p2_wins} updated={r.updated_at}")
        print()

        joined = (await db.execute(text(
            """
            SELECT m.id AS match_id, m.tour, m.surface, m.start_utc,
                   p1.name AS p1_name, p2.name AS p2_name,
                   h.p1_wins, h.p2_wins, h.surface AS h2h_surface
            FROM matches m
            LEFT JOIN players p1 ON p1.id = m.p1_id
            LEFT JOIN players p2 ON p2.id = m.p2_id
            LEFT JOIN h2h h
              ON h.p1_id = m.p1_id AND h.p2_id = m.p2_id AND h.surface IS NULL
            WHERE m.start_utc >= NOW() - INTERVAL '1 day'
              AND m.start_utc <  NOW() + INTERVAL '2 days'
            ORDER BY m.start_utc
            LIMIT 20
            """
        ))).all()
        print("Upcoming/today matches with all-surface H2H lookup (LEFT JOIN — NULL = no row):")
        if not joined:
            print("  (no matches scheduled in -1d / +2d window)")
        for r in joined:
            wins = "—" if r.p1_wins is None else f"{r.p1_wins}-{r.p2_wins}"
            print(f"  match {r.match_id} {r.tour} {r.surface} {r.p1_name} vs {r.p2_name} | h2h={wins}")


if __name__ == "__main__":
    asyncio.run(main())
