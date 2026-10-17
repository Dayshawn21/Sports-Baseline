"""Diagnose why props are not linking to matches.

Read-only. Distinguishes ingest-ordering failures (matches existed only after the
prop was stored) from a date/timezone mismatch in find_match_for_player.

    python diagnose_prop_links.py
"""
import asyncio
import sys

from sqlalchemy import text

from app.db.pool import SessionLocal

if sys.platform == "win32":
    # psycopg needs the selector loop; the default on Windows is ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main() -> None:
    async with SessionLocal() as db:
        print("=" * 72)
        print("PROP -> MATCH LINK DIAGNOSTIC")
        print("=" * 72)

        rows = await db.execute(text("""
            SELECT source,
                   COUNT(*)                                        AS total,
                   COUNT(*) FILTER (WHERE player_id IS NULL)       AS no_player,
                   COUNT(*) FILTER (WHERE player_id IS NOT NULL
                                      AND match_id IS NULL)        AS player_no_match,
                   COUNT(*) FILTER (WHERE match_id IS NOT NULL)    AS linked,
                   COUNT(*) FILTER (WHERE start_time IS NULL)      AS no_start_time
            FROM props
            WHERE fetched_at >= CURRENT_DATE
            GROUP BY source
            ORDER BY source
        """))
        print("\n-- today's props by source --")
        print(f"{'source':<14}{'total':>8}{'no_player':>11}{'plyr/no_match':>15}{'linked':>8}{'no_start':>10}")
        for r in rows.fetchall():
            print(f"{r[0]:<14}{r[1]:>8}{r[2]:>11}{r[3]:>15}{r[4]:>8}{r[5]:>10}")

        rows = await db.execute(text("""
            SELECT source,
                   COALESCE(raw_json->>'match_link_method', '(null)') AS method,
                   COUNT(*)
            FROM props
            WHERE fetched_at >= CURRENT_DATE
            GROUP BY source, method
            ORDER BY source, COUNT(*) DESC
        """))
        print("\n-- match_link_method recorded at ingest --")
        for r in rows.fetchall():
            print(f"  {r[0]:<14}{r[1]:<24}{r[2]:>8}")

        # The key question: for an unlinked prop with a resolved player, does a
        # match row actually exist now? If yes -> ingest ordering. If the only
        # match is on an adjacent date -> timezone/date mismatch.
        rows = await db.execute(text("""
            SELECT p.id,
                   p.source,
                   pl.name,
                   p.start_time,
                   (p.start_time AT TIME ZONE 'UTC')::date          AS utc_date,
                   m.id                                             AS match_id,
                   m.match_date,
                   m.start_utc
            FROM props p
            JOIN players pl ON pl.id = p.player_id
            LEFT JOIN LATERAL (
                SELECT id, match_date, start_utc
                FROM matches
                WHERE (p1_id = p.player_id OR p2_id = p.player_id)
                  AND match_date BETWEEN (p.start_time AT TIME ZONE 'UTC')::date - 1
                                     AND (p.start_time AT TIME ZONE 'UTC')::date + 1
                ORDER BY ABS(EXTRACT(EPOCH FROM (start_utc - p.start_time))) ASC
                LIMIT 1
            ) m ON TRUE
            WHERE p.fetched_at >= CURRENT_DATE
              AND p.match_id IS NULL
              AND p.player_id IS NOT NULL
              AND p.start_time IS NOT NULL
            ORDER BY p.source, p.id
            LIMIT 25
        """))
        print("\n-- sample unlinked props: does a match exist within +/-1 day? --")
        found = missing = same_day = off_day = 0
        for r in rows.fetchall():
            pid, source, name, start_time, utc_date, match_id, match_date, start_utc = r
            if match_id is None:
                missing += 1
                verdict = "NO MATCH IN DB"
            else:
                found += 1
                if match_date == utc_date:
                    same_day += 1
                    verdict = "match exists, SAME date -> ingest ordering"
                else:
                    off_day += 1
                    verdict = f"match on {match_date} vs utc_date {utc_date} -> DATE MISMATCH"
            print(f"  prop {pid:<8}{source:<12}{name[:22]:<24}{verdict}")

        print(f"\n  summary of sample: match_found={found} (same_day={same_day}, "
              f"off_by_date={off_day}), no_match_in_db={missing}")

        # Aggregate the same question across every unlinked prop.
        row = await db.execute(text("""
            SELECT COUNT(*)                                             AS unlinked,
                   COUNT(m.id)                                          AS resolvable,
                   COUNT(*) FILTER (WHERE m.match_date
                                          = (p.start_time AT TIME ZONE 'UTC')::date) AS same_date,
                   COUNT(*) FILTER (WHERE m.id IS NOT NULL
                                      AND m.match_date
                                          <> (p.start_time AT TIME ZONE 'UTC')::date) AS other_date
            FROM props p
            LEFT JOIN LATERAL (
                SELECT id, match_date
                FROM matches
                WHERE (p1_id = p.player_id OR p2_id = p.player_id)
                  AND match_date BETWEEN (p.start_time AT TIME ZONE 'UTC')::date - 1
                                     AND (p.start_time AT TIME ZONE 'UTC')::date + 1
                ORDER BY ABS(EXTRACT(EPOCH FROM (start_utc - p.start_time))) ASC
                LIMIT 1
            ) m ON TRUE
            WHERE p.fetched_at >= CURRENT_DATE
              AND p.match_id IS NULL
              AND p.player_id IS NOT NULL
              AND p.start_time IS NOT NULL
        """))
        unlinked, resolvable, same_date, other_date = row.fetchone()
        print("\n-- ALL unlinked props (with a resolved player) --")
        print(f"  unlinked ..................... {unlinked}")
        print(f"  a match exists for them now .. {resolvable}")
        print(f"    ... on the same UTC date ... {same_date}   (=> ingest ordering)")
        print(f"    ... on an adjacent date .... {other_date}   (=> date/tz mismatch)")
        print(f"  genuinely no match in DB ..... {unlinked - resolvable}")

        # Confidence distribution, to see what survives once linking is fixed.
        rows = await db.execute(text("""
            SELECT source, COUNT(*), COUNT(*) FILTER (WHERE match_id IS NOT NULL)
            FROM props
            WHERE fetched_at >= CURRENT_DATE
            GROUP BY source ORDER BY source
        """))
        print("\n-- matches table coverage --")
        row = await db.execute(text("""
            SELECT COUNT(*),
                   MIN(match_date),
                   MAX(match_date),
                   COUNT(*) FILTER (WHERE match_date = CURRENT_DATE)
            FROM matches
        """))
        total, min_d, max_d, today_n = row.fetchone()
        print(f"  matches rows={total} range={min_d}..{max_d} today={today_n}")


if __name__ == "__main__":
    asyncio.run(main())
