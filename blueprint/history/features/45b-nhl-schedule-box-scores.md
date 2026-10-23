# Feature: NHL schedule and box-score ingest

**From build-plan:** feature 45b (parent 45)
**Status:** complete (2026-10-23)

## Goal

Load NHL teams, games and per-game skater and goalie box scores into the
database from the NHL's own free APIs, as 45a decided: seasons 2023-24
through 2026-27 as a backfill (a prior, a development, a holdout and the
live season for a later projection harness), and a daily refresh that keeps
schedule, finals and box scores current. This is 20b's job for NHL, on the
shared `sport_*` tables from day one, so item 45 adds no parallel stack.
45c (prop lines), 45d (odds) and 45e (pages) all link to the rows this
feature writes.

## In scope

- **Migration `0049`:** seed `('nhl', 'NHL')` in `sports`; add nullable
  `sport_games.end_period` (`REG`, `OT`, `SO`; NHL only); create
  `nhl_skater_game_stats` and `nhl_goalie_game_stats` with 45a's columns.
- **Shared week helper:** move `opening_night` and the Monday-to-Sunday week
  rule out of `app/core/nba_season.py` into a sport-neutral
  `app/core/regular_season_week.py`; NBA keeps its names as re-exports, so
  no NBA caller or test changes.
- **Pure season logic** in `app/core/nhl_season.py`: season in progress for a
  date, the NHL season id (`20262027`) for a start year, NHL `gameType` to
  `game_type`, web API states to `status` and `end_period`.
- **Parsers** for the web API weekly schedule (`/v1/schedule/{date}`) and the
  stats REST per-game reports (`skater/summary`, `skater/realtime`,
  `skater/faceoffwins`, `goalie/summary`) into frozen dataclasses.
- **Repository** `app/repositories/nhl.py`: batched upserts for teams, games,
  players, skater rows and goalie rows, every `sport_*` statement carrying the
  literal `'nhl'`.
- **Ingest command** `python -m app.ingest.nhl_api`:
  - `--season 2023` backfills one season (whole schedule plus every REG and
    PST box score)
  - no `--season`: the season in progress, the whole schedule plus box
    scores for games dated in the last `--days-back` days (default 3)
  - `--dry-run` fetches, parses and counts without writing
- **Backfill** 2023-24, 2024-25, 2025-26 and the 2026-27 season to date.
- **Daily workflow** `.github/workflows/nhl-ingest.yml`, September through
  June, and the NHL line in `AGENTS.md`'s ingest commands.

## Out of scope

- PrizePicks NHL lines, the `TB` to `TBL` map and player linking (45c).
- Game odds and the Odds-API.io team-name map (45d).
- `SPORTS`, `SPORT_PAGES`, `SPORT_STATUS`, any web or API route (45e).
- Injuries and probable goalies (45f).
- A `SportPropSource`, frozen predictions, finished-week logic, projections
  (later 45 sub-items). `end_period` is stored now; nothing reads it yet.
- Preseason (`gameType` 1), All-Star and any other game type: never stored.
- The sportsdataverse fallback source. 45a named it; it is built only if the
  NHL APIs fail from GitHub's runners (a later `/fix`).
- Conference and division on `sport_teams` (left NULL, as for NBA).
- Seasons before 2023-24.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Migration `0049`** - seed `nhl`, add `sport_games.end_period`
  with its checks, create both stat tables (Data / contracts). Downgrade drops
  both tables, drops the column, then deletes the `nhl` row; if any `sport_*`
  row still references `nhl` the delete fails loudly rather than cascading.
  Run each alembic command **separately** (never chained; see the 20b
  incident) with `-c` pointing at the local `alembic.ini`. *Done when:*
  - `upgrade head` reaches `0049`; a separate `downgrade -1` then a separate
    `upgrade head` round-trip cleanly
  - `SELECT code FROM sports` lists `nfl`, `nba`, `nhl`
  - NFL and NBA row counts in the seven `sport_*` tables and
    `nba_player_game_stats` are identical before and after
  - inserting an NFL or NBA game with a non-NULL `end_period`, or an NHL game
    with `end_period = 'XX'`, is rejected by a check constraint (checked in a
    rolled-back transaction)
