# Feature: NFL on the shared tables

**From build-plan:** feature 17b
**Status:** completed (2026-10-02)

## Goal

Move every NFL reader and writer off the `nfl_*` compatibility views and onto
the `sport_*` tables 17a created, scope the four provider unique keys by sport,
then drop the views. After 17b a second sport can insert teams, players, games
and aliases without colliding with NFL (an NBA `ATL` beside the NFL `ATL`), and
nothing reads or writes the old names.

Plumbing only. No NFL report, page, number, ordering or timing changes, and the
proof is the same before-and-after comparison 17a used.

## In scope

- **Migration `0040` (additive, safe for master's code):**
  - sport-scoped unique indexes beside the global ones:
    `(sport, team_code)`, `(sport, source_player_id)`, `(sport, source_game_id)`,
    `(sport, alias_name_norm)`
  - rename the `nfl_`-named indexes, constraints and `id` sequences on the seven
    `sport_*` tables to `sport_` names (17a deferred this)
  - leaves the views and global indexes in place, so master's code and the
    GitHub crons keep working through the views
- **Repository and ingest SQL** (`app/repositories/nfl.py`, the inline
  PrizePicks insert in `app/ingest/prizepicks_nfl.py`):
  - table names `sport_*`, columns `source_player_id`, `source_game_id`,
    `player_id` (aliases)
  - **every reference to a `sport_*` table carries `<alias>.sport = 'nfl'`**,
    exactly as the views did (see Notes for why this rule and why a literal)
  - every insert names `sport` explicitly; every upsert's `ON CONFLICT` names
    the scoped key, e.g. `ON CONFLICT (sport, team_code)`
- **Tests:** `tests/test_nfl_repository.py` SQL assertions follow the new
  names, plus a static guard test that no `app/` file names an old table or
  renamed column.
- Comments and docstrings that name the old tables (`nfl_resolution.py`,
  `nfl_names.py`, `nfl_game_line_clv.py`, `props_provider.py`,
  `schemas/nfl.py`, three `nflverse_*` ingest modules).
- **Migration `0041` (destructive):** drop the seven views and the four global
  unique indexes. Reversible: the downgrade recreates both, and refuses to
  run while any non-`nfl` row exists (as `0039`'s does), since a second sport's
  rows could violate the global indexes.
- Proof: a rolled-back run with `0041` applied, a before-and-after comparison of
  the five 17a outputs, then the `0041` apply.

## Out of scope

- **NFL-only game columns stay on `sport_games`** (`spread_line`,
  `total_line`, moneylines, `roof`, rest, `temp`, `wind`, `espn_event_id`).
  Decided here: they are nullable, NBA leaves them NULL, and moving them to an
  NFL context table would rewrite every game query for no behavior change.
  Revisit only if item 20 finds a column it needs under the same name.
- **Python names.** `upsert_player(nflverse_id=...)`, `game_key`,
  `player_key` and the `nfl_repo` module keep their names; only SQL changes.
  `app/repositories/nfl.py` is the NFL repository over shared tables.
- **Parameterizing by sport.** The filter is the literal `'nfl'`. 17c
  parameterizes the prop pipeline (lines, predictions, ranking, loaders).
- **Moving the inline PrizePicks insert into the repository.** 17c reworks
  PrizePicks league selection per sport and owns that move.
- NFL stat and context tables (`nfl_player_weekly_stats` and the rest), tennis,
  `bets.sport`, routes and nav (17d), and seeding `nba` (item 20).
- Backtests and services: they hold no SQL for these tables (checked
  2026-10-02), so they change only through the repository and are proved by the
  report comparison.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Migration `0040` and its test** - write
  `0040_sport_scoped_keys.py`: the four scoped unique indexes, and the
  index, constraint and sequence renames as a module-level map read from the
  live catalog first (`pg_indexes`, `pg_constraint`, `pg_class` for the seven
  tables; record the list in the migration). Downgrade reverses both. Add
  `tests/test_migration_0040.py` pinning the scoped key columns and that every
  renamed object starts `nfl_` and lands `sport_`. *Not applied in this step.*
  *Done when:* `pytest` passes and `alembic heads` shows `0040`.

- [x] **Step 2 - Apply `0040`** (applied 2026-10-02 13:44 UTC) - **needs a separate yes**; it changes the
  shared hosted database. Additive only: master's code is unaffected, so cron
  windows do not matter, but apply outside them anyway. *Done when:*
  `alembic current` reads `0040`; the catalog shows the four scoped indexes
  and no `nfl_`-named index, constraint or sequence on a `sport_*` table; and
  one run of `nfl_ranking_check --season 2026` matches its pre-apply stdout.

- [x] **Step 3 - Writers** - everything in the repository above
  `write_red_zone_usage` (`insert_player_prop_odds_snapshot`,
  `insert_game_odds_snapshot`, `get_latest_game_odds`,
  `insert_game_weather_snapshot`, `upsert_team`, `upsert_game`,
  `upsert_player`, `upsert_weekly_stat`), plus `set_line_linkage`,
  `upsert_player_alias`, `insert_prop_predictions` and the PrizePicks insert in
  `prizepicks_nfl.py`. Explicit `sport` on inserts into `sport_*`, scoped
  `ON CONFLICT`. Update their tests. *Done when:* `pytest` passes and each
  upsert's test asserts the `sport_*` table, the `sport` value `'nfl'` and the
  scoped conflict target.

- [x] **Step 4 - Stat-table writers and the readers among them** - repository
  `write_red_zone_usage` through `replace_team_efficiency` (lines 370-780):
  the roster, snap, red-zone, ELO and efficiency writers, and `get_elo_games`,
  `get_game_line_games`, `get_game_line_clv_games`, `get_team_efficiency`.
  The `nfl_*` stat targets stay; only references to players, teams and games
  move, each with the sport filter. *Done when:* `pytest` passes with the
  existing "never inserts a player or game" assertions rewritten to the new
  names.

- [x] **Step 5 - Schedule, resolution and slate readers** - repository lines
  780-1625: `get_team_schedule` through `get_week_team_games`, including
  `get_player_candidates`, `get_game_index`, `get_player_aliases`,
  `get_current_week`, the baseline and ELO readers, and `get_game`.
  *Done when:* `pytest` passes.

- [x] **Step 6 - Slate lines, grading and profile readers** - repository lines
  1625 to the end: `_slate_line_rows` through `get_player_game_rows`, except
  the writers Step 3 moved. Then the comment and docstring
  updates in the files listed under In scope. *Done when:* `pytest` passes and
  `grep` for the seven old table names, `nflverse_id`, `nflverse_game_id` and
  `nfl_player_id` in `app/` SQL finds nothing.

- [x] **Step 7 - Guard test and outputs unchanged** (2026-10-02: all five outputs
  identical across 6 branch and 5 master runs; timing matched side by side, but
  `get_slate_lines` stalls 10-20x intermittently on master as well as the branch,
  so the 20% bound was judged on matched runs, owner approved; follow-up for
  `/debug` after 17b) - add
  `tests/test_no_nfl_view_names.py`: scans `app/**/*.py` (migrations excluded)
  and fails on any of the seven old table names or three old column names, so a
  later change cannot quietly write against a dropped view. Then, with `0040`
  applied and the views still present:
  - baseline on master: stdout of `nfl_ranking_check --season 2026`,
    `nfl_prizepicks_lines`, `nfl_game_line_clv --season 2026`, and the JSON of
    `GET /nfl/slate` (current week) and `GET /nfl/model/ranking?season=2026`,
    each timed
  - the same five on the branch

  *Done when:* the guard test passes (and fails when an old name is
  reintroduced, checked once by hand); the CLI reports are byte-identical
  (timing lines excepted); the API responses match exactly except
  request-time fields such as `gradedAt`; and no output takes more than 20%
  longer than its baseline (27a ran 22 s after 17a). If a cron wrote in
  between, re-capture both sides.

- [x] **Step 8 - Migration `0041` and a rolled-back proof** (2026-10-02 14:42 UTC, all checks passed) - write
  `0041_drop_nfl_views.py` (drop the views, drop the four global unique
  indexes; guarded, reversible downgrade) and `tests/test_migration_0041.py`.
  Then a scratchpad script (not committed) that, in one transaction ending in
  `ROLLBACK`:
  1. runs the `0041` upgrade
  2. calls every Step 3 writer and the readers behind the five outputs
     (`get_slate_games`, `get_slate_lines`, `get_frozen_gradeable_lines`,
     `get_gradeable_prop_lines`, `get_game_line_clv_games`,
     `get_player_profile`) for the current week
  3. inserts `sports ('nba')` and an `nba` team `ATL`, player, alias and game
     reusing NFL provider ids, which must succeed, then confirms the NFL readers
     return the same rows as in 2
  4. runs the `0041` downgrade with the `nba` rows removed, and diffs the schema
     against the pre-upgrade dump

  *Done when:* every call succeeds, the NFL reads in 2 and 3 are equal, the
  downgrade schema diff is empty, and row counts match after the rollback.

- [x] **Step 9 - Apply `0041`, immediately before `/complete`** (applied
  2026-10-02 15:05 UTC; all five outputs matched Step 7; 27a 17.2 s; push must
  follow before Saturday 14:00 UTC, else `alembic downgrade 0040`) - **needs a
  separate yes, and the merge and push must follow in the same sitting.** Once
  the views are gone, master's code (the GitHub crons) fails until the branch
  is pushed. Apply outside the cron windows (`nfl-weather.yml` daily 14:00 UTC;
  `nfl-ingest.yml` Tuesday 15:00; `nfl-prop-lines.yml` Thursday 20:00, Saturday
  23:00, Sunday 15:00, Monday 20:00; `nfl-prop-odds.yml` Wednesday 23:10,
  Thursday 18:10, Saturday 23:10, Sunday 12:10), with at least two hours clear.
  The local `ingest_daily` task runs the checked-out branch, so it is fine on
  either the branch or merged master. **If the push is declined, run `alembic
  downgrade 0040` before stopping.** Restart the API after the apply.
  *Done when:* `alembic current` reads `0041`; the catalog shows no `nfl_`
  view and none of the four global unique indexes; the five Step 7 outputs
  re-run on the branch match Step 7's branch side within the same timing
  bound (if a cron wrote since Step 7, re-capture a fresh branch run just
  before the apply and compare to that).

## Files / areas

- `api/app/db/migrations/versions/0040_sport_scoped_keys.py` (new)
- `api/app/db/migrations/versions/0041_drop_nfl_views.py` (new)
- `api/app/repositories/nfl.py` (SQL only)
- `api/app/ingest/prizepicks_nfl.py` (the one inline insert)
- Comments only: `app/core/nfl_resolution.py`, `app/core/nfl_names.py`,
  `app/core/nfl_game_line_clv.py`, `app/services/nfl/props_provider.py`,
  `app/schemas/nfl.py`, `app/ingest/nflverse_pbp.py`,
  `app/ingest/nflverse_snap_counts.py`, `app/ingest/nflverse_team_efficiency.py`
- `api/tests/test_nfl_repository.py`, `api/tests/test_migration_0040.py`,
  `api/tests/test_migration_0041.py`, `api/tests/test_no_nfl_view_names.py`
  (new tests)
- No web, router, service or backtest changes.

## Data / contracts

**Load-bearing for 17c, 17d and item 20:**

- **Provider keys are unique per sport:** `sport_teams (sport, team_code)`,
  `sport_players (sport, source_player_id)`, `sport_games (sport,
  source_game_id)`, `sport_player_aliases (sport, alias_name_norm)`. These are
  the `ON CONFLICT` targets every sport's ingest uses.
- **A sport's rows are reached through its own `sport` filter,** never through
  another sport's ids. Item 20 writes NBA rows with `sport = 'nba'` into the
  same tables, and NFL queries must not see them.
- **The `nfl_*` names for the seven shared tables no longer exist** after
  `0041`, and the guard test keeps them out of `app/`.
- **NFL-only columns stay on `sport_games`,** nullable for other sports.
- Unchanged: `sport_prop_predictions`' unique key (scoped through
  `prop_line_id`), `sport_games.week`'s NFL check, the `sports` table.

## Testing

- **Test gate:** the migrations' contracts (`test_migration_0040.py`,
  `test_migration_0041.py`), every rewritten writer's table, sport and conflict
  target (`test_nfl_repository.py`, fake sessions as today), and the
  static guard. Existing NFL tests that do not assert SQL must pass untouched.
