"""Check recent fantasy score prop lines from PrizePicks to calibrate formula."""
import asyncio
import asyncio as _asyncio
_asyncio.set_event_loop_policy(_asyncio.WindowsSelectorEventLoopPolicy())
from app.db.pool import SessionLocal
from sqlalchemy import text

async def main():
    async with SessionLocal() as db:
        rows = await db.execute(text("""
            SELECT
                COALESCE(raw_json->>'player_name', '') AS player_name,
                line,
                start_time,
                raw_json->>'surface' AS surface
            FROM props
            WHERE source = 'prizepicks'
              AND LOWER(stat_type) LIKE '%fantasy%'
            ORDER BY start_time DESC
            LIMIT 30
        """))
        results = rows.fetchall()
        if not results:
            print("No fantasy score props found in DB")
            return
        print(f"{'Player':<25} {'Line':>6} {'Surface':<8} {'Start'}")
        print("-" * 60)
        for row in results:
            print(f"{row.player_name:<25} {float(row.line):>6.1f} {(row.surface or '?'):<8} {row.start_time}")

asyncio.run(main())
