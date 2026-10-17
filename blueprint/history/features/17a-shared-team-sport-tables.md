# Feature: Shared team-sport tables

**From build-plan:** feature 17a
**Status:** completed (2026-10-02)

## Goal

Move the seven cross-sport NFL tables into sport-keyed `sport_*` tables, so
NBA and WNBA (items 20, 21) add rows rather than a third parallel stack. The
old `nfl_*` names stay behind as auto-updatable compatibility views, so every
NFL reader, writer, cron job and test keeps working unchanged until 17b moves
them over.

Schema only. No NFL code, report, page or number changes.

## In scope

- A `sports` registry table, seeded with `nfl` only.
- Migration `0039` renaming, in place (rows, ids, sequences and inbound foreign
  keys all carried by the rename):

  | Old table | New table | Column renames |
  |---|---|---|
  | `nfl_teams` | `sport_teams` | none |
  | `nfl_players` | `sport_players` | `nflverse_id` -> `source_player_id` |
  | `nfl_player_aliases` | `sport_player_aliases` | `nfl_player_id` -> `player_id` |
  | `nfl_games` | `sport_games` | `nflverse_game_id` -> `source_game_id` |
  | `nfl_prop_lines` | `sport_prop_lines` | none |
  | `nfl_game_odds` | `sport_game_odds` | none |
  | `nfl_prop_predictions` | `sport_prop_predictions` | none |

- A `sport` column on all seven: `text NOT NULL`, foreign key to
  `sports(code)`, backfilled `'nfl'`, **no default on the base table**.
- `sport_games.week` relaxed to nullable, with `CHECK (sport <> 'nfl' OR week
  IS NOT NULL)`, because NBA has no weeks.
- One view per old name: `SELECT <the exact pre-17a columns, renamed columns
  aliased back>, sport FROM sport_<x> WHERE sport = 'nfl' WITH LOCAL CHECK
  OPTION`, plus `ALTER VIEW ... ALTER COLUMN sport SET DEFAULT 'nfl'`, so an
  old-code insert that omits `sport` lands as NFL and nothing else can.
- A reversible downgrade that refuses to run if any non-`nfl` row exists.
- Proof in a rolled-back transaction before the migration touches the hosted
  database, then before-and-after report comparison once it is applied.

## Out of scope

- **Changing any NFL code** (repositories, ingest, backtests, services,
  tests). That is 17b.
- **Sport-scoped unique keys.** `team_code`, `source_player_id`,
  `source_game_id` and `alias_name_norm` stay globally unique in 17a, because
  they are the `ON CONFLICT` arbiters old code infers through the views. 17b
  rescopes them to `(sport, ...)`. Until then no second sport can be inserted,
  and the `sports` seed enforces that.
- **Renaming indexes, constraints and sequences.** They keep their `nfl_` names
  until 17b, so this diff stays readable.
- **NFL-only game columns** (`spread_line`, `total_line`, moneylines, `roof`,
  rest, `temp`, `wind`, `espn_event_id`) stay on `sport_games` as nullable
  columns. 17b decides whether they move to an NFL context table.
- **NFL stat and context tables** (`nfl_player_weekly_stats`, snaps, rosters,
  injuries, depth charts, weather, ELO, efficiency, `nfl_player_prop_odds`,
  `nfl_prop_results`). Their columns are genuinely sport-specific; their
  foreign keys follow the rename automatically.
- Tennis tables, the prop pipeline (17c), the API and web shell (17d), and
  NBA itself (item 20). `nba` is not seeded here.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Migration `0039` and its contract test** - write
  `0039_shared_team_sport_tables.py` with the table and column renames as
  module constants, the upgrade (sports table, renames, `sport` backfill,
  foreign keys, `week` check, views with check option and view defaults) and the
  guarded downgrade. Add `tests/test_migration_0039.py`, which loads the
  migration by path and pins, per view, the exact pre-17a column list from the
  live schema read on 2026-10-01 (for example `nfl_games` exposes
  `nflverse_game_id` through `temp` and `wind`, 24 columns, plus `sport`).
  *Not applied to any database in this step.* *Done when:* `pytest` passes,
  including a test that fails if a view drops, adds or renames a pre-17a
  column, and `alembic heads` shows `0039`.

- [x] **Step 2 - Rolled-back proof against the hosted database** - a
  scratchpad script (not committed) that, inside one transaction ending in
  `ROLLBACK`:
  1. runs the `0039` upgrade
  2. calls the real NFL writers through the views: `upsert_team`,
     `upsert_game`, `upsert_player`, `upsert_player_alias`,
     `insert_game_odds_snapshot`, the PrizePicks NFL line insert (inline SQL
     in `app/ingest/prizepicks_nfl.py`, run verbatim) and
     `insert_prop_predictions` (inserting the same row twice must store it
     once)
  3. calls the readers `get_slate_games`, `get_slate_lines` and
     `get_frozen_gradeable_lines` for the current week
  4. confirms an insert with `sport = 'nba'` through a view is rejected
  5. runs the downgrade and diffs the schema against the pre-upgrade dump

  *Done when:* every call succeeds, the schema diff after downgrade is empty,
  and row counts of all seven tables match before and after the rollback.