- **Integration evidence:** Step 7's comparison (new code reads the same as old
  code, at the same speed) and Step 8's rolled-back run (nothing uses the views,
  and a second sport does not collide or leak into NFL reads). There is no
  local test database; every database is the hosted one.
- Final checks: `pytest` from `api/`; `npm run build` and `npm run test` in
  `web/` (unchanged, run for completeness).

## Notes for the AI

- **Why every `sport_*` reference gets the filter, even across a foreign key.**
  A filter on a row reached through a sport-scoped foreign key is redundant, but
  it reproduces exactly what the views did, so plans and results stay what 17a
  measured. Deciding per join which filters are "needed" is where a leak to NBA
  rows would hide. Uniform is auditable.
- **Why the literal `'nfl'`, not a bind parameter.** The views inlined the
  literal, so the planner used the column's statistics directly. A bind
  parameter can switch to a generic plan after repeated prepared executions;
  17a already saw a slate plan go from 27 s to 9 minutes on a bad estimate. 17c
  can parameterize once it re-measures.
- **Why two migrations.** New code needs the scoped `ON CONFLICT` targets
  (`0040`) before it runs anywhere; master's code needs the views and global
  arbiters until the push. `0040` is safe for both, `0041` only for the new
  code. Postgres infers an arbiter by its exact column list, so the global and
  scoped unique indexes coexist and each code version picks its own.
