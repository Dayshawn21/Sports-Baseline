import os

import psycopg
DB = os.environ["DATABASE_URL"]
with psycopg.connect(DB) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, tour, sofascore_id FROM players WHERE name ILIKE '%Tseng%' OR name ILIKE '%Chun%'")
        players = cur.fetchall()
        print("=== PLAYERS ===")
        for p in players:
            print(f"  id={p[0]}  name={p[1]}  tour={p[2]}  sofascore_id={p[3]}")
        if not players:
            print("  (none found)")
        else:
            pids = [p[0] for p in players]
            cur.execute("SELECT player_id, as_of_date, elo, elo_hard, elo_clay, elo_grass FROM player_elo WHERE player_id = ANY(%s) ORDER BY player_id, as_of_date DESC", (pids,))
            rows = cur.fetchall()
            print("\n=== ELO (latest per player) ===")
            seen = set()
            for e in rows:
                if e[0] not in seen:
                    print(f"  player_id={e[0]}  date={e[1]}  elo={e[2]}  hard={e[3]}  clay={e[4]}  grass={e[5]}")
                    seen.add(e[0])
            if not seen:
                print("  (no ELO rows)")
            cur.execute("SELECT player_id, surface, stat_period, win_rate, svc_pts_won, ret_pts_won, hold_pct, break_pct, matches_count, computed_at FROM player_rolling_stats WHERE player_id = ANY(%s) ORDER BY player_id, surface, computed_at DESC", (pids,))
            stats = cur.fetchall()
            print("\n=== ROLLING STATS ===")
            for s in stats:
                print(f"  player_id={s[0]}  surface={s[1]}  period={s[2]}  wr={s[3]}  svc={s[4]}  ret={s[5]}  hold={s[6]}  brk={s[7]}  n={s[8]}  computed={s[9]}")
            if not stats:
                print("  (no stats rows)")
            cur.execute("SELECT m.id, m.match_date, m.tournament, m.surface, m.round, m.tour, m.status, p1.name, p2.name FROM matches m JOIN players p1 ON p1.id=m.p1_id JOIN players p2 ON p2.id=m.p2_id WHERE (m.p1_id = ANY(%s) OR m.p2_id = ANY(%s)) AND m.match_date = CURRENT_DATE ORDER BY m.start_utc", (pids, pids))
            matches = cur.fetchall()
            print("\n=== TODAY MATCHES ===")
            for m in matches:
                print(f"  match_id={m[0]}  date={m[1]}  {m[7]} vs {m[8]}  tournament={m[2]}  surface={m[3]}  round={m[4]}  tour={m[5]}  status={m[6]}")
            if not matches:
                print("  (no matches today)")
