# Feature: 2024 injury and depth backfill

**From build-plan:** feature 70b1 (parent 70b, Usage-shift backtest arm; feature 70, Injury-aware NFL projections)
**Status:** complete (2026-11-22). Verify passed (1871 web tests, typecheck, build; 6592 API tests). 2024 stored: 5,919 injury rows and 7,655 depth rows; coverage verdict go for 70b2.
**Branch:** `feature/70b-usage-shift` (worktree `.claude/worktrees/70b-usage-shift`)

## Goal

Store 2024's regular-season NFLverse injury reports and weekly depth charts in
the tables 19l built, so 70b2 and 70b3 can replay 2024 with each week's Out
status and active depth. 2024 is the development season for the usage-shift arm
and 2025 stays the holdout, as for every earlier NFL projection arm (decided
2026-11-22).

Today neither table has a 2024 row (read 2026-11-22):

| Table | 2025 | 2026 | 2024 |
|---|---|---|---|
| `nfl_player_injuries` | 5,688 rows, 18 weeks, 1,301 Out | 3,410 rows, 11 weeks, 693 Out | none |
| `nfl_player_depth_charts` | 9,433 rows, 18 weeks | 5,836 rows, 12 weeks | none |

## What exists

- **Injuries:** `app/ingest/nflverse_injuries.py` already parses the 2024 file
  (`parse_injuries` filters on `game_type` because "older files (2024) have no
  `season_type`"), and `--season 2024` is accepted. It was simply never run for
  2024.
- **Depth charts:** `app/ingest/nflverse_depth_charts.py` reduces the daily ESPN
  snapshot layout (`dt, team, gsis_id, pos_abb, pos_rank`, 2025 on). The 2024 file
  is a different, weekly layout, which 19l left out:

  ```
  season,club_code,week,game_type,depth_team,last_name,first_name,football_name,
  formation,gsis_id,jersey_number,position,elias_id,depth_position,full_name
  ```

  Read from the file on 2026-11-22: 37,312 rows, 35,025 `REG`, weeks 1-19 under
  `REG`; `depth_team` 1-3. For skill players, `position` is clean (`QB`, `RB`,
  `WR`, `TE`, `FB`) while `depth_position` is noisy: blank or whitespace, `HB`,
  and players listed in another slot (an RB at `FB`). WRs share ranks across
  three slots, as in the ESPN layout. Some team-weeks look incomplete (KC week 5
  lists Perine as RB2 and no RB1).

## In scope

- Running the existing injury ingest for 2024 (dry run, then a real write).
- A pure parser for the weekly depth layout, sharing the `NflverseDepthWeek`
  output and `replace_weekly_depth_charts` writer.
- The depth CLI picking the parser from the file's header, so `--season 2024`
  works and 2025+ is unchanged.
- A read-only coverage report comparing 2024 with 2025, which is 70b2's go/no-go
  evidence.
- The real 2024 depth write.

## Out of scope

- Replay rows, the usage-shift adjustment, the arm, the pass rule and any scored
  run (70b2, 70b3).
- Any projection, edge, P(over), rank, pick, color or model-version change.
  Nothing served reads 2024 injury or depth rows.
- 2023 or earlier seasons, playoffs, and positions other than QB/RB/WR/TE.
- Scheduled refreshes: 2024 is a one-time backfill, and no workflow changes.
- A migration: the 2024 rows fit the 0026 tables as they are.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - 2024 injuries, dry run then write.** No code change. Run
  `python -m app.ingest.nflverse_injuries --season 2024 --dry-run`, record its
  output, then (after a yes in chat, since it writes to the shared Neon database)
  the same command without `--dry-run`.
  *Done when:* Results records both outputs, and a read-only count shows 2024 rows
  for 18 regular-season weeks with an Out count in the range of 2025's 1,301, and
  the skipped count is explained (players not in `nfl_players`).
- [x] **Step 2 - Weekly depth parser (pure).** In
  `app/ingest/nflverse_depth_charts.py`, `reduce_weekly_depth_charts(lines,
  season, schedule)`: keeps `game_type == "REG"`, `formation == "Offense"`, weeks
  the team has in `schedule`, and `position` in QB/RB/WR/TE (the `position`
  column, never `depth_position`; `FB` is dropped); `depth_rank = depth_team`;
  a player listed twice in a team-week keeps his best rank; rows without an id,
  team or rank are dropped. `snapshot_at` is the team's game date at 00:00 UTC
  (the file has no timestamp; see Notes).
  *Done when:* tests in `api/tests/test_nflverse_depth_charts.py` cover a clean
  row, a non-REG row, a defensive row, an RB listed at `FB` (kept as RB), an `FB`
  (dropped), a blank `depth_position` (kept), a player listed twice (best rank), a
  week with no scheduled game (dropped), and the `snapshot_at` value.
- [x] **Step 3 - Layout detection in the CLI.** `fetch_depth_charts` reads the
  header and sends the weekly layout (`club_code` present) to the new parser and
  the ESPN layout to `reduce_depth_charts`; an unknown header raises with the
  columns it saw. A dry run for 2024 prints its row and week counts.
  *Done when:* a test pins the layout choice for both headers and the unknown one,
  `python -m app.ingest.nflverse_depth_charts --season 2024 --dry-run` prints
  rows for weeks 1-18, and `--season 2025 --dry-run` prints the same counts as
  before the change (recorded in Results).
- [x] **Step 4 - Coverage report (read-only).** A CLI,
  `python -m app.backtest.nfl_depth_coverage --seasons 2024,2025`, prints per
  season: team-weeks with a rank-1 QB, RB, WR and TE; Out rows (QB/RB/WR/TE) whose
  player has a depth row that week; and Out rank-1 starters with a teammate ranked
  directly behind him (the cases 70b's shift can act on). Counting logic in a pure
  function with a test; SQL in `app/repositories/nfl.py`.
  *Done when:* the report runs on 2025 now and on 2024 after step 5, both outputs
  are recorded in Results, and the test covers the counts on a fixed fixture.
- [x] **Step 5 - 2024 depth write and coverage verdict.** After a yes in chat, run
  `python -m app.ingest.nflverse_depth_charts --season 2024`, then the coverage
  report.
  *Done when:* Results holds the write output and the 2024 coverage beside 2025,
  with a one-line go/no-go for 70b2. **Stop and ask** if 2024's rank-1 RB or WR
  coverage, or its actionable Out-starter count, is below about half of 2025's.
- [x] **Step 6 - Verify.** Passed 2026-11-22: web typecheck, 1871 tests and build;
  API 6592 passed (13 new). `npm --prefix web run verify && cd api && python -m pytest`.
  *Done when:* it passes.

## Files / areas

- `api/app/ingest/nflverse_depth_charts.py` (new parser, layout detection)
- `api/tests/test_nflverse_depth_charts.py` (extended; the ESPN-layout tests stay as they are)
- `api/app/backtest/nfl_depth_coverage.py` (new, read-only CLI)
- `api/app/core/nfl_depth_coverage.py` (new, pure counting)
- `api/app/repositories/nfl.py` (one read-only coverage query)
- `api/tests/test_nfl_depth_coverage.py` (new)
- `docs/commands.md` and `AGENTS.md` (the coverage CLI and the 2024 depth note)

## Data / contracts

- No schema change. 2024 rows use `nfl_player_injuries` and
  `nfl_player_depth_charts` (migration 0026) as they are.
- **Load-bearing for 70b2:** `nfl_player_depth_charts.snapshot_at` for 2024 means
  "the team's game date at 00:00 UTC", not a real snapshot time. Anything that
  reads `snapshot_at` must not treat 2024 values as observed times.
- `NflverseDepthWeek` is unchanged and shared by both parsers.

## Testing

- API, pure: the weekly parser (step 2), the layout choice (step 3) and the
  coverage counts (step 4), each with fixed CSV or row fixtures and no network.
- Ingest runs are evidence, not tests: dry-run and write outputs go in Results.
- No web change, so the web half of Verify only confirms nothing broke.

## Notes for the AI

- **Every write is a separate yes in chat** (steps 1 and 5). Dry runs first. The
  database is the shared Neon one; run one command at a time.
- **Point-in-time caveat:** the 2024 weekly chart has no timestamp and some
  team-weeks look stale or incomplete. 2024 injuries carry `date_modified`, so the
  Out status is point-in-time; depth is "that week's published chart". Say so in
  Results, and let step 5's coverage decide whether 2024 is fit for 70b2.
- **Holdout discipline:** this feature reads no projection or result for any
  season. The 2025 rows are counted only (coverage), never scored.
- Keep the existing ESPN-layout parser and its tests byte-for-byte unchanged in
  behavior; the 2025 dry run in step 3 is the guard.
- `club_code` may not match the stored team codes the way the ESPN `team` column
  does (for example `LA` against `LAR`). The writer already reports
  `unknown_teams`; if step 3's dry run or step 5's write lists any, map them in the
  parser and add a test, rather than dropping those teams.
- Unknown players are skipped and counted, as 19l does; do not create
  `nfl_players` rows from these files.
- The 2024 depth file is about 3.4 MB, so streaming it like the ESPN file is not
  required, but reuse the same download path rather than adding a second one.
- No em dashes in new comments, docs or commit messages.

## Results

### Step 1 - 2024 injuries

Dry run, 2026-11-22, `python -m app.ingest.nflverse_injuries --season 2024 --dry-run`:

```
NFLverse injuries would load 5952 injury rows for weeks 1-18 of season 2024
```

(2025 stores 5,688 rows over 18 weeks, so the size is in line.)

Write, 2026-11-22, after a yes in chat, `python -m app.ingest.nflverse_injuries --season 2024`:

```
NFLverse injuries loaded 5952 injury rows for weeks 1-18 of season 2024: 0 replaced, 5919 stored, 33 skipped (player or team not stored)
```

Read-only count afterward:

| Season | Rows | Weeks | Out rows |
|---|---|---|---|
| 2024 | 5,919 | 18 | 1,078 |
| 2025 | 5,688 | 18 | 1,301 |
| 2026 | 3,410 | 11 | 693 |

The 33 skipped rows (0.6%) are players with no `nfl_players` row, skipped and
counted as 19l does. 2024's Out count is 83% of 2025's.

### Step 2 - weekly depth parser

`reduce_weekly_depth_charts` run offline on the real 2024 file with a stand-in
schedule (every team, weeks 1-18, no byes; no database): 32 teams, 8,138 rows for
weeks 1-18 (WR 3,032, TE 1,894, RB 1,854, QB 1,358). A rank-1 player exists in
569 of 576 team-weeks for QB and RB, 572 for WR and 574 for TE. The file uses
`LA` for the Rams; step 3's dry run against the stored schedule shows whether
that matches. Tests: 14 passed in `tests/test_nflverse_depth_charts.py` (5 new).

### Step 3 - layout detection

`reducer_for(header)` picks the reducer from the header; `fetch_depth_charts`
reads the first line and passes it back in front of the rest. Dry runs,
2026-11-22, one at a time:

| Season | Before | After |
|---|---|---|
| 2025 | 9,904 rows, weeks 1-18 | 9,904 rows, weeks 1-18 (unchanged) |
| 2024 | (not loadable) | 7,699 rows, weeks 1-18 |

The stored 2024 schedule has 32 teams and uses `LA` for the Rams (17 games), so
no team-code mapping is needed. One 2025 dry run failed with Neon closing the
connection during the 50 MB download and passed on a retry 10 seconds later; the
import holds its session open across the download (existing behavior, not
changed here). Tests: 16 passed (2 new).

### Step 4 - coverage report

`python -m app.backtest.nfl_depth_coverage --seasons 2024,2025`, 2026-11-22,
before step 5's write:

```
                                              2024          2025
Team-weeks charted                               0           544
Team-weeks with a QB1                            0    544 (100%)
Team-weeks with a RB1                            0    543 (100%)
Team-weeks with a WR1                            0    543 (100%)
Team-weeks with a TE1                            0    543 (100%)
Out players (QB/RB/WR/TE)                      293           430
  with a chart row that week                0 (0%)     418 (97%)
  Out starters with a charted backup             0           124
```

2025's 124 actionable Out starters is the scale of one season's usage-shift
sample, split across four positions; worth keeping in mind for 70b3's minimum
paired cases. Tests: 4 passed in `tests/test_nfl_depth_coverage.py`.

### Step 5 - 2024 depth write and verdict

The first write, after a yes in chat, failed and rolled back (nothing stored):
`UniqueViolation ... Key (player_id, season, week)=(758, 2024, 10)`. One player
in the whole 2024 file sits on two charts in one week: Mike Williams, WR2 for
both NYJ and PIT in week 10, the week of his trade. Fixed in the parser: when two
teams chart a player in a week, the team that also charts him the next week
keeps the row, and otherwise the player-week is dropped (2 new tests). The
dry run then gave 7,698 rows, and the write:

```
NFLverse depth charts loaded 7698 depth rows for weeks 1-18 of season 2024: 0 replaced, 7655 stored, 43 skipped (player or team not stored)
```

Coverage afterward, `python -m app.backtest.nfl_depth_coverage --seasons 2024,2025`:

```
                                              2024          2025
Team-weeks charted                             544           544
Team-weeks with a QB1                    538 (99%)    544 (100%)
Team-weeks with a RB1                    537 (99%)    543 (100%)
Team-weeks with a WR1                    541 (99%)    543 (100%)
Team-weeks with a TE1                   542 (100%)    543 (100%)
Out players (QB/RB/WR/TE)                      293           430
  with a chart row that week             237 (81%)     418 (97%)
  Out starters with a charted backup           122           124
```

**Verdict: go for 70b2.** Starter coverage is 99% or better at every position and
2024 has 122 actionable Out starters against 2025's 124, well above the
half-of-2025 stop line.

**Carry into 70b2:** 19% of 2024's Out players have no chart row that week
(3% in 2025). The weekly 2024 chart often already leaves an Out player off, so
his backup is charted at rank 1 and no teammate "moves up" in the stored ranks.
70b2 must find the Out starter another way for those weeks (his previous week's
chart rank, for example) or count them as missed cases, and say which in its spec.