- **Index renames are safe for old code:** no `ON CONFLICT ON CONSTRAINT
  <name>` exists in `app/` (checked 2026-10-02); every conflict target is a
  column list.
- `ALTER SEQUENCE ... RENAME` is safe: the `id` default's `nextval` binds by
  OID.
- **Keep migrations self-contained;** do not import from `app/`.
- The PrizePicks insert in `prizepicks_nfl.py` runs from the
  `nfl-prop-lines.yml` cron. After `0041` it must be on origin/master, which
  is why Step 9 is tied to the push.
- `test_migration_0039.py` keeps the old names; it pins history and is excluded
  from the guard (the guard scans `app/`, not `tests/`).
- At `/complete`, re-run `/overview`: the data model still lists the `nfl_*`
  tables and revision `0037`.
- No em dashes in migrations, comments or docs.

## Outcome notes

- **Deviation: `upsert_player_alias`'s parameter is `player_id`,** not
  `nfl_player_id`, to match the column. Every caller passes it positionally.
  `upsert_player(nflverse_id=...)` kept its name as specced; the guard bans
  only the qualified column form (`p.nflverse_id`).
- **The guard regex** skips names preceded by `.` so the module path
  `app.ingest.nfl_prop_predictions` passes, and leaves the NFL-only stat tables
  (`nfl_player_weekly_stats`, `nfl_team_elo` and the rest) alone.
- **`get_slate_lines` stalls intermittently, on master too.** In-process 27a
  runs took 17-24 s normally, but 2 of 5 branch runs and 1 of 5 master runs
  spent 33-99 s per call in `get_slate_lines` (master's worst run: 240 s).
  Every output stayed identical. Not caused by 17b; a `/debug` follow-up
  (compare `EXPLAIN ANALYZE` of a slow and a fast run) is recommended. The
  model page's 27a request has a 90 s timeout, so a stall can fail it.
- **Applied:** `0040` 2026-10-02 13:44 UTC, `0041` 15:05 UTC. After `0041`,
  the three reports and the slate JSON were byte-identical to Step 7 and the
  ranking response differed only in `gradedAt`; 27a took 17.2 s.
- **The rolled-back proof (Step 8)** also showed the aliases table is empty in
  the hosted database, so the NBA alias collision reused the proof's own alias.
- **`/overview` was not re-run in this commit,** to keep the merge and push
  ahead of Saturday's crons. Run it next: the overview's data model still lists
  `nfl_*` tables and revision `0037`.
