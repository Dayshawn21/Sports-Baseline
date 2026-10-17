"""List the distinct markets stored in match_odds. Read-only."""
import asyncio, sys
from sqlalchemy import text
from app.db.pool import SessionLocal

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def main():
    async with SessionLocal() as db:
        rows = await db.execute(text("""
            SELECT LOWER(book), market, COUNT(*), COUNT(line) AS with_line
            FROM match_odds
            WHERE fetched_at >= now() - interval '24 hours'
            GROUP BY 1, 2 ORDER BY 1, 3 DESC
        """))
        print(f"{'book':<16}{'market':<24}{'rows':>8}{'with_line':>11}")
        for b, m, n, wl in rows.fetchall():
            print(f"{b:<16}{m:<24}{n:>8}{wl:>11}")

asyncio.run(main())