- [x] **Step 2 - Shared week and NHL season logic** -
  `app/core/regular_season_week.py` (`opening_night`, `regular_season_week`),
  `app/core/nba_season.py` re-exporting them as `opening_night` and
  `nba_week`, and `app/core/nhl_season.py`, plus
  `tests/test_regular_season_week.py` and `tests/test_nhl_season.py`.
  *Done when:* existing NBA season tests pass unchanged, and new tests pass for:
  - `current_nhl_season`: 2026-10-23 gives 2026, 2027-04-01 gives 2026,
    2026-07-15 gives 2025 (a new season counts from August; 2026-27 opened
    2026-09-29)
  - `season_id(2026)` is `"20262027"`
  - `gameType` 2 to `REG`, 3 to `PST`; 1, 4 and unknown types to None
  - `game_status(gameState, gameScheduleState)`: `OFF` or `FINAL` with `OK`
    gives `completed`; `PPD` gives `postponed`; `CNCL` gives `canceled`;
    `FUT`, `PRE`, `LIVE`, `CRIT` give `scheduled`
  - `end_period` is `REG`, `OT` or `SO` only for a completed game, else None
  - weeks: 2024-25's Prague opening (Friday 2024-10-04) puts week 1 at
    2024-09-30 to 2024-10-06; a date in the 4 Nations break week still gets
    its calendar week number (weeks skip, never renumber); a date before
    week 1 raises `ValueError`
- [x] **Step 3 - Parsers** - `app/ingest/nhl_api.py` holding `NhlGame`,
  `NhlSkaterGame`, `NhlGoalieGame`, `parse_schedule_week`,
  `parse_skater_reports` (joins the three skater reports on
  `(playerId, gameId)`) and `parse_goalie_summary`, plus
  `tests/test_nhl_api.py` with small inline JSON fixtures trimmed from real
  responses. *Done when:* tests pass for:
  - a regulation, an overtime and a shootout final parse with UTC
    `start_utc`, Eastern `game_date`, scores, `status` and `end_period`
  - a future game parses with NULL scores and `end_period`; a postponed
    game parses as `postponed`
  - preseason and All-Star games are skipped and counted by type
  - team name is `placeName` plus `commonName` (`Montréal Canadiens`)
  - a skater present in `summary` but missing from `realtime` or
    `faceoffwins` keeps those columns NULL, never 0
  - time on ice parses from seconds (`1189.0` to 1189)
  - goalie `decision` is `W`, `L` (`losses`), `O` (`otLosses`) or None;
    `started` follows `gamesStarted`
  - `homeRoad` `H`/`R` sets `is_home`; a row missing `playerId` or `gameId`
    is skipped and counted
- [x] **Step 4 - Repository** - `app/repositories/nhl.py` with `upsert_team`,
  `upsert_games`, `upsert_players`, `upsert_skater_games`,
  `upsert_goalie_games` (one `executemany` per 1,000-row chunk, ids read back
  in one query), mirroring `app/repositories/nba.py`. A game upsert updates
  date, start, week, game type, teams, scores, status and `end_period`, so a
  rescheduled game moves weeks. *Done when:* every `sport_*` statement in the
  diff inserts or filters the literal `'nhl'`; `tests/test_no_nfl_view_names.py`
  and the full `pytest` stay green. Exercised for real in Step 5.
- [x] **Step 5 - Fetch, CLI and the live season** - `run(season, days_back,
  dry_run)` and the CLI in `app/ingest/nhl_api.py`: one schedule call dated
  October 15 of the start year reads the season's `regularSeasonStartDate`
  and `playoffEndDate`; page the weekly schedule from the first through the
  second by `nextStartDate`; fetch the four stats reports per calendar month
  (`limit=-1`, game types 2 and 3) for the backfill, or for the `--days-back`
  window; raise if any report's `total` differs from the rows returned; then
  upsert in one transaction (roll back on any error). Stat rows are stored
  only for games the parsed schedule marks `completed`; rows for any other or
  unknown game are skipped and counted by reason. Every HTTP call has a 20 s
  timeout and tenacity retry on transport errors and 5xx. *Done when:*
  - the default run with `--dry-run` prints game, skater and goalie counts
    and the skip counts, and writes nothing
  - the default run stores the 2026-27 schedule: 1,344 `REG` games (45a's
    count), no preseason game, `week` 1 holding exactly the games of
    2026-09-29 to 2026-10-04 (week 1 spans Monday 2026-09-28 to Sunday
    2026-10-04), and box scores for completed games of the last 3 days
  - `--season 2026` loads every completed 2026-27 game's box scores to date
  - a second identical run leaves every NHL row count unchanged
