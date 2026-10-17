"""
Find duplicate players sharing the same sofascore_id.
Shows ELO and stats coverage so you can decide which to keep.
"""
import os

import psycopg

DB = os.environ["DATABASE_URL"]

with psycopg.connect(DB) as conn:
    with conn.cursor() as cur:

        # Find all sofascore_ids shared by more than one player
        cur.execute("""
            SELECT sofascore_id, array_agg(id ORDER BY id) AS player_ids
            FROM players
            WHERE sofascore_id IS NOT NULL
            GROUP BY sofascore_id
            HAVING count(*) > 1
            ORDER BY sofascore_id
        """)
        groups = cur.fetchall()

        if not groups:
            print("No duplicate sofascore_ids found.")
        else:
            print(f"Found {len(groups)} sofascore_id(s) with duplicates:\n")

            for sofascore_id, pids in groups:
                print(f"  sofascore_id={sofascore_id}")
                for pid in pids:
                    # Player info
                    cur.execute("SELECT id, name, tour FROM players WHERE id = %s", (pid,))
                    p = cur.fetchone()

                    # ELO
                    cur.execute("SELECT elo, as_of_date FROM player_elo WHERE player_id = %s ORDER BY as_of_date DESC LIMIT 1", (pid,))
                    elo = cur.fetchone()

                    # Stats
                    cur.execute("SELECT stat_period, count(*) FROM player_rolling_stats WHERE player_id = %s GROUP BY stat_period", (pid,))
                    stats = cur.fetchall()

                    # Match count
                    cur.execute("SELECT count(*) FROM matches WHERE p1_id = %s OR p2_id = %s", (pid, pid))
                    match_count = cur.fetchone()[0]

                    elo_str  = f"elo={elo[0]} ({elo[1]})" if elo else "NO ELO"
                    stat_str = ", ".join(f"{s[1]} rows [{s[0]}]" for s in stats) if stats else "NO STATS"
                    print(f"    id={p[0]:<6} tour={p[2]:<12} matches={match_count:<4} {elo_str:<30} stats: {stat_str}  name={p[1]}")
                print()
