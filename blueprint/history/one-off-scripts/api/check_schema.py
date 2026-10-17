import os

import psycopg
DB = os.environ["DATABASE_URL"]
with psycopg.connect(DB) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.referential_constraints rc
              ON tc.constraint_name = rc.constraint_name
            JOIN information_schema.key_column_usage ccu
              ON rc.unique_constraint_name = ccu.constraint_name
            WHERE ccu.table_name = 'players'
              AND tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_name
        """)
        print("Tables with FK to players:")
        for row in cur.fetchall():
            print(f"  {row[0]}.{row[1]}")