- [x] **Step 6 - Backfill 2023-24 to 2025-26 and integrity checks** - run
  `--season 2023`, `2024`, `2025` one at a time. *Done when:*
  - each season stores its full `REG` schedule (2024-25 and 2025-26: 1,312
    each, per 45a; 2023-24: report the count) plus every `PST` game, all
    completed `REG` and `PST` games `completed`
  - 2025-26 weeks 19 and 20 (Olympic break) have no games; 2024-25 week 20
    (4 Nations) has none; 2024-25 week 1 holds the 2 Prague games
  - SQL checks, each expecting 0 rows (any exception is listed in the build
    notes with its reason):
    - a completed game with no skater row or no goalie row for either team
    - a completed non-`SO` game where a team's summed skater goals differ
      from its score; for `SO` games the winner's score minus 1
    - a stat row pointing at a non-NHL game, player or team
  - game `2025021018` stores CAR 5, PIT 4, `end_period = 'SO'`, skater goals
    4 and 4, and Andersen 24 saves on 28 shots
  - NFL and NBA counts in the seven `sport_*` tables are unchanged
- [x] **Step 7 - Daily workflow and docs** - `.github/workflows/nhl-ingest.yml`
  (cron `45 9 * 1-6,9-12 *`, after the latest West Coast final, plus
  `workflow_dispatch`; the same setup steps as `nba-ingest.yml`; runs
  `python -m app.ingest.nhl_api`; `contents: read`, `DATABASE_URL` only), and
  the NHL line in `AGENTS.md`'s ingest commands. *Done when:* the workflow
  parses as YAML with the cron and command shown; the exact command succeeds
  locally against the database; `AGENTS.md` lists `python -m
  app.ingest.nhl_api [--season 2025] [--days-back 3] [--dry-run]`; Verify
  passes. Runner reachability of `api.nhle.com` and `api-web.nhle.com` is
  recorded as unverified until the first post-push run.

## Build evidence

### Step 1 (2026-10-23, approved)

- Branch: `feature/45b-nhl-schedule-box-scores`.
- Added `0049_nhl_games_and_box_scores.py`; local ignored `api/alembic.ini`
  supplies the migration path and logging configuration, with no credentials.
- Ran each command separately from `api/` with `.venv/Scripts/python.exe -m`:
  `alembic -c alembic.ini upgrade head`, then
  `alembic -c alembic.ini downgrade -1`, then
  `alembic -c alembic.ini upgrade head`. Revisions were 0048, 0049, 0048,
  0049. The shared database is now at 0049; sports are `nba`, `nfl`, `nhl`.
- Checked counts before migration, after upgrade, after downgrade and after
  re-upgrade. All stayed identical:

  | Table | NFL | NBA |
  |---|---:|---:|
  | `sport_teams` | 32 | 30 |
  | `sport_players` | 2,738 | 952 |
  | `sport_player_aliases` | 0 | 0 |
  | `sport_games` | 3,935 | 5,239 |
  | `sport_prop_lines` | 123,373 | 66,723 |
  | `sport_game_odds` | 10,170 | 3,455 |
  | `sport_prop_predictions` | 76,390 | 65,289 |
  | `nba_player_game_stats` | n/a | 107,872 |

- Live database checks confirmed both empty stat tables, their unique keys,
  indexes and FK deletion policies. NFL/NBA game inserts with `OT` were
  rejected by `ck_sport_games_nhl_end_period`; NHL `XX` was rejected by
  `ck_sport_games_end_period`. NHL `REG`, `OT`, `SO` and NULL were accepted.
  All synthetic rows were rolled back.
- A synthetic NHL team/game reference also blocked the migration's sport
  deletion with a foreign-key violation. The probe's DDL was rolled back;
  the actual empty-schema downgrade separately removed both tables, the
  column and NHL registration cleanly.
- Verify passed: `npm --prefix web run verify && cd api && python -m pytest`
  with the API venv on PATH. Web: 815 tests plus typecheck/build; API: 3,764
  tests. Vite reported its large-chunk warning; pytest reported one
  Starlette/anyio deprecation warning.
- Local verification helper and baseline: ignored `output/45b-step1/`.
  No ingest or provider changes yet, so the interview guide is unchanged.
- Owner approved Step 1 and proceeding to Step 2. No checkpoint commit.

### Step 2 (2026-10-23, approved)

- Extracted `opening_night` and the unchanged week calculation into
  `app/core/regular_season_week.py`; NBA re-exports the same public names,
  so no existing caller or NBA test changed.
- Added pure NHL season/id, stored game type, status and end-period helpers
  in `app/core/nhl_season.py`. Postponement/cancellation overrides a final
  state; completion requires `OK`. Unknown or unfinished end periods stay NULL.
