# Feature: NFL injuries and depth charts

**From build-plan:** feature 19l
**Status:** complete (2026-09-19); live injury-tag check deferred to the user (see Step 8 notes)

## Goal

Store each skill player's weekly injury report and depth-chart order from
NFLverse, refresh them on a pre-game schedule, and show role changes on the slate
(an Out or Questionable tag, a depth move such as "WR2, was WR1") so the user sees
them before trusting an edge. **Display only:** projections, edges, and ranking
are unchanged. Using these signals in the model is a later, backtested decision
(like 19j).

## In scope

- Migration `0026`: `nfl_player_injuries` and `nfl_player_depth_charts`, one row
  per player per season-week.
- Pure parsers for NFLverse `injuries_{season}.csv` and `depth_charts_{season}.csv`.
  The depth chart reduces daily snapshots to **one pre-game snapshot per
  team-week**.
- Idempotent ingest commands for each, a 2025 and 2026 backfill, and refreshes on
  Tuesday, Thursday, and Sunday.
- Slate lines gain the player's injury status and depth rank, their previous
  depth rank, and quality flags for injury status and depth moves.
- The `/nfl` page shows an injury tag by the player name, a depth line in the
  evidence panel, and labels for the new flags.

## Out of scope

- Any model use: projection, edge, or ranking adjustments, or suppressing an Out
  player's edge. Once enough history exists, a backtest (the 19j harness) decides.
- Teammate effects, for example "WR1 is Out, so WR2 gains targets". That is
  model work.
- 2024 depth charts. NFLverse's 2024 file uses an older weekly layout with
  different columns, and this feature has no model to feed.
- Kickers, defense, special teams, and offensive line depth. Only QB, RB, WR,
  and TE carry props that this affects.
- Creating `nfl_players` from these files. Unknown players are skipped and
  counted, as in 19k.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Tables.** Migration `0026` creates both tables (shapes in Data
  / contracts) with downgrades.
  *Done when:* `alembic upgrade head` reaches `0026`, and `downgrade -1` then
  `upgrade head` are clean.

- [x] **Step 2 - Injury parser.** New `app/ingest/nflverse_injuries.py` with
  `parse_injuries(lines, season) -> list[NflverseInjuryWeek]`. It keeps
  `game_type == "REG"` rows for the season (`season_type` is absent in 2024,
  `game_type` is always present), skips rows without a gsis id or team, turns a
  blank `report_status`, `practice_status`, or injury into `None`, and keeps the
  later row for a duplicate player-week.
  *Done when:* tests on a fixture with the real 2026 header cover kept fields,
  the blank-to-`None` rule, the REG and season filter, skips, and duplicates. The
  real 2026 file parses to 412 rows.

- [x] **Step 3 - Injury ingest, backfill, and cron.** A fetch, `run(season,
  dry_run)`, and a CLI (`python -m app.ingest.nflverse_injuries [--season N]
  [--dry-run]`). A repository function replaces the file's season-weeks in one
  transaction, matching players and teams without creating either. Backfill 2025
  and 2026. Add the step to `nfl-ingest.yml` after rosters, and to
  `nfl-prop-odds.yml` before the price fetch with `continue-on-error: true`.
  *Done when:* a repository test proves the scoped replace and skip-not-create.
  The backfill prints stored and skipped counts, a rerun leaves an identical
  checksum, and both workflows parse.

