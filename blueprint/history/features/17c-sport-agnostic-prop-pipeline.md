# Feature: Sport-agnostic prop pipeline

**From build-plan:** feature 17c
**Status:** completed (2026-10-02)

## Goal

Make the PrizePicks prop pipeline sport-agnostic. That covers league selection,
line storage and relinking, frozen predictions, 27i's ranking rule, 27j's
forward check and the ranking track-record loader. Each takes a sport instead
of assuming NFL. Item 20 then adds NBA by supplying a config, its own stat and
roster reads, and a projection. It does not copy the pipeline.

This is a refactor. No NFL line, frozen row, report, response, number or
ordering changes. The proof is the same before-and-after comparison 17a and 17b
used.

## In scope

- **A per-sport prop config** (pure, `app/core/prop_sports.py`):
  - sport code
  - PrizePicks league prefix (`NFL`) and segment suffix map
  - board segments
  - market aliases
  - the period label (`week` for NFL)

  `NFL_PROPS` is built from today's constants in `prizepicks_nfl.py` and
  `app/nfl/markets.py`.
- **Generic league selection:** `segment_for_league_name(name, config)` and
  `board_leagues(leagues, config)`. NFL keeps its current results exactly.
- **Generic ranking rule and check:**
  - `app/core/nfl_ranking_rule.py` becomes `app/core/prop_ranking_rule.py`.
  - `app/core/nfl_ranking_check.py` becomes `app/core/prop_ranking_check.py`.
  - `week` becomes `period`.
  - Every constant is unchanged: break-evens, playable sides, margin,
    `MIN_PICKS`, `MIN_WEEKS` (renamed `MIN_PERIODS`, same value 4) and the 2 SE
    rule.
  - The check takes lines that are already settled. Settlement stays with each
    sport.
- **A sport-parameterized prop repository** (`app/repositories/sport_props.py`)
  for the queries that touch only `sport_*` tables:
  - the PrizePicks line insert (moved out of `prizepicks_nfl.py`, as 17b
    deferred)
  - `get_lines_for_relink`, `set_line_linkage`, `get_player_aliases` and
    `get_game_index`
  - `insert_prop_predictions`

  Each takes `sport` as a bind parameter (see Notes).
- **A sport source protocol** (`app/services/sport_props.py`), holding what
  stays sport-specific:
  - resolution candidates (NFL reads its weekly rosters)
  - the current period
  - the lines to freeze, with their predictions (NFL: `build_slate`)
  - frozen settled lines (NFL joins `nfl_player_weekly_stats` and snaps, then
    applies `settle_line`)
  - finished periods and frozen coverage
  - model and P(over) versions

  `NflPropSource` implements it by delegating to today's repository functions.
- **Generic ingest, freeze and loader**, each with NFL wrappers that keep their
  module names, so `nfl-prop-lines.yml` and `nfl-ingest.yml` run unchanged:
  - `app/ingest/prizepicks_props.py`, which `prizepicks_nfl.py` (with
    `--dry-run` and `--relink`) calls
  - `freeze_rows` and `PropPredictionRow` in
    `app/services/prop_predictions.py`, which `nfl_prop_predictions.py` calls
  - `load_ranking_calls(db, source, season)`, which `track_record.py` and
    `nfl_ranking_check.py` call
- **A toy-sport test** that runs league selection, freezing and the ranking
  verdict end to end with a fake source and no NFL import. It proves that a new
  sport supplies only config, data reads and a projection.
- **Proof:**
  - a rolled-back writer run against the hosted database
  - byte-identical reports and responses against master, with timing

## Out of scope

- **27a line grading** (`load_line_grading`, `nfl_prizepicks_lines`). It is an
  NFL diagnostic that replays `build_slate`. A new sport's pre-registered
  evidence is the frozen forward check, which this feature generalizes. 27a
  stays NFL-only, unchanged.
- **Settlement logic and stat tables.** `settle_line`, `GradeableLine`,
  `STAT_COLUMN_BY_MARKET` and `nfl_player_weekly_stats` stay NFL. Each sport
  settles its own lines and hands the check an outcome.
- **The 28 CLV loader and the 27g fit record.** These are game-line and fit
  data, not the prop pipeline.
- **Routes, nav, `bets.sport` and a sport registry.** These belong to 17d.
  `/nfl/model/ranking` keeps its path and response. 17d decides how a sport
  selects the source.
- **NBA itself:** the config values, the period definition and seeding `nba`
  all belong to item 20.