- Added `tests/test_regular_season_week.py` for opening dates, Monday/Sunday
  boundaries, the 4 Nations break and pre-opening rejection, and
  `tests/test_nhl_season.py` for August rollover, season ids, excluded game
  types, schedule states and completed-only REG/OT/SO values.
- Focused command from `api/`: `.venv/Scripts/python.exe -m pytest
  tests/test_nba_season.py tests/test_regular_season_week.py
  tests/test_nhl_season.py -q`: 76 passed, including 56 new cases.
- Verify passed with the API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`.
  Web: 815 tests plus typecheck/build; API: 3,820 tests. The same Vite
  large-chunk and Starlette/anyio deprecation warnings remain.
- Local review artifacts: ignored `output/45b-step2.diff` and
  `output/45b-step2-verify.log`. `git diff --check` passed.
- No database or provider calls in this step. Owner approved Step 2 and
  proceeding to parsers; no checkpoint commit.

### Step 3 (2026-10-23, approved)

- Added frozen `NhlGame`, `NhlSkaterGame` and `NhlGoalieGame` dataclasses
  and typed schedule/report inputs in `app/ingest/nhl_api.py`.
- Weekly schedules preserve official scores and REG/OT/SO outcomes, derive
  Eastern dates from aware UTC starts, and count excluded game types.
  Weeks remain NULL until Step 5 has fetched the season's opening night.
- Skater reports left-join on both player id and game id. Missing columns
  or supplemental rows remain NULL; real zeroes stay zero. Goalie rows use
  gamesStarted and W/L/O decision counts. Missing ids and invalid homeRoad
  values are skipped with counts rather than assigned to a player or side.
- Added 32 tests in `tests/test_nhl_api.py`, with inline JSON trimmed from
  the NHL's 2026-03-10 schedule and per-game report responses. Variants
  cover future/postponed/canceled games, excluded game types, accented
  names, Eastern dates, missing fields/reports, keyed joins, goalie
  decisions and frozen outputs.
- Focused command from `api/`: `.venv/Scripts/python.exe -m pytest
  tests/test_nhl_api.py -q`: 32 passed.
- Parsed the complete cached real week: 56 games, 36 skater rows and 2
  goalie rows, zero skips. Game 2025021018 retains CAR 5, PIT 4, SO;
  skater goals sum to 4 and 4, and Andersen has 24 saves on 28 shots.
  Raw local responses are in ignored `output/45b-step3/`.
- Verify passed with the API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`.
  Web: 815 tests plus typecheck/build; API: 3,852 tests. Existing Vite
  large-chunk and Starlette/anyio deprecation warnings remain.
- Local review artifacts: ignored `output/45b-step3.diff` and
  `output/45b-step3-verify.log`. `git diff --check` passed.
- No database writes, repository, fetch loop or CLI in this step.
  Owner approved Step 3 and proceeding to the repository; no checkpoint commit.

### Step 4 (2026-10-23, approved)

- Added `app/repositories/nhl.py` with `upsert_team`, `upsert_games`,
  `upsert_players`, `upsert_skater_games` and `upsert_goalie_games`, plus
  `NhlPlayerRow`. Mirrored NBA's batching pattern without any NBA imports.
- Every shared-table INSERT contains literal `'nhl'`; both id readbacks
  filter literal `'nhl'`. Games and players use sport-scoped conflict keys.
- Game conflicts refresh season, date, start, week, game type, teams,
  scores, status and end_period. Player conflicts preserve an existing
  position if the incoming position is NULL. Historical teams stay on the
  stat rows; the ingest caller will choose each player's latest loaded team.
- Games, players and both stat tables use executemany chunks of up to
  1,000 rows. Game/player ids are read back in one query per call. Stat
  upserts refresh all supplied stats, team ids and fetched_at.
- Focused command from `api/`: `.venv/Scripts/python.exe -m pytest
  tests/test_no_nfl_view_names.py -q`: 2 passed. Repository import passed.