- [x] **Step 4 - Depth chart parser and pre-game reduction.** New
  `app/ingest/nflverse_depth_charts.py`, streaming the ~50 MB file:
  `reduce_depth_charts(lines, schedule) -> list[NflverseDepthWeek]`. `schedule`
  maps team code to that team's `(week, game_date)` list. Each snapshot row
  (`dt`) belongs to its team's next game: the first week whose `game_date` is on
  or after the snapshot's UTC date. For each team-week, only the **latest**
  snapshot counts. Keep `pos_abb` in QB, RB, WR, and TE; take `pos_rank` as the
  depth rank; skip rows without a gsis id. A player listed twice in one snapshot
  (none in the latest 2026 snapshot, but possible in history) keeps the lowest
  rank. Snapshots after the team's last scheduled game are dropped. It is pure,
  with the schedule passed in, so tests need no database.
  *Done when:* tests prove:
  - a snapshot on game day belongs to that week, and one the day after belongs to
    the next;
  - a later snapshot replaces an earlier one for the same team-week;
  - a bye week maps to the following game;
  - a duplicate listing keeps the lowest rank;
  - post-season snapshots are dropped;
  - non-skill positions and rows without an id are dropped.

  The real 2026 file reduces to one snapshot per team for weeks 1 and 2, with
  each week's timestamp recorded.

- [x] **Step 5 - Depth ingest, backfill, and cron.** Same shape as Step 3: the
  schedule comes from `nfl_games`, the command is
  `python -m app.ingest.nflverse_depth_charts`, the replace is per season-week,
  and the step goes in both workflows (after injuries).
  *Done when:* this step has the same tests and rerun checksum as Step 3. A
  spot check of one team's stored week 2 depth (CIN WR: Chase 1, Higgins 2)
  matches the file's latest pre-game snapshot.

- [x] **Step 6a - Slate query: availability rows.** In `get_slate_lines`, left
  join the player's week-W injury row and depth row, plus their latest depth row
  from strictly before (S, W), through a `DISTINCT ON` CTE so the per-season
  baseline fan-out is not multiplied. Pass the values through the row dict only.
  No API change yet.
  *Done when:* repository tests prove the week-W joins and the strictly-before
  bound. A before/after 2026 week 2 run shows the same line count and identical
  projection and edge on every line, and a count of lines with injury and depth
  rows is recorded.

- [x] **Step 6b - Slate API: fields and role flags.** In `routers/nfl.py` and
  `schemas/nfl.py`, return the new nullable fields and add flags:
  - `injury_out`, `injury_doubtful`, `injury_questionable` from `report_status`;
  - `depth_promoted` and `depth_demoted` when the rank moved against the
    previous row at the same position;
  - `depth_new` when there is no earlier row, or the position or team changed.

  Projection, edge, and rank are untouched.
  *Done when:* router tests cover each flag and the all-null case. The live 2026
  week 2 slate shows flag counts (recorded), identical projections and edges,
  and one Out player and one depth move that match the source files.

- [x] **Step 7 - Show it on `/nfl`.** Types in `web/src/types/nfl.ts`. The
  player cell gets a small status tag: OUT, D, or Q, colored by severity. The
  evidence panel gets a line: "Depth: WR2 (was WR1)" and "Injury: Questionable,
  hamstring, limited practice". Labels and colors for the new flags go in
  `nflLabels.ts` and `FLAG_COLORS`. Any new formatter goes in `src/utils/` with a
  test.
  *Done when:* web tests and the build pass. A screenshot of a Questionable or
  Out player's row and panel matches the API values, and a player with no report
  shows no tag.

- [x] **Step 8 - Verify.** (Live tag screenshot deferred by the user; see
  Implementation notes.) Full API tests, web tests, and web build. Migration
  `0026 (head)`. After NFLverse publishes week 2's final injury reports (the
  2026-09-18 12:12 UTC file had them only for DET and BUF), rerun the injury
  ingest and confirm one live OUT, D, or Q tag, carried over from Step 7.
  *Done when:* all pass, the Step 6a before/after check still shows unchanged
  edges, and a screenshot shows a live injury tag and tooltip matching the API.

## Files / areas

