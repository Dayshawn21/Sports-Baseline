"""
One-time fix: merge duplicate Chun-Hsin Tseng records.
  id=202  "Chun Hsin Tseng"   ATP  (has ELO, no stats)   ← keep this one
  id=11007 "Chun-Hsin Tseng"  CHALLENGER (has stats, no ELO) ← merge into 202, delete
"""
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

KEEP_ID   = 202    # canonical ATP record
DUPE_ID   = 11007  # duplicate CHALLENGER record


async def main():
    from app.db.pool import SessionLocal
    from sqlalchemy import text

    async with SessionLocal() as db:
        # 1. Show current state
        r = await db.execute(text(
            "SELECT id, name, tour, sofascore_id FROM players WHERE id IN (:a, :b)"
        ), {"a": KEEP_ID, "b": DUPE_ID})
        for row in r.fetchall():
            print(f"BEFORE player: id={row[0]} name={row[1]} tour={row[2]} sofascore_id={row[3]}")

        # 2. Copy stats from dupe → canonical (only rows not already present on 202)
        await db.execute(text("""
            INSERT INTO player_rolling_stats
                (player_id, surface, stat_period, win_rate, svc_pts_won, ret_pts_won,
                 aces_per_game, df_per_game, hold_pct, break_pct, matches_count, computed_at)
            SELECT :keep, surface, stat_period, win_rate, svc_pts_won, ret_pts_won,
                   aces_per_game, df_per_game, hold_pct, break_pct, matches_count, computed_at
            FROM player_rolling_stats
            WHERE player_id = :dupe
            ON CONFLICT (player_id, stat_period, surface) DO UPDATE SET
                win_rate       = EXCLUDED.win_rate,
                svc_pts_won    = EXCLUDED.svc_pts_won,
                ret_pts_won    = EXCLUDED.ret_pts_won,
                aces_per_game  = EXCLUDED.aces_per_game,
                df_per_game    = EXCLUDED.df_per_game,
                hold_pct       = EXCLUDED.hold_pct,
                break_pct      = EXCLUDED.break_pct,
                matches_count  = EXCLUDED.matches_count,
                computed_at    = EXCLUDED.computed_at
        """), {"keep": KEEP_ID, "dupe": DUPE_ID})
        print(f"Stats copied from {DUPE_ID} to {KEEP_ID}")

        # 3. Re-point all matches from dupe → canonical
        r = await db.execute(text(
            "UPDATE matches SET p1_id = :keep WHERE p1_id = :dupe"
        ), {"keep": KEEP_ID, "dupe": DUPE_ID})
        print(f"Updated p1_id on {r.rowcount} matches")

        r = await db.execute(text(
            "UPDATE matches SET p2_id = :keep WHERE p2_id = :dupe"
        ), {"keep": KEEP_ID, "dupe": DUPE_ID})
        print(f"Updated p2_id on {r.rowcount} matches")

        # 4. Re-point player_aliases if any
        await db.execute(text(
            "UPDATE player_aliases SET canonical_player_id = :keep WHERE canonical_player_id = :dupe"
        ), {"keep": KEEP_ID, "dupe": DUPE_ID})

        # 5. Delete dupe player's remaining stats and the dupe player row
        await db.execute(text("DELETE FROM player_rolling_stats WHERE player_id = :dupe"), {"dupe": DUPE_ID})
        await db.execute(text("DELETE FROM player_elo WHERE player_id = :dupe"), {"dupe": DUPE_ID})
        await db.execute(text("DELETE FROM players WHERE id = :dupe"), {"dupe": DUPE_ID})
        print(f"Deleted duplicate player {DUPE_ID}")

        await db.commit()

        # 6. Confirm final state
        r = await db.execute(text(
            "SELECT id, name, tour, sofascore_id FROM players WHERE id = :a"
        ), {"a": KEEP_ID})
        for row in r.fetchall():
            print(f"AFTER  player: id={row[0]} name={row[1]} tour={row[2]} sofascore_id={row[3]}")

        r = await db.execute(text(
            "SELECT surface, stat_period, win_rate, svc_pts_won, matches_count FROM player_rolling_stats WHERE player_id = :a ORDER BY surface"
        ), {"a": KEEP_ID})
        for row in r.fetchall():
            print(f"AFTER  stats:  surface={row[0]} period={row[1]} wr={row[2]} svc={row[3]} n={row[4]}")

        r = await db.execute(text(
            "SELECT m.id, m.match_date, m.tournament, p1.name, p2.name FROM matches m JOIN players p1 ON p1.id=m.p1_id JOIN players p2 ON p2.id=m.p2_id WHERE (m.p1_id=:a OR m.p2_id=:a) AND m.match_date=CURRENT_DATE"
        ), {"a": KEEP_ID})
        for row in r.fetchall():
            print(f"AFTER  match:  id={row[0]} date={row[1]} {row[3]} vs {row[4]} @ {row[2]}")


asyncio.run(main())