- Verify passed with the API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`.
  Web: 815 tests plus typecheck/build; API: 3,852 tests. Existing Vite
  large-chunk and Starlette/anyio deprecation warnings remain.
- Local review artifacts: ignored `output/45b-step4.diff` and
  `output/45b-step4-verify.log`. `git diff --check` passed.
- No database calls were made in this step. Repository SQL is exercised
  by the actual loads and repeat-run checks in Steps 5-6, per the spec.
  Owner approved Step 4 and proceeding to fetch/CLI/live load; no checkpoint commit.

### Step 5 (2026-10-23, approved)

- Added sequential HTTP fetching, CLI and `run` to `app/ingest/nhl_api.py`.
  Every request has a 20 s timeout; tenacity retries transport errors and
  5xx three times. HTTP 4xx exits with a clear error. The October 15
  metadata seeds the season bounds; weekly schedule pages follow nextStartDate.
- Live-source adjustment: 2027-04-06 is the last currently published week,
  and omits nextStartDate because the 2026-27 playoffs are not published.
  The first dry run caught this without writing. Paging now ends on that
  terminal response and rejects non-advancing dates. A focused test pins it.
- Stats fetches use calendar-month windows, `limit=-1`, the exact season
  id and game types 2/3. Every report's total must equal its returned row
  count. Selection counts unknown/nonfinal games, wrong teams and rows
  outside the requested dates. Dry runs import no database code; real
  writes share one transaction. Latest player metadata uses game start time.
- Added 13 tests for month boundaries, truncation, terminal paging,
  completed-game selection, latest-team ordering, retry rules and invalid
  inputs. Focused `tests/test_nhl_api.py -q`: 45 passed.
- `/check` for this step ran the real CLI from `api/`, using
  `.venv/Scripts/python.exe -m app.ingest.nhl_api`:

  | Check | Observed result |
  |---|---|
  | `--dry-run` | 1,344 games, 900 skater rows, 53 goalie rows, 622 players, 32 teams; skips none; database counts unchanged |
  | Default write | Same counts; both teams covered for every completed game dated October 20-23 |
  | `--season 2026` | 1,344 games, 5,939 skater rows, 348 goalie rows, 783 players, 32 teams; skips none |
  | Repeat `--season 2026` | Every NHL row count unchanged |
  | Schedule SQL | Exactly 1,344 REG games, no PRE; week 1 is exactly 39 games dated September 29-October 4 |
  | Full coverage SQL | Both teams have skater and goalie rows for every completed game through October 23 |
  | Link SQL | Every stat row references a completed NHL game and NHL player/team/opponent |
  | Isolation | NFL/NBA counts unchanged in all seven shared tables and nba_player_game_stats, against the baseline captured before Step 5 |

- The daily window follows NBA's existing rule: today minus days_back
  through today, inclusive (October 20-23 for the default run on October 23).
- Rolled-back repository probes verified that a reschedule updates date,
  start, week, status and end_period, and that an injected final goalie-write
  error rolls back preceding game/player/skater writes. No probe rows remain.
- Verify passed with the API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`.
  Web: 815 tests plus typecheck/build; API: 3,865 tests. Existing Vite
  large-chunk and Starlette/anyio deprecation warnings remain.
- Local review artifacts: ignored `output/45b-step5.diff` (relative to the
  approved parser version), `output/45b-step5-verify.log` and
  `output/45b-step5/` (CLI logs, baseline/counts and SQL/probe helpers).
  `git diff --check` passed. The interview guide remains unchanged under
  the spec's instruction to wait for 45e unless it lists ingest providers.
- Owner approved Step 5 and proceeding to historical backfills; no checkpoint commit.

### Step 6 (2026-10-23, approved)

- Ran `.venv/Scripts/python.exe -m app.ingest.nhl_api --season 2023`,
  then `--season 2024`, then `--season 2025`, separately from `api/`.
  Refreshed `--season 2026` last so historical loads do not leave current
  players' team metadata on an older season. No source changes were needed.

  | Season | REG games | PST games | Skater rows | Goalie rows |
  |---|---:|---:|---:|---:|
  | 2023-24 | 1,312 | 88 | 50,389 | 2,979 |
  | 2024-25 | 1,312 | 86 | 50,320 | 2,953 |
  | 2025-26 | 1,312 | 82 | 50,182 | 2,942 |
  | 2026-27 to date | 1,344 scheduled in full | 0 published | 5,939 | 348 |

- Every historical REG/PST game is completed. Current season: 165
  completed and 1,179 scheduled games. Total inventory: 33 teams (ARI and
  UTA separate), 1,356 players, 5,536 games, 156,830 skater rows and
  9,222 goalie rows.
- Excluded game types were counted, never stored: 2023 had type 4 (3)
  and type 12 (1); 2024 had type 1 (17), type 19 (6), type 20 (1);
  2025 had type 9 (30). No other skips occurred.
- `/check` SQL found zero missing skater/goalie boxes for either team of
  every completed game, and zero invalid sport, season, home/away or team
  links. Every player's current team matches their latest loaded game
  across all four seasons.
