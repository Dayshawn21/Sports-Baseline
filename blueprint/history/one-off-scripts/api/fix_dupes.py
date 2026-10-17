"""
Merge all duplicate players (same sofascore_id) into the canonical record.
Rule: keep the one with ELO (lower id, ATP record), merge stats + matches from the dupe.
"""
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# (keep_id, dupe_id) — keep=has ELO, dupe=has stats
PAIRS = [
    (115,  15363),   # Christopher O'Connell
    (116,  15348),   # Bu Yunchaokete / Yunchaokete Bu
    (200,  11115),   # Daniel Merida Aguilar / Daniel Merida
    (419,  11155),   # Diego Dedura Palomero / Diego Dedura-Palomero
]


async def merge(db, keep_id: int, dupe_id: int) -> None:
    from sqlalchemy import text

    r = await db.execute(text("SELECT id, name, tour FROM players WHERE id IN (:a, :b)"), {"a": keep_id, "b": dupe_id})
    players = {row[0]: row for row in r.fetchall()}
    keep = players.get(keep_id)
    dupe = players.get(dupe_id)
    if not keep or not dupe:
        print(f"  SKIP ({keep_id}, {dupe_id}) — one or both not found")
        return

    print(f"\nMerging: [{dupe[0]}] {dupe[1]} ({dupe[2]})  -->  [{keep[0]}] {keep[1]} ({keep[2]})")

    # Copy stats from dupe -> keep
    r = await db.execute(text("""
        INSERT INTO player_rolling_stats
            (player_id, surface, stat_period, win_rate, svc_pts_won, ret_pts_won,
             aces_per_game, df_per_game, hold_pct, break_pct, matches_count, computed_at)
        SELECT :keep, surface, stat_period, win_rate, svc_pts_won, ret_pts_won,
               aces_per_game, df_per_game, hold_pct, break_pct, matches_count, computed_at
        FROM player_rolling_stats
        WHERE player_id = :dupe
        ON CONFLICT (player_id, stat_period, surface) DO UPDATE SET
            win_rate      = EXCLUDED.win_rate,
            svc_pts_won   = EXCLUDED.svc_pts_won,
            ret_pts_won   = EXCLUDED.ret_pts_won,
            aces_per_game = EXCLUDED.aces_per_game,
            df_per_game   = EXCLUDED.df_per_game,
            hold_pct      = EXCLUDED.hold_pct,
            break_pct     = EXCLUDED.break_pct,
            matches_count = EXCLUDED.matches_count,
            computed_at   = EXCLUDED.computed_at
    """), {"keep": keep_id, "dupe": dupe_id})
    print(f"  Stats copied")

    # Re-point matches
    r = await db.execute(text("UPDATE matches SET p1_id = :keep WHERE p1_id = :dupe"), {"keep": keep_id, "dupe": dupe_id})
    r2 = await db.execute(text("UPDATE matches SET p2_id = :keep WHERE p2_id = :dupe"), {"keep": keep_id, "dupe": dupe_id})
    print(f"  Matches re-pointed: {r.rowcount + r2.rowcount}")

    # Re-point all FK references
    await db.execute(text("UPDATE player_aliases SET canonical_player_id = :keep WHERE canonical_player_id = :dupe"), {"keep": keep_id, "dupe": dupe_id})
    await db.execute(text("UPDATE props SET player_id = :keep WHERE player_id = :dupe"), {"keep": keep_id, "dupe": dupe_id})
    await db.execute(text("UPDATE matches SET winner_id = :keep WHERE winner_id = :dupe"), {"keep": keep_id, "dupe": dupe_id})
    r = await db.execute(text("UPDATE h2h SET p1_id = :keep WHERE p1_id = :dupe"), {"keep": keep_id, "dupe": dupe_id})
    r2 = await db.execute(text("UPDATE h2h SET p2_id = :keep WHERE p2_id = :dupe"), {"keep": keep_id, "dupe": dupe_id})
    if r.rowcount + r2.rowcount:
        print(f"  H2H rows re-pointed: {r.rowcount + r2.rowcount}")

    # Delete dupe
    await db.execute(text("DELETE FROM player_rolling_stats WHERE player_id = :dupe"), {"dupe": dupe_id})
    await db.execute(text("DELETE FROM player_elo WHERE player_id = :dupe"), {"dupe": dupe_id})
    await db.execute(text("DELETE FROM players WHERE id = :dupe"), {"dupe": dupe_id})
    print(f"  Deleted player {dupe_id}")


async def main():
    from app.db.pool import SessionLocal
    for keep_id, dupe_id in PAIRS:
        async with SessionLocal() as db:
            await merge(db, keep_id, dupe_id)
            await db.commit()
    print("\nAll done.")


asyncio.run(main())