| Path | Change |
|---|---|
| `api/app/db/migrations/versions/0026_nfl_injuries_depth_charts.py` | Two tables, with downgrade |
| `api/app/ingest/nflverse_injuries.py`, `api/app/ingest/nflverse_depth_charts.py` | New parsers, fetch, CLI |
| `api/app/repositories/nfl.py` | Two replace writes, schedule-by-team read, slate joins |
| `api/app/routers/nfl.py`, `api/app/schemas/nfl.py` | New slate fields and flags |
| `.github/workflows/nfl-ingest.yml`, `.github/workflows/nfl-prop-odds.yml` | Refresh steps |
| `web/src/types/nfl.ts`, `web/src/pages/NflIntelligencePage.tsx`, `web/src/utils/nflLabels.ts` | Tag, panel line, flag labels |
| `api/tests/test_nflverse_injuries.py`, `api/tests/test_nflverse_depth_charts.py`, `test_nfl_repository.py`, `test_nfl_projection.py` | Parser, reduction, write, join, and flag coverage |

## Data / contracts

**Sources** (public, no key; refreshed daily around 12:00 UTC):
- `.../injuries/injuries_{season}.csv`: weekly, one row per listed player.
  2026 had 412 rows for weeks 1 and 2. `report_status` is Out, Doubtful,
  Questionable, or blank (on the practice report only).
- `.../depth_charts/depth_charts_{season}.csv`: about 50 MB, one ESPN snapshot
  per day since March (two a day lately), stamped `dt`. The offense group is
  `3WR 1TE`. `pos_rank` is the order within `pos_abb` (CIN WR: Chase 1,
  Higgins 2, Iosivas 3). The latest 2026 snapshot has one row per skill player,
  and 491 of 565 of them are stored players.

**Schema (load-bearing: the model decision after this feature and 19m read it),
migration `0026`:**

`nfl_player_injuries`
- `player_id` -> `nfl_players.id` (cascade), `season`, `week` smallint;
  **unique (`player_id`, `season`, `week`)**
- `team_id` -> `nfl_teams.id`
- `report_status` text NULL (Out, Doubtful, Questionable; NULL = on the
  practice report only)
- `practice_status` text NULL, `primary_injury` text NULL
- `updated_at` timestamptz