- 2025-26 weeks 19/20 and 2024-25 week 20 have zero games. The two Prague
  games (2024020001/2024020002, October 4/5) are exactly 2024-25 week 1.
- Score reconciliation has five explained exceptions. Each team's summed
  skater goals is one below its official final because a goalie scored.
  Separate official goalie/summary fetches confirmed each goal; their
  returned totals matched the received row counts. Goalie goals are not
  columns in this feature's stat-table contract, so no skater stat or
  official team score was changed:

  | Game id | Date | Team | Score | Skater goals | Goalie with 1 goal |
  |---|---|---|---:|---:|---|
  | 2023020345 | 2023-11-30 | PIT | 4 | 3 | Tristan Jarry |
  | 2024020052 | 2024-10-15 | MIN | 4 | 3 | Filip Gustavsson |
  | 2024020720 | 2025-01-17 | PIT | 5 | 4 | Alex Nedeljkovic |
  | 2024020949 | 2025-03-01 | NYI | 7 | 6 | Ilya Sorokin |
  | 2026020010 | 2026-10-01 | NYR | 5 | 4 | Igor Shesterkin |

- No unexplained score mismatches remain. Game 2025021018 stores CAR 5,
  PIT 4, SO, skater goals 4/4, Andersen 24 saves on 28 shots.
- NFL/NBA counts in all seven shared tables and nba_player_game_stats
  match the baseline captured before the historical loads.
- Verify passed: `npm --prefix web run verify && cd api && python -m pytest`
  with the API venv on PATH. Web: 815 tests plus typecheck/build; API:
  3,865 tests. Existing Vite large-chunk and Starlette/anyio deprecation
  warnings remain. `git diff --check` passed.
- Evidence: ignored `output/45b-step6/` contains each CLI log, the baseline,
  integrity SQL/helper, full results and raw goalie reports supporting the
  exceptions; `output/45b-step6-verify.log` holds Verify output.
- Owner approved Step 6 and proceeding to workflow/docs; no checkpoint commit.

### Step 7 (2026-10-23, approved)

- Added `.github/workflows/nhl-ingest.yml`: cron `45 9 * 1-6,9-12 *`,
  manual dispatch, `contents: read`, DATABASE_URL as its only secret, and
  the same checkout, Python 3.11/pip-cache and install steps as NBA ingest.
  Its final step runs `cd api` then `python -m app.ingest.nhl_api`.
- Added the exact NHL CLI options, daily window, applied migration and
  schedule to `AGENTS.md`. The shared instructions already flow through
  CLAUDE.md; no adapter changes were needed.
- Parsed the YAML with the API venv's existing PyYAML 6.0.3 BaseLoader;
  asserted the exact cron, triggers, permissions, single secret, command
  and setup-step equivalence to NBA. All checks passed.
- `/check` ran the workflow's exact `python -m app.ingest.nhl_api` command
  from `api/` with the API venv on PATH. It succeeded: 1,344 games,
  900 recent skater rows, 53 recent goalie rows, 622 players, 32 teams;
  skips none. No GitHub workflow was dispatched.
- GitHub runner reachability of api.nhle.com and api-web.nhle.com remains
  unverified until the first post-push run; the workflow is still local.
- Verify passed: `npm --prefix web run verify && cd api && python -m pytest`
  with the API venv on PATH. Web: 815 tests plus typecheck/build; API:
  3,865 tests. Existing Vite large-chunk and Starlette/anyio deprecation
  warnings remain. `git diff --check` passed.
- Findings ledger: F-09 (P3) and F-12 (P2) remain unverified; no open or
  fixed P0/P1 finding blocks completion. This step did not change findings.
- Review artifacts: ignored `output/45b-step7.diff`,
  `output/45b-step7/workflow-command.log` and `output/45b-step7-verify.log`.
- Owner approved Step 7 by invoking /complete. The completion record below
  distinguishes local engineering completion from runner acceptance.

## Files / areas

- `api/app/db/migrations/versions/0049_nhl_games_and_box_scores.py` (new)
- `api/app/core/regular_season_week.py` (new), `api/app/core/nba_season.py`
  (re-exports only)
- `api/app/core/nhl_season.py` (new)
- `api/app/ingest/nhl_api.py` (new)
- `api/app/repositories/nhl.py` (new)
- `api/tests/test_regular_season_week.py`, `api/tests/test_nhl_season.py`,
  `api/tests/test_nhl_api.py` (new)
- `.github/workflows/nhl-ingest.yml` (new)
- `AGENTS.md` (ingest commands)