- **Tennis.** Tennis props live in `props` and `prop_projection_snapshots`,
  and tennis `matches` convergence stays out of item 17. The tennis PrizePicks
  ingest (`prizepicks.py`) is untouched, apart from sharing its fetch helpers
  as today. Whether `prop_projection_snapshots` merges with
  `sport_prop_predictions` stays open (open question 18).
- **Workflow files.** They are untouched because the CLI module names are kept.
- **Schema.** No migration. `sports` and the `sport` columns exist from 17a and
  17b.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 0 - Baseline on master** (2026-10-02 17:04-17:12 UTC, master
  `879bbdc`; files in
  `C:\Users\dayshawn\AppData\Local\Temp\claude\c--Users-dayshawn-Desktop-SportAppV2\158e9e7f-a443-43ed-8feb-018347b01098\scratchpad\baseline\`: ranking check 8.6 s,
  ranking API 2.1 s, freeze dry run 89.8 s with frozen 7,503 and kicked off
  653, PrizePicks dry run 66 s with 7,548 live lines, so only its shape is
  comparable; writer proof stored 2 lines, predictions 4 then 0, counts
  unchanged after rollback; script `writers_proof.py`) - capture, on master,
  before any code:
  - the stdout of `nfl_ranking_check --season 2026`
  - the JSON of `GET /nfl/model/ranking?season=2026`
  - the summary of `nfl_prop_predictions --dry-run`
  - the stdout of `prizepicks_nfl --dry-run` (one provider request; skip if
    throttled and say so)
  - each one timed

  Also save the exact rows that master's PrizePicks insert, `set_line_linkage`
  and `insert_prop_predictions` write for a fixed fixture, captured in a
  rolled-back transaction (scratchpad script, not committed). *Done when:* the
  baseline files exist in the scratchpad with their timings, and the
  rolled-back run left the row counts of `sport_prop_lines` and
  `sport_prop_predictions` unchanged.

- [x] **Step 1 - Sport prop config and league selection** (deviation:
  `NFL_PROPS` lives in `app/nfl/markets.py`, not core, because it is built
  from `NflPropMarket` and core must not import NFL or ingest modules; the
  aliases and board segments moved there from `prizepicks_nfl.py`) - add
  `app/core/prop_sports.py` with a frozen `SportPropConfig` dataclass and
  `NFL_PROPS`, plus the generic `segment_for_league_name(name, config)` and
  `board_leagues(leagues, config)`. `app/nfl/markets.py` and
  `prizepicks_nfl.py` call them, and their public functions keep their
  signatures. *Done when:* `pytest` passes, including a table test over every
  league name in today's tests plus `NFL`, `NFL1H`, `NFL 1Q`, `NFLSZN` and a
  non-NFL league, giving the same segments as before. A toy `NBA` config
  maps `NBA1H` and rejects `WNBA` and `NFL`.

- [x] **Step 2 - Generic ranking rule and check** (`FrozenLine` has no
  `segment`: the sport's settlement already reports a non-full-game line as
  `unsettleable_segment`, so the check never read it; `Exclusion` is now `str`
  because settlement reasons are the sport's own; `nfl_ranking_check` CLI
  output byte-identical to the Step 0 baseline) - move the two core modules
  to `prop_ranking_rule.py` and `prop_ranking_check.py`, with `week` renamed to
  `period` and `MIN_WEEKS` to `MIN_PERIODS`. `prop_ranking_check.FrozenLine`
  carries `line_id`, `period`, `player_id`, `game_id`, `market`, `segment`,
  `odds_type`, the settled `outcome`, `p_over`, `p_under` and the two versions.
  It has no `GradeableLine`. In this same step,
  `get_frozen_gradeable_lines` settles each row with `settle_line` and returns
  the new `FrozenLine`, and `to_frozen_call` reads `period`, so the app works
  after the step. Its exclusion stays `week_not_finished` until Step 7 adds
  the NFL mapping, so no output changes mid-feature.
  Update every import and move the two test files. *Done when:* `pytest`
  passes. Every assertion in `test_nfl_ranking_rule.py` and
  `test_nfl_ranking_check.py` survives the move unchanged except the renames.
  A constants test pins the break-evens, margin, `MIN_PICKS == 200` and
  `MIN_PERIODS == 4`. `grep` finds no `nfl_ranking_rule` or `nfl_ranking_check`
  module import in `app/`, and the CLI module `app.backtest.nfl_ranking_check`
  keeps its name.

- [x] **Step 3 - Sport prop repository** (also moved `nfl_prop_odds.py`'s
  alias read; pulled `PropPredictionRow` forward from Step 6 into
  `app/services/prop_predictions.py` so the shared repository imports no NFL
  module, and `NflPropPredictionRow` is gone; rolled-back writer proof on the
  branch byte-identical to Step 0) - add
  `app/repositories/sport_props.py` with `insert_prop_line`,
  `get_lines_for_relink`, `set_line_linkage`, `get_player_aliases`,
  `get_game_index` and `insert_prop_predictions`. Each takes `sport` and binds
  it as `:sport`. Remove the NFL repository copies and point callers at the new
  module. `get_player_candidates` stays in the NFL repository, because it reads
  NFL rosters. *Done when:* `pytest` passes, and each function's test asserts
  the `sport_*` table, the `:sport` bind with value `'nfl'` and, for inserts,
  the scoped conflict target.

- [x] **Step 4 - Sport source protocol** (deviations: `NflPropSource` lives in
  `app/services/nfl/prop_source.py` so the protocol module imports no NFL
  code; `resolution_candidates` became `load_resolver(db) -> LineResolver`,
  because name resolution lives in `app/core/nfl_resolution.py` and a new
  sport must not load it; the NFL freeze module's `_row` is now public
  `prediction_row`) - add `app/services/sport_props.py`
  with `FreezableGame`, the `SportPropSource` protocol (see Data / contracts)
  and `NflPropSource`. `NflPropSource` delegates to today's NFL repository
  functions and `build_slate`. It has no callers outside tests yet. *Done when:* `pytest` passes, and a test with a
  fake session shows each `NflPropSource` method calls the expected repository
  function with the NFL week as the period.

- [x] **Step 5 - Generic PrizePicks ingest** (log lines keep their text and
  logger name through a per-sport `prizepicks_{code}_ingest` logger; the run
  tests' fetch patches now target `app.ingest.prizepicks_props`; rolled-back
  writer proof identical to Step 0; relink is covered by unit tests only) - add
  `app/ingest/prizepicks_props.py` with `run(source, dry_run)` and
  `relink(source)`. These cover league fetch, market mapping from
  `source.config`, the throttle handling, resolution and the insert through
  Step 3. `prizepicks_nfl.py` keeps its CLI, exit code 75, log lines and public
  helpers (`market_for_prizepicks_stat`, `board_nfl_leagues`,
  `unmapped_stat_counts`) as thin wrappers over `NflPropSource`. *Done when:*
  `pytest` passes, and `test_prizepicks_nfl.py` passes unchanged apart from
  import paths. A new test runs `run` with a toy source and a fake provider,
  and checks that it stores the toy sport's code on every line.

- [x] **Step 6 - Generic freeze** (deviation: `PropPredictionRow`,
  `FreezableGame` and the pure `freeze_rows` live in
  `app/core/prop_predictions.py`, because `freeze_current_period` writes
  through `repositories/sport_props.py`, which imports the row type; keeping
  both in one services module would be a circular import. `FreezeRun` carries
  the result; the NFL wrapper keeps `freeze_rows(slate, now)` and the CLI
  summary. Live dry run identical to Step 0 in 15 s, against the baseline's
  90 s, which likely hit the `get_slate_lines` stall) - add
  `app/services/prop_predictions.py`
  with `PropPredictionRow` (today's `NflPropPredictionRow` fields) and
  `freeze_rows(games, now)` over `FreezableGame(start_utc, rows)`, with the
  same kicked-off and no-start-time skips and the same counts. Add
  `freeze_current_period(db, source, dry_run)`. The NFL module keeps `_row`
  (slate line to row), which `NflPropSource.freezable_games` uses, and
  `nfl_prop_predictions.py` keeps its CLI and summary keys (`week`,
  `with_p_over_*`). *Done when:* `pytest` passes, and
  `test_nfl_prop_predictions.py` gives identical rows and counts for its slate
  fixtures.

- [x] **Step 7 - Ranking loader on the source** (the generic loader is
  `app/services/prop_ranking.py` returning `RankingCalls`; NFL's
  `load_ranking_calls(db, season)` wraps it into the unchanged
  `RankingInputs`; the exclusion is named `{period_label}_not_finished`, so no
  NFL-side mapping is needed; CLI byte-identical and `/nfl/model/ranking`
  identical except `gradedAt`) -
  `load_ranking_calls(db, source, season)` returns `RankingInputs` with
  periods. `track_record.py` (`get_ranking_record`, `build_ranking_record`)
  and the `nfl_ranking_check.py` CLI pass `NflPropSource`. `RankingRecord` and
  the `/nfl/model/ranking` response keep their field names (`finished_weeks`,
  `last_settled_week`, `coverage[].week`), and the NFL layer maps periods to
  weeks. The generic exclusion `period_not_finished` is reported as
  `week_not_finished` in the NFL CLI and response, so both stay
  byte-identical. *Done when:* `pytest` passes, including
  `test_nfl_track_record_service.py` and `test_nfl_track_record_routes.py`
  unchanged.

- [x] **Step 8 - Toy-sport end-to-end test** (the no-NFL check runs the
  pipeline in a fresh subprocess, since the pytest process already holds NFL
  modules from other tests; checked by hand: freezing a started game fails
  with `[1, 2, 3] == [1, 2]`, and importing `app.nfl.markets` from a shared
  module fails the subprocess check) -
  `tests/test_sport_props_pipeline.py` defines a `toy` config and an in-memory
  `ToySource`. It runs:
  1. league selection
  2. `freeze_rows` on two games, one already started
  3. frozen lines across 4 periods, enough for a decided slice, through
     `slice_results`

  It imports nothing from `app.nfl`, `app.core.nfl_*`,
  `app.repositories.nfl` or `app.services.nfl`, and asserts that. *Done when:*
  the test passes, and it fails if the started game's lines are frozen
  (checked once by hand).

- [x] **Step 9 - Rolled-back writer proof** (2026-10-02: NFL writer rows
  identical to Step 0; the toy rows reused a real frozen NFL line's provider
  prop id, game id, player id, team code and an alias, and all nine NFL reads
  were unchanged; with the alias read's sport filter removed by hand the check
  reported `aliases: false`; after rollback `sports` holds only `nfl` and no
  non-NFL row exists) - rerun Step 0's scratchpad script
  on the branch, in one transaction ending in `ROLLBACK`:
  1. the PrizePicks insert
  2. `set_line_linkage`
  3. `insert_prop_predictions`, inserting the same rows twice must store them
     once
  4. an insert under a second sport code added inside the transaction
     (`sports ('toy')`), whose rows must not appear in any NFL read from Step 7

  *Done when:* the NFL rows written match Step 0's row for row (ids excepted),
  the toy rows stay out of NFL reads, and row counts match after the rollback.

- [x] **Step 10 - Outputs and timing unchanged** (2026-10-02 18:12-18:35 UTC,
  against a fresh master worktree at `879bbdc`. Outputs:
  - `nfl_ranking_check`: 6 runs byte-identical to each other and to Step 0
  - freeze dry run: 18 runs byte-identical to each other and to Step 0
  - `/nfl/model/ranking`: master and branch identical except `gradedAt`
  - PrizePicks dry run: same 429 retry, log lines and exit 0; 7,538 lines
    against 7,548 from provider drift

  Timing, judged on matched pairs as 17b did:
  - ranking CLI: median 3.4 s branch against 3.9 s master
  - freeze: 9 pairs, median 10.6 s branch against 11.4 s master, with stalls
    on both sides up to 28.9 s
  - cold API ranking: 3 restarted pairs, 7.0 s total against 6.8 s (+3%);
    an earlier single cold pair read 6.5 s against 1.8 s and did not repeat

  The `:sport` bind needed no fallback. Final checks: `pytest` 2,166 passed,
  `npm run build` ok, `npm run test` 446 passed) - rerun Step 0's reads on the
  branch, back to back with a fresh master run if a cron wrote in between.
  *Done when:*
  - the CLI stdout is byte-identical (timing lines excepted)
  - the ranking JSON matches except `gradedAt`
  - the freeze dry-run summary matches when master and branch run within the
    same minute, so no game kicks off in between
  - no output takes more than 20% longer than its matched baseline, judged on
    matched runs as 17b did, because `get_slate_lines` stalls intermittently
    on both

  If the `:sport` bind regresses timing, switch that query to a literal checked
  against the registry, and record it.

## Files / areas

- New: `app/core/prop_sports.py`, `app/core/prop_ranking_rule.py`,
  `app/core/prop_ranking_check.py` (moved from the `nfl_` names),
  `app/repositories/sport_props.py`, `app/services/sport_props.py`,
  `app/services/prop_predictions.py`, `app/ingest/prizepicks_props.py`
- Changed: `app/nfl/markets.py`, `app/ingest/prizepicks_nfl.py`,
  `app/ingest/nfl_prop_predictions.py`, `app/services/nfl/prop_predictions.py`,
  `app/services/nfl/track_record.py`, `app/backtest/nfl_ranking_check.py`,
  `app/repositories/nfl.py` (copies removed, frozen-line builder settles to an
  outcome)
- Tests: `test_prop_ranking_rule.py` and `test_prop_ranking_check.py` (moved),
  `test_prizepicks_nfl.py`, `test_nfl_prop_predictions.py`,
  `test_nfl_repository.py`, new `test_prop_sports.py`,
  `test_sport_props_repository.py` and `test_sport_props_pipeline.py`
- No web, router, schema, migration or workflow changes.

## Data / contracts

**Load-bearing for 17d and item 20:**

- **`SportPropConfig`**: `code`, `league_prefix`, `segment_suffixes`,
  `board_segments`, `market_aliases`, `period_label`. A new sport adds one
  instance. A league name maps to a sport only when its normalized prefix
  equals `league_prefix` exactly, followed by nothing or a known suffix, so
  `WNBA` is never `NBA`.
- **`SportPropSource`** is the sport's whole contract with the pipeline:
  - `config`, `model_version`, `over_probability_version`
  - `load_resolver(db) -> LineResolver`, a function from a `ProviderLine`
    (name, team, position, start time) to a `LineLinkage` (player id, game
    id, reason, matched); NFL's wraps `resolve_player` and `find_game_id`
  - `current_period(db, now) -> (season, period) | None`
  - `freezable_games(db, season, period, now) -> list[FreezableGame]`
  - `frozen_lines(db, season) -> list[FrozenLine]` (already settled)
  - `finished_periods(db, season) -> set[int]`
  - `frozen_coverage(db, season) -> dict[int, tuple[int, int]]`

  17d's registry maps a sport code to its source.
- **A period** is an integer ordinal within a season, supplied by the sport.
  It is finished only when every game in it has completed. NFL's period is the
  week, so NFL verdicts are exactly 27i's. Item 20 defines NBA's period before
  any NBA frozen row exists, and records it as part of that sport's
  pre-registration.
- **The ranking rule is shared and unchanged.** The same constants decide
  every sport's slices. A sport that needs different payouts or thresholds
  needs a new rule version, never an edit to these constants.
- **Every `sport_*` read and write in the generic repository filters or sets
  `sport` from its argument.** A sport never reaches another sport's rows.
- Unchanged: `sport_prop_lines`, `sport_prop_predictions`, the
  `/nfl/model/ranking` response and every CLI's output.

## Testing

- **Test gate:** each logic step ships tests:
  - the config and league selection (Step 1)
  - the moved rule and check, plus a constants pin (Step 2)
  - the repository's table, sport bind and conflict targets (Step 3)
  - `NflPropSource` delegation (Step 4)
  - the ingest with a toy source (Step 5)
  - `freeze_rows` (Step 6)
  - the loader through the existing track-record tests (Step 7)
  - the toy-sport end-to-end (Step 8)

  NFL tests that do not name a moved module must pass untouched.
- **Integration evidence:** Step 9's rolled-back writers and Step 10's
  before-and-after comparison. There is no local test database, so every
  database is the hosted one.
- Final checks: `pytest` from `api/`. Run `npm run build` and `npm run test`
  in `web/` too; nothing changes there, but they run for completeness.

## Notes for the AI

- **Why the sport is a bind parameter now.** 17b used the literal `'nfl'` and
  deferred parameterizing to 17c, "once it re-measures". Step 10 is that
  re-measure.
  - With one sport, `sport = $1`'s generic estimate is the whole table,
    matching the literal.
  - The 9-minute plan in 17a came from missing statistics, not from the
    literal.
  - If timing does regress, the fallback is a literal checked against the
    known sport codes. A raw string from a caller is never formatted into SQL.
- **Only queries that touch nothing but `sport_*` tables go generic.** Any
  query that joins an `nfl_*` stat, roster or snap table stays in
  `app/repositories/nfl.py` behind `NflPropSource`. That is what keeps NBA from
  needing NFL columns.
- **The rule's module moves, but its meaning does not.** The 27i archive,
  `nfl_ranking_rule.py` docstring and overview cite the old path. Keep the
  docstring's pre-registration date and add one line naming the old path. The
  `/overview` refresh at `/complete` picks up the new name.
- **`app/core/` stays pure.** The config, rule and check have no I/O. The
  protocol and NFL source live in `app/services/`.
- **Cron safety:** `nfl-prop-lines.yml` runs `prizepicks_nfl` and then
  `nfl_prop_predictions` from origin/master. Nothing in this feature changes
  the schema, so master and the branch can both run against the database at
  any time. Merge order does not matter.
- `prizepicks_nfl.py`'s docstring says "API-Sports". Leave it unless the step
  already touches that line.
- **The overview was regenerated on 2026-10-02** after this spec was written.
  It now covers 17a, 17b, 26c and 26d, with the `sport_*` data model at
  `0041`. Re-run `/overview` at `/complete` so it picks up 17c's module moves.
- No em dashes in code, comments or docs.
