# Feature: NBA schedule and box-score ingest

**From build-plan:** feature 20b
**Status:** complete (2026-10-06)

## Goal

Load NBA games, teams, players and per-game player box scores into the
database from hoopR's ESPN release files, as 20a decided: the full 2025-26
season as a backfill, the 2026-27 schedule, and a daily refresh that keeps
scores and box scores current from opening night (2026-10-20). This is the
NBA counterpart of 19a, written on the shared `sport_*` tables from day one so
item 20 adds no parallel stack.

## In scope

- **Migration `0043`:** seed `('nba', 'NBA')` in `sports`; create
  `nba_player_game_stats` with 20a's column list.
- **Pure season logic** in `app/core/nba_season.py`: hoopR file season to
  stored season, the season in progress for a date, opening night, the
  regular-season week (20a's period), and ESPN season type to `game_type`.
- **Parsers** for `espn_nba_schedules/nba_schedule_<YYYY>.csv` and
  `espn_nba_player_boxscores/player_box_<YYYY>.csv` into frozen dataclasses.
- **Repository** `app/repositories/nba.py`: upserts for teams, games,
  players and box-score rows, every statement carrying `sport = 'nba'`.
- **Ingest command** `python -m app.ingest.hoopr_nba`:
  - `--season 2025` backfills 2025-26 (schedule plus every box score)
  - no `--season`: the season in progress, the whole schedule plus box scores
    for games dated in the last `--days-back` days (default 3)
  - `--dry-run` parses and counts without writing
- **Daily workflow** `.github/workflows/nba-ingest.yml`, October through June.
- `AGENTS.md` ingest command list gains the NBA line.

## Out of scope

- PrizePicks NBA lines and the PrizePicks-to-ESPN team code map (20c).
- Game odds (20d), web pages (20e), projections (20f, 20g).
- Injuries (proposed 20h, not in the plan).
- Preseason games (ESPN season type 1): never stored.
- Team ratings or team-game efficiency tables (20a: none).
- Conference and division on `sport_teams` (not in the files; left NULL).
- Seasons before 2025-26 (20f replays 2025-26 only; add older seasons only if
  20f asks for them).
- WNBA (item 21).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Migration `0043`** - seed `nba` in `sports` and create
  `nba_player_game_stats` (columns and keys under Data / contracts).
  Downgrade drops the table, then deletes the `nba` row; if any `sport_*` row
  still references `nba` the delete fails loudly rather than cascading.
  *Done when:* `alembic upgrade head` reaches `0043`; `alembic downgrade -1`
  then `upgrade head` round-trips cleanly; `SELECT code FROM sports` lists
  `nfl` and `nba`; NFL row counts in the seven `sport_*` tables are identical
  before and after.
- [x] **Step 2 - Season logic** - `app/core/nba_season.py` (pure) plus
  `tests/test_nba_season.py`. *Done when:* tests pass for:
  - file season 2026 stores as 2025 (`stored_season`)
  - `current_nba_season`: 2026-10-05 gives 2026, 2027-03-01 gives 2026,
    2026-07-15 gives 2025 (a new season starts in August)
  - opening night 2026-10-20 (a Tuesday): week 1 is 2026-10-19 through
    2026-10-25, week 2 starts 2026-10-26; a date before the Monday of opening
    week raises `ValueError`
  - ESPN season types 2, 5, 3 map to `REG`, `PIN`, `PST`; type 1 and unknown
    types map to None
- [x] **Step 3 - Parsers** - `app/ingest/hoopr_nba.py` holding `NbaGame` /
  `NbaPlayerGame` dataclasses, `parse_schedule` and `parse_player_box`, plus
  `tests/test_hoopr_nba.py` with small inline CSV fixtures. *Done when:*
  tests pass for:
  - a regular, a play-in and a playoff game parse with `game_type`, stored
    season, Eastern `game_date`, UTC `start_utc`, scores (NULL until
    completed) and `week` (NULL off the regular season)
  - a preseason row and a `TBD`-side row are skipped and counted
  - a DNP row gives `did_not_play = True` and NULL stats
  - `plus_minus` `"+2"` / `"-7"` / `""` parse to 2 / -7 / None
  - a row with a blank `athlete_id` or `game_id` is skipped and counted
- [x] **Step 4 - Repository** - `app/repositories/nba.py` with `upsert_team`,
  `upsert_game`, `upsert_player`, and a batched `upsert_player_games` (one
  `executemany` per chunk, not one round trip per row), mirroring
  `app/repositories/nfl.py`'s SQL and `ON CONFLICT` targets, with the literal
  `'nba'` on every statement. A game upsert updates `game_date`, `start_utc`,
  `week`, scores and `status`, so a rescheduled game moves weeks. *Done when:*
  every statement in the diff inserts or filters `'nba'`; `pytest` stays
  green. Exercised for real in Step 5.
- [x] **Step 5 - Ingest command and backfill** - `run(season, days_back,
  dry_run)` and the CLI in `app/ingest/hoopr_nba.py`: fetch both files with
  `httpx` (follow redirects), parse, then upsert in one transaction (roll back
  on any error). A missing box-score asset is fine while no game of that
  season is completed (exit 0 with a message); otherwise exit 1. *Done when:*
  - `--season 2025 --dry-run` prints game and box-score row counts and writes
    nothing
  - `--season 2025` loads 2025-26: every regular, play-in and playoff game
    with final scores, and box-score rows equal to the parsed count (about
    34,880 less skipped rows), with the skip counts printed
  - a second `--season 2025` run leaves every NBA row count unchanged
  - a default run (season in progress) stores the 2026-27 schedule: every
    file row except the `TBD` placeholders (1,200 `REG` games plus 6 skipped
    NBA Cup slots, the file's 1,206), all `scheduled`, `week` 1 holding exactly the games of
    2026-10-20 to 2026-10-25, no `TBD` team in `sport_teams`, and exits 0
    although no 2026-27 box-score file exists yet
  - SQL check: no `nba_player_game_stats` row points at a non-NBA game,
    player or team, and NFL counts in the seven `sport_*` tables are unchanged
- [x] **Step 6 - Daily workflow and docs** - `.github/workflows/nba-ingest.yml`
  (cron `30 9 * 1-6,10-12 *`, after hoopR's 07:00 UTC release run, plus
  `workflow_dispatch`; the same setup steps as `nfl-scores.yml`; runs
  `python -m app.ingest.hoopr_nba`), and the NBA line in `AGENTS.md`'s ingest
  commands. *Done when:* the workflow file parses as YAML with the cron and
  command shown; the exact command it runs succeeds locally against the
  database; `AGENTS.md` lists `python -m app.ingest.hoopr_nba [--season
  2025] [--days-back 3] [--dry-run]`.

## Files / areas

- `api/app/db/migrations/versions/0043_nba_games_and_box_scores.py` (new)
- `api/app/core/nba_season.py` (new), `api/tests/test_nba_season.py` (new)
- `api/app/ingest/hoopr_nba.py` (new), `api/tests/test_hoopr_nba.py` (new)
- `api/app/repositories/nba.py` (new)
- `.github/workflows/nba-ingest.yml` (new)
- `AGENTS.md` (ingest commands)

## Data / contracts

**`sports`:** new row `('nba', 'NBA')`.

**`sport_games` for NBA** (existing columns; NFL-only columns stay NULL):

| Column | NBA value |
|---|---|
| `source_game_id` | ESPN `game_id` |
| `season` | start year (hoopR file season minus 1) |
| `week` | regular-season week (20a); NULL for `PIN` and `PST` |
| `game_type` | `REG`, `PIN` (play-in, ESPN type 5), `PST` (playoffs, type 3); fits the existing `varchar(3)` |
| `game_date` | ESPN `game_date` (the Eastern date) |
| `start_utc` | ESPN `start_date`, as UTC |
| `home_score`, `away_score` | NULL until ESPN marks the game completed |
| `status` | `completed` when ESPN's `status_type_completed` is true; `postponed` or `canceled` for ESPN's `STATUS_POSTPONED` / `STATUS_CANCELED`; else `scheduled`. **Load-bearing:** a postponed game is replayed under a new ESPN game id (4 in 2025-26), so its row never completes; a week counts as finished once every `REG` game in it is `completed`, `postponed` or `canceled` |

**`sport_teams`:** `team_code` = ESPN abbreviation (`NY`, `SA`, `GS`,
`UTAH`, ...), `name` = ESPN display name. `TBD` is never stored. `0043`
widens `team_code` from `varchar(3)` to `varchar(8)` because Utah's ESPN code
is `UTAH`; NFL codes are unchanged.

**Skipped games:** preseason (ESPN type 1), `TBD` placeholders, and the
All-Star games, which ESPN files as type 2 with `type_abbreviation =
'ALLSTAR'` (4 in 2025-26, teams Stars, Stripes and World). The NBA Cup final
(`type_abbreviation = 'CC'`) is kept as `REG` with a week.

**`sport_players`:** `source_player_id` = ESPN `athlete_id`, `name` =
`athlete_display_name`, `position` = `athlete_position_abbreviation`,
`team_id` = last loaded team. **Load-bearing:** NBA trades happen mid-season,
so any later reader that needs a player's team for a past game reads
`nba_player_game_stats.team_id`, never `sport_players.team_id`.

**`nba_player_game_stats` (new, load-bearing for 20c to 20g):**

| Column | Type | Notes |
|---|---|---|
| `id` | bigint PK | |
| `player_id` | bigint FK `sport_players.id` (cascade) | |
| `game_id` | bigint FK `sport_games.id` (cascade) | |
| `team_id`, `opponent_team_id` | bigint FK `sport_teams.id` | |
| `season` | smallint | start year, copied from the game |
| `is_home`, `starter`, `did_not_play` | boolean, not null | |
| `dnp_reason` | text | ESPN `reason` |
| `minutes` | real | |
| `points`, `rebounds`, `offensive_rebounds`, `defensive_rebounds`, `assists`, `steals`, `blocks`, `turnovers`, `fouls` | smallint | |
| `field_goals_made`, `field_goals_attempted`, `three_pointers_made`, `three_pointers_attempted`, `free_throws_made`, `free_throws_attempted` | smallint | |
| `plus_minus` | smallint | |
| `fetched_at` | timestamptz, default `now()` | |

- **Unique on (`player_id`, `game_id`)**: the upsert target.
- Index on (`player_id`, `season`) for baselines, and on `game_id`.
- **NULL means not loaded or did not play, never zero.** A DNP row stores
  `did_not_play = true` with NULL stats.
- No `sport` column: the table is NBA-only by name, like the `nfl_*` stat
  tables, and its foreign keys point at NBA rows only.

## Testing

- **Unit tests (test gate on):**
  - `tests/test_nba_season.py`: season label, season in progress, opening
    night, week boundaries, game type mapping (Step 2)
  - `tests/test_hoopr_nba.py`: schedule and box-score parsing with inline CSV,
    including skips, DNPs and `plus_minus` (Step 3)
- **Not unit-tested:** repository SQL and the workflow; proved by the Step 5
  backfill, re-run and SQL checks, and by running the workflow's command
  locally (Step 6).
- Final gate: `cd api && .venv\Scripts\python.exe -m pytest`.

## Notes for the AI

- Mirror `app/ingest/nflverse.py`: fetch and parse with no database import at
  module level; the store function imports the repository; the
  `WindowsSelectorEventLoopPolicy` goes in `__main__`.
- Every SQL statement on a `sport_*` table carries the literal `'nba'` (the
  17a/17b rule); `tests/test_no_nfl_view_names.py` must stay green.
- Parse CSV with `csv.DictReader`; no pandas or pyarrow (not dependencies).
  The 2025-26 box-score CSV is about 17.7 MB; read it once, never per game.
- hoopR names files by season end year; the stored season is the start year.
  Keep that conversion in one function (`stored_season`) so it cannot drift.
- Opening night is the earliest `REG` game date in the season's schedule file,
  not a constant, so a schedule change moves week 1 with it. Compute weeks
  only after the whole schedule is parsed.
- The NBA Cup final is a real game in ESPN's file; store it as whatever
  season type ESPN gives it. If it arrives as type 2 it is `REG` with a week,
  even though the league excludes it from standings; note that in the archive
  if seen.
- Upsert games and box scores in chunks with `executemany` so the backfill is
  not 35,000 round trips to the database.
- The local `ingest_daily` scheduled task and GitHub Actions share one
  database; the migration is additive, so no push ordering constraint applies.
- No em dashes in new comments, docstrings or docs.

## Build notes

- **First run (2026-10-06):** 2025-26 loaded in 24 s: 1,326 games (1,231 `REG`
  final, 4 postponed, 6 `PIN`, 85 `PST`), 34,777 box-score rows, 591 players,
  30 teams; skipped 4 All-Star games, their 73 box-score rows, and 33 rows with
  no athlete id. 2026-27: 1,200 `REG` games scheduled, 6 NBA Cup `TBD` slots
  skipped; week 1 is 2026-10-20 to 2026-10-25 (43 games), weeks 1 to 25.
  2025-26 regular-season teams averaged 115.6 points.
- **Found in the real files, not in the draft spec:** postponed games replayed
  under new ESPN ids (stored as `postponed`); All-Star games filed as regular
  season (skipped by `type_abbreviation`); Utah's code `UTAH` overflowing
  `sport_teams.team_code varchar(3)` (widened to 8 in `0043`).
- **Known data gaps for 20f:** 24 played 2025-26 rows have no `minutes`.
- **Incident:** while testing `0043`, a chained `upgrade head; downgrade -1;
  upgrade head` ran the downgrade after the first upgrade failed, rolling the
  shared database to `0041` and wiping 34b's `fg_made`, `pat_made` and
  `punts`. They were restored the same day by re-running `nflverse` and
  `nflverse_pbp` for 2024 to 2026, and checked against 34b's done-whens
  (no kicker row missing `fg_made` or `pat_made`, no NULL `punts`, 2025 punts
  3.55 per team-game). Migration commands are now run one at a time.
