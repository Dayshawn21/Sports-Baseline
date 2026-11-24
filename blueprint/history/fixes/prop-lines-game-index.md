# Fix: Index sport_prop_lines by game

**Type:** Fix
**Branch:** `fix/prop-lines-game-index` (worktree `.claude/worktrees/sharp-elbakyan-f84efc`, cut from `master` at `502fe488`)
**Status:** completed 2026-11-23

## The problem

`/nhl/slate` took 8.2 s cold on production, alone, on 2026-11-22 (0.55 s on
2026-11-11). Timing each read against Neon on 2026-11-23, `nhl.get_prop_line_counts`
(the `_latest_props` CTE in `api/app/repositories/nhl.py`) took 7.27 s; every other
read took 0.06-0.17 s.

`sport_prop_lines` has no index that starts with `game_id` (it has the pkey,
`(player_id, market, fetched_at)`, `(provider, provider_prop_id)`,
`(segment, market)`, `(odds_type, market)`). `EXPLAIN (ANALYZE, BUFFERS)` for the
5 games of 2026-11-22 shows a Parallel Seq Scan of all 703,343 rows of every sport
(142,208 blocks, about 1.1 GB with `raw_json`) to keep 4,187: 0.56 s with the pages
cached, 7.27 s from Neon storage. It grows with every PrizePicks snapshot, NBA and
NFL included. NBA's `get_prop_line_counts` and `_game_prop_lines` filter the same
table by game the same way (being checked in the NBA slate session).

## The fix

- Migration `0056_prop_lines_game_index`: `CREATE INDEX CONCURRENTLY IF NOT EXISTS
  idx_sport_prop_lines_game ON sport_prop_lines (game_id)` inside Alembic's
  `autocommit_block()`, so the ingest writers are never blocked while it builds;
  downgrade drops it the same way.
- No query, response, ranking or web change. Every game-scoped prop read of every
  sport can use it; the planner decides.

**Must not break:** writes to `sport_prop_lines` (one more index to maintain on
each snapshot insert, small next to the table) and any existing migration.

## Build steps

- [x] **Step 1 - Migration.** Done 2026-11-23 on `master` at `502fe488`
  (70b2 landed first, no migration): `alembic heads` is `0056` alone; the
  `--sql` preview runs the concurrent create between commits; Verify passed
  (1,874 web tests and build, 6,627 API). `api/app/db/migrations/versions/0056_prop_lines_game_index.py`,
  `down_revision = "0055"`. *Done when:* `alembic heads` shows `0056` alone (pass
  a local `-c` ini as AGENTS.md says), `alembic upgrade 0055:0056 --sql` prints
  the concurrent create, and Verify passes.
- [x] **Step 2 - Apply to Neon (separate yes in chat).** Done 2026-11-23:
  `0055` to `0056` in 4.7 s, index valid; the EXPLAIN is a bitmap scan reading
  1,682 blocks (was 142,208); `get_prop_line_counts` 0.07 s (was 7.27 s); NBA's
  `get_prop_line_counts` 0.06 s and `get_date_modelled_lines` 0.39 s. `alembic upgrade head`
  against the shared database, run once. *Done when:* `pg_indexes` lists
  `idx_sport_prop_lines_game`, the same EXPLAIN shows an index scan on it for the
  2026-11-22 games, and the scratchpad timing probe puts `get_prop_line_counts`
  under 0.3 s.
- [x] **Step 3 - Docs.** Done 2026-11-23: no command or startup needs `0056`,
  so no doc line changed; Verify passed in step 1 with the same tree. `AGENTS.md`/`docs/commands.md` note the migration only if
  a command line needs it (`0056` is required by nothing at startup).
  *Done when:* Verify passes.

## Verify

- Verify: `npm --prefix web run verify && cd api && python -m pytest`.
- No new logic, so no new unit test; the evidence is the EXPLAIN plan and timing.
- After deploy (outside this fix): a cold `GET /nhl/slate` answers in under about
  1 s, and `/nba/slate` and `/nba/slate/gaps` re-timed for the NBA session.

## Out of scope

- Snapshotting the NHL or NBA slate, or changing what the prop count counts.
- Pruning or partitioning old `sport_prop_lines` rows.

## Notes for the AI

- Migrations run manually, one command at a time; `alembic.ini` is untracked.
- The index applies to the shared Neon database production reads, so the code
  merge does not need to wait for it, but step 2 needs its own yes.
- Interview guide: the measured 7.3 s to index-scan result is a fair example;
  update it on disk at `/complete` if it exists, never stage it.