- [x] **Step 3 - Apply and compare** (applied 2026-10-02 13:06 UTC; see the
  apply note under Notes for the AI) - capture baselines, apply, then re-run.
  **Needs a separate yes before `alembic upgrade head`**: it changes the shared
  hosted database that the GitHub Actions crons and the local `ingest_daily`
  task write to. Apply outside the cron windows (`nfl-prop-lines.yml`:
  Thursday 20:00, Saturday 23:00, Sunday 15:00, Monday 20:00 UTC;
  `nfl-prop-odds.yml`: Wednesday 23:10, Thursday 18:10, Saturday 23:10, Sunday
  12:10 UTC; Tuesday `nfl-ingest.yml`).
  - Baseline, immediately before: the stdout of `nfl_ranking_check --season
    2026`, `nfl_prizepicks_lines`, `nfl_game_line_clv --season 2026`, and the
    JSON of `GET /nfl/slate` for the current week and `GET
    /nfl/model/ranking?season=2026`.
  - Apply `alembic upgrade head`, restart the API.
  - Re-run the same five.

  *Done when:* the three CLI reports are byte-identical to the baseline (timing
  lines excepted), and the two API responses match with numbers within 1e-9
  relative and everything else (ids, strings, flags, order) exact. Step 2 found
  that reading through the views changes the plan, so float averages in
  `get_slate_lines` move by up to 4.9e-15 relative (three runs without the
  migration were identical). Also: `alembic current` reads `0039`, `alembic current` reads `0039`, and the
  catalog shows the seven `sport_*` tables and seven `nfl_*` views. The 27a
  report must also finish in about its baseline time (27 s), not just print the
  same numbers. If a cron
  wrote in between and the numbers moved, re-capture both sides rather than
  explain the difference away.

## Files / areas

- `api/app/db/migrations/versions/0039_shared_team_sport_tables.py` (new)
- `api/tests/test_migration_0039.py` (new)
- No application code changes.

## Data / contracts

**Load-bearing for 17b, 17c and item 20:**

- **`sports(code text PRIMARY KEY, name text NOT NULL)`.** One row per sport,
  `nfl` only for now. Item 20 seeds `nba` (after 17b rescopes keys). 17d's
  registry reads this table.
- **The `sport_*` names and `sport` column** on teams, players, player aliases,
  games, prop lines, game odds and prop predictions. Every later team sport
  writes here with an explicit `sport`; there is no base-table default, so a
  missing sport is an error, not a silent `nfl`.
- **Provider ids are `source_player_id` and `source_game_id`,** unique per
  sport once 17b rescopes them.
- **`sport_games.week` is nullable** for every sport except NFL.
- **Sport-specific stat tables stay per sport** (`nfl_player_weekly_stats`
  now, an NBA stats table in item 20), each referencing the shared ids.

The `nfl_*` views are temporary. 17b drops them; nothing new may be written
against them.

## Testing

- **Test gate:** the migration's column contract is the logic here, so
  `test_migration_0039.py` pins each view's column list and the rename map.
  Existing NFL tests use fake sessions and must pass untouched, which is itself
  evidence that no NFL code changed.
- **Integration evidence:** Step 2's rolled-back run and Step 3's byte-identical
  report and API comparison. There is no local test database; every database
  here is the hosted one, which is why Step 2 runs in a transaction that rolls
  back.
- Final checks: `pytest` from `api/`, and `npm run build` and `npm run test` in
  `web/` (unchanged, run for completeness).

## Notes for the AI

- **Postgres facts this relies on, which Step 2 proves rather than assumes:**
  - `ALTER TABLE ... RENAME` keeps every inbound foreign key (29 of them, from
    16 tables), the
    `id` sequence defaults and all indexes, because they bind by OID.
  - Single-table views with a `WHERE` and plain or aliased columns are
    auto-updatable, support `RETURNING`, and support `INSERT ... ON CONFLICT`,
    inferring the arbiter from the base table's unique indexes. That is why
    17a keeps the single-column unique indexes.
  - A view column default applies to inserts through the view, so the base
    table's `sport` stays default-free.
- **Migrations run in one transaction** (`env.py`), so a failed upgrade leaves
  nothing half-renamed.
- **Keep the migration self-contained.** Do not import from `app/`; an
  applied migration must not change when app code does. The test imports the
  migration, not the reverse.
- **The live database is PostgreSQL 17** (hosted). `NULLS NOT DISTINCT` on
  `uq_nfl_prop_predictions_line_version` survives the rename.
- **Cron safety comes from the views.** Master's code keeps writing `nfl_*`
  before and after the upgrade, so the apply order against merges does not
  matter. A running API should be restarted after the apply in case of cached
  statements.
- `tg.*` in `get_week_team_recent_results` is a CTE star, not a table star; no
  code selects `*` from these tables, so the extra `sport` column on the views
  is invisible to NFL code.
- **Apply note (2026-10-02).** `0039` was applied at 13:06 UTC. Every output
  matched, but the slate-lines query ran past 9 minutes (27 s before) because
  the new `sport` column had no statistics: the planner estimated 1 row for
  `sport = 'nfl'` filters where 272 returned. A manual `ANALYZE` of the seven
  tables (owner approved) fixed it; after it, all five outputs matched the
  baseline (only the request-time `gradedAt` differed, and `/nfl/slate` showed
  no float noise) and 27a took 22 s. `0039` now ends with `ANALYZE` on each
  table, pinned by a test, so other databases get statistics too. The edit
  changes nothing on this database, which was analyzed by hand. Step 2 missed
  this because its single reads ran inside one transaction; a timing check is
  now part of Step 3's done-when.
- **Cron list correction:** `nfl-weather.yml` also runs daily at 14:00 UTC
  against `nfl_games`. It works through the views either way.
- At `/complete`, re-run `/overview`: the data model section names the
  `nfl_*` tables and says revision `0037` (the database is at `0038`).
- No em dashes in the migration docstring or comments.