## Data / contracts

All load-bearing for 45c-45f and the later NHL model items.

**`sports`:** new row `('nhl', 'NHL')`.

**`sport_games` for NHL** (existing columns; NFL-only columns stay NULL):

| Column | NHL value |
|---|---|
| `source_game_id` | NHL `gameId` as text (`2025021018`) |
| `season` | start year; equals the first four digits of `gameId` |
| `week` | regular-season week (Monday to Sunday by Eastern date, week 1 holds opening night = earliest stored `REG` game date); NULL for `PST` |
| `game_type` | `REG` (`gameType` 2) or `PST` (3) |
| `game_date` | Eastern date of `startTimeUTC` |
| `start_utc` | `startTimeUTC` |
| `home_score`, `away_score` | official final, shootout winner's goal included; NULL until `completed` |
| `status` | `completed` (`OFF`/`FINAL`), `postponed` (`PPD`), `canceled` (`CNCL`), else `scheduled` |
| `end_period` (**new**) | `REG`, `OT` or `SO` from `gameOutcome.lastPeriodType`, completed games only |

- `end_period`: `varchar(3)`, nullable, `CHECK (end_period IN ('REG','OT','SO'))`
  and `CHECK (sport = 'nhl' OR end_period IS NULL)`.

**`sport_teams`:** `team_code` = NHL `abbrev` (`TBL`, `UTA`; `ARI` for
2023-24 Arizona, a separate row from `UTA`), `name` = `placeName` +
`commonName`, latest loaded wins.

**`sport_players`:** `source_player_id` = NHL `playerId`, `name` = full name
from the stats reports, `position` = `positionCode` (`C`, `L`, `R`, `D`,
`G`), `team_id` = team of the latest loaded game. **A past game's team is the
stat row's `team_id`, never `sport_players.team_id`** (NBA's rule).

**`nhl_skater_game_stats`** and **`nhl_goalie_game_stats`** (new):

| Shared column | Type |
|---|---|
| `id` | bigint PK |
| `player_id` | FK `sport_players.id` (cascade), not null |
| `game_id` | FK `sport_games.id` (cascade), not null |
| `team_id`, `opponent_team_id` | FK `sport_teams.id`, not null |
| `season` | smallint, not null (copied from the game) |
| `is_home` | boolean, not null |
| `time_on_ice_seconds` | integer |
| `fetched_at` | timestamptz, default `now()` |

- Skater only: `position` text; smallint `goals`, `assists`, `points`,
  `shots`, `power_play_goals`, `power_play_points`, `shorthanded_points`,
  `plus_minus`, `hits`, `blocked_shots`, `faceoffs_won`, `faceoffs_lost`,
  `penalty_minutes`, `giveaways`, `takeaways`, `ot_goals`.
- Goalie only: `started` boolean not null; `decision` text (`W`, `L`, `O` or
  NULL); smallint `saves`, `shots_against`, `goals_against`.
- **Unique (`player_id`, `game_id`)** on each (the upsert target); index on
  (`player_id`, `season`) and on `game_id`.
- **No row means did not play** (a skater row exists only if he dressed, a
  goalie row only if he played): a void, never zero. A NULL column means not
  loaded. Shootout goals and saves are in no column.
- Stat rows exist only for `completed` games.
- No `sport` column: NHL-only by name, like the `nfl_*` and `nba_*` stat
  tables.

**Source field map:**

| Column | Report and field |
|---|---|
| goals, assists, points, shots, plus_minus, penalty_minutes, ot_goals | `skater/summary` `goals`, `assists`, `points`, `shots`, `plusMinus`, `penaltyMinutes`, `otGoals` |
| power_play_goals, power_play_points, shorthanded_points | `skater/summary` `ppGoals`, `ppPoints`, `shPoints` |
| time_on_ice_seconds (skater) | `skater/summary` `timeOnIcePerGame` |
| hits, blocked_shots, giveaways, takeaways | `skater/realtime` same names |
| faceoffs_won, faceoffs_lost | `skater/faceoffwins` `totalFaceoffWins`, `totalFaceoffLosses` |
| saves, shots_against, goals_against, time_on_ice_seconds, started | `goalie/summary` `saves`, `shotsAgainst`, `goalsAgainst`, `timeOnIce`, `gamesStarted` |
| team, opponent, is_home | `teamAbbrev`, `opponentTeamAbbrev`, `homeRoad` |

**`regular_season_week(game_date, opening)`** (`app/core/regular_season_week.py`)
is the one week rule for NBA and NHL; it imports no sport package.