`nfl_player_depth_charts`
- `player_id`, `season`, `week`; **unique (`player_id`, `season`, `week`)**
- `team_id`, `position` text (QB, RB, WR, TE), `depth_rank` smallint
- `snapshot_at` timestamptz (the snapshot this week's row came from)
- `updated_at` timestamptz

**Pre-game rule (load-bearing):** a team-week's depth row comes from the latest
snapshot whose UTC date is on or before that team's game date. Snapshots land
around 06:00 and 12:00 UTC, before any kickoff, including London games at 13:30
UTC.

**Slate API (additive, all nullable):** `injury_status`, `practice_status`,
`injury`, `depth_position`, `depth_rank`, `previous_depth_position`,
`previous_depth_rank`. New flags: `injury_out`, `injury_doubtful`,
`injury_questionable`, `depth_promoted`, `depth_demoted`, `depth_new`.

## Testing

Test gate is on:

- Step 2: injury parser.
- Step 4: depth reduction.
- Steps 3 and 5: scoped replace.
- Step 6a: joins. Step 6b: flags.
- Step 7: any formatter.

There are no live downloads in tests. Backfills, rerun checksums, slate
before/after, and spot checks are explicit verification runs. API from `api/`
with `.venv\Scripts\python.exe -m pytest`, and web with `npm run test` and
`npm run build`.

## Notes for the AI

- Display only. If a step seems to need changing a projection, an edge, or
  `slate_line_rank`, stop. That is out of scope.
- A player absent from the injury file means "not on the report", or that the
  report is not published yet. It never means "healthy confirmed". Show no tag,
  not a "Healthy" tag.
- Week 1 compares against the previous season's last depth row, so offseason
  moves show up as `depth_new`, `depth_promoted`, or `depth_demoted` in week 1.
  That is intended: those are real role changes.
- Both files use NFLverse team codes (all 32 checked). Unknown codes are still
  skipped and counted, not aliased.
- `injury_out` on a line still leaves its edge in place and ranked. The red tag
  is the warning. Suppression is model use and out of scope.
- Stream the depth file; do not hold all 530k rows. Only the current best
  snapshot per team-week is kept in memory.
- Keep `NULL` distinct from empty or zero, as in 19h and 19j.
- Follow 19k's shapes: an `Iterable[str]` parser, a whole-file parse before one
  transaction, replace by season-week, skip and count unknown players, and
  `SeasonNotPublished(season, asset)`.

## Implementation notes

- Step 1: migration `0026` (both tables share one player-week column helper)
  upgrade, downgrade, and re-upgrade clean; API tests 867 passed.
- Step 2: `parse_injuries`. `primary_injury` takes the game report's injury and
  falls back to the practice report's, so a practice-only DNP keeps its reason
  (for example "Not injury related - resting player"). Blank and `NA` become
  `None`. The real 2026 file parses to 412 rows (week 1: 182, week 2: 230):
  Out 33, Questionable 28, Doubtful 6, practice-only 345, and every row has
  injury text. 6 tests; API tests 873 passed.
- Step 3: new `_replace_player_weeks` helper in `repositories/nfl.py` (delete
  season-weeks, insert through player and team joins), used by
  `replace_weekly_injuries` and next by depth charts. 19k's roster write is left
  as is (out of scope). Backfill: 2025 5,783 parsed / 5,688 stored / 95 skipped;
  2026 412 / 384 / 28; no unknown teams. A 2026 rerun replaced 384 with 384, and
  both checksums were identical. Workflow order: stats, red zone, rosters,
  injuries, odds, relink (Tuesday); rosters, injuries, prices (Thursday and
  Sunday, with the refreshes on `continue-on-error`). API tests 876 passed.
- Step 4: `reduce_depth_charts(lines, season, schedule)` keeps only the best
  snapshot per team-week (it is order-independent) and bisects each team's
  sorted game dates. The real 2026 file (531,796 rows) reduces in 2.0 s to
  1,169 rows, one snapshot per team-week and one row per player-week:
  - week 1: 32 teams, each on its game-day morning snapshot (9/9 and 9/10
    openers, 9/13 12:42 for Sunday, 9/14 13:53 for Monday night);
  - week 2: 32 teams, 9/17 12:34 for Thursday's DET and BUF, 9/18 12:12 for the
    rest;
  - week 3: DET and BUF only (their week 2 game is played, so today's chart is
    their next game's). This is intended.

  CIN WR week 2: Chase rank 1. 6 tests; API tests 882 passed.
- Step 5: `fetch_depth_charts` streams the file to a temporary file and reduces
  it from disk; `run` reads `get_team_schedule` first. `replace_weekly_depth_charts`
  uses the shared helper. Also added the missing `date` import in
  `repositories/nfl.py` (it was used in hints only). Backfill: 2025 9,904
  reduced / 9,433 stored / 471 skipped, covering 544 of 544 team-weeks; 2026
  1,169 / 1,016 / 153, 66 team-weeks (weeks 1 and 2, plus DET and BUF week 3).
  A 2026 rerun replaced 1,016 with 1,016, and the checksums were identical.
  Stored CIN week 2: QB Burrow 1, Flacco 2; WR Chase 1, Higgins 2, Iosivas 3.
  WR4 (rookie Colbie Young, not stored) is absent, so ranks keep the file's
  numbering rather than being renumbered. API tests 886 passed.
- Step 6a: `_AVAILABILITY_CTE`, `_AVAILABILITY_COLUMNS`, and `_availability(row)`
  in `repositories/nfl.py`; three left joins in `get_slate_lines`. Slate
  before/after (2026 wk2): the same 8,401 line ids and 0 lines differing. Of 346
  slate players: 339 have a week 2 depth row, 342 an earlier one, and 39 moved
  rank at the same position and team (e.g. Darnell Washington TE2 -> TE1,
  DeMario Douglas WR3 -> WR2). 48 have a week 2 injury row but **none has a
  game status**. As of the 2026-09-18 12:12 UTC refresh, week 2 game statuses
  exist only for Thursday's DET (2) and BUF (3), whose final report was
  midweek; every other team's final report publishes Friday afternoon. Week 1
  has game statuses for 26 teams. So Step 6b's Out spot check uses week 1, and
  the Sunday 14:00 UTC refresh is what carries week 2 statuses. API tests 888
  passed.
- Step 6b: the flag rules are pure, in a new `app/core/nfl_availability.py`
  (`availability_flags`, 11 tests). A different team or position counts as
  `depth_new`, not a rank move, and no chart this week adds no depth flag. The
  router appends them after the team flag, and the schema adds 7 nullable
  fields. Live 2026 wk2: all 8,401 lines have identical projection, edge, and
  opponent, and their non-availability flags are unchanged. Flags per player:
  25 `depth_promoted`, 14 `depth_demoted`, 1 `depth_new`, 0 injury flags
  (statuses unpublished, see 6a). Week 1 has only 21 players with stored lines
  and none with a game status, so the Out spot check used the stored row:
  Audric Estimé (NO), wk1 Out, thigh, DNP, matches the raw file and yields
  `injury_out`. Depth spot check: Darnell Washington (PIT) is TE2 in the
  2026-09-13 12:42 snapshot and TE1 in 2026-09-18 12:12, matching the file and
  flagged `depth_promoted` on the slate. API tests 901 passed.
- Step 7: formatting lives in a new `web/src/utils/nflAvailability.ts`
  (`injuryTag`, `injuryLabel`, `depthLabel`, 8 tests). The page adds a
  `PlayerName` tag, Depth chart and Injury report lines in the panel, and short
  labels and colors for the six new flags. It also adds the missing
  `team_not_in_game` short label (19k). Web tests 84 and the build passed.
  Screenshot (`.playwright-mcp/19l-washington-panel.png`, PIT @ NE): Darnell
  Washington, receiving yards, shows "Depth chart TE1 (was TE2)", "Injury
  report: Practice report only · Not injury related - personal matter · did
  not practice", a green "Depth up" quality tag, and no name tag (no game
  status). This matches the API. The live OUT/D/Q tag could not be shown: at
  2026-09-19 03:11 UTC the injury file was still the 2026-09-18 12:12 UTC one,
  with no week 2 final statuses for teams with lines. That check moved to Step
  8. Unrelated and pre-existing: `recent_market_model` has no short label and
  renders raw.
- Step 8 (partial, 2026-09-19 ~03:15 UTC): API tests 901 passed; web tests 84
  passed; `npm run build` passed; migration `0026 (head)`. Against the
  pre-feature snapshot taken before Step 6a, the week 2 slate has the same
  8,401 lines with 0 changes to projection, edge, opponent, or non-availability
  flags.
- **Live OUT/D/Q tag screenshot: skipped by user decision (2026-09-19).** At
  03:14 UTC the NFLverse injury file was still the 2026-09-18 12:12 UTC one,
  with no week 2 final statuses for teams with lines. The user chose to
  complete on the existing evidence and run the live check manually the next
  day:
  - the `injuryTag`, `injuryLabel`, and `availability_flags` unit tests;
  - the web build;
  - the stored Audric Estimé week 1 Out row matching the raw file and yielding
    `injury_out`;
  - the rendered panel for Darnell Washington.

  Manual check: `python -m app.ingest.nflverse_injuries` from `api/`, then on
  `/nfl` (2026 week 2) find a player tagged OUT, D, or Q by name and confirm
  the tooltip matches `/nfl/slate`'s `injuryStatus`, `injury`, and
  `practiceStatus`.