## Testing

- **Unit tests (test gate on):**
  - `tests/test_regular_season_week.py`: week boundaries, skipped weeks, the
    before-week-1 error (Step 2)
  - `tests/test_nhl_season.py`: season in progress, season id, game types,
    status and `end_period` mapping (Step 2)
  - `tests/test_nhl_api.py`: schedule and stats-report parsing with inline
    JSON, including OT/SO, skips, missing-report NULLs and goalie decisions
    (Step 3)
- **Not unit-tested:** repository SQL, HTTP paging and the workflow; proved by
  the Step 5 and Step 6 loads, re-runs and SQL checks, and by running the
  workflow's command locally (Step 7).
- Final gate: Verify (`npm --prefix web run verify && cd api && python -m
  pytest`, or the API half with `.venv\Scripts\python.exe -m pytest`).

## Notes for the AI

- Mirror `app/ingest/hoopr_nba.py`: fetch and parse with no database import at
  module level; the store function imports the repository; the
  `WindowsSelectorEventLoopPolicy` goes in `__main__` (see the local API
  memory).
- Every SQL statement on a `sport_*` table carries the literal `'nhl'` (the
  17a/17b rule). Do not import `app.repositories.nba` or any NBA module from
  NHL code; duplicate the two small private helpers (`_chunks`,
  `_ids_by_source`) instead. The shared week module imports neither sport.
- The NHL APIs are unofficial: 20 s timeouts, sequential requests, tenacity on
  transport errors and 5xx, a clear exit-1 message on a 4xx. A whole season
  is about 40 schedule calls and about 40 stats calls (4 reports by about 10
  months); a daily run is about 40 plus 4. Paging starts at
  `regularSeasonStartDate`, not the preseason, so preseason weeks are never
  fetched; any stray preseason or All-Star game is still skipped by type.
- Parse `startTimeUTC` as UTC and derive `game_date` with
  `ZoneInfo("America/New_York")`, as `espn_nba_preseason.py` does. Never use
  the stats REST `easternStartTime` (local, no offset).
- Opening night is computed from the parsed schedule after the whole season
  is fetched, not taken from `regularSeasonStartDate`; compute weeks only
  after that.
- `limit=-1` returned a full month (6,480 skater rows, 3.3 MB) in the 45a/45b
  probes; the `total` guard is what makes truncation loud if that changes.
- The goalie report lists only goalies who played; a dressed backup has no
  row (45a). Skater reports never list goalies.
- Migrations are manual against the shared Neon database, one command at a
  time; the migration is additive, so no push ordering constraint applies.
  The local `ingest_daily` task and Actions share the database.
- 44b is parked on `feature/44b-nba-pover-confirmation`; branch this work
  from `master` as `feature/45b-nhl-schedule-box-scores` and do not touch 44b
  files.
- Interview guide: NHL is not yet visible to users; update the guide's data
  sources passage only if it lists ingest providers, otherwise wait for 45e.
- No em dashes in new comments, docstrings or docs.

## Completion review (2026-10-23)

- All seven steps approved. Local engineering is complete; migration 0049
  and the four-season backfill are applied to the shared database.
- Final safety pass found only the approved feature paths. Invariants review
  was clean: NHL-scoped shared SQL, pure sport-neutral week helper, no NBA
  imports from NHL, no model or UI changes, no tracked secrets, and no new
  request-path work. Shared Blueprint adapters were not changed.
- NHL 2025-26's designated future holdout was imported (1,394 games,
  50,182 skater rows, 2,942 goalie rows) and read for data-integrity checks.
  No fit, projection evaluation, ranking test or adoption decision was run.
  Existing tennis/NFL/NBA model evidence and versions were unchanged.
- Exact Verify command passed in this session: 815 web tests, 3,865 API
  tests, typecheck and build. Runtime evidence and documented goalie-goal
  exceptions are recorded above. No required local check was skipped.
- F-09 (P3) and F-12 (P2) remain unverified in the findings ledger. No
  finding was resolved by this feature; none was removed or archived.
- Workflow runner acceptance and deployment remain unverified until the
  approved code is pushed and the new workflow runs. Local completion
  does not claim that the daily GitHub job is active.
- The interview guide remains unchanged per the spec's instruction to
  wait for the NHL pages (45e) unless its source passage lists providers.
- Manual try from api/: `.venv/Scripts/python.exe -m app.ingest.nhl_api
  --dry-run`. It prints schedule/box-score counts and skip counts without
  writing. Use --season only when intentionally backfilling that season.
