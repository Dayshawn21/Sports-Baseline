# Feature: Frozen NBA predictions

**From build-plan:** feature 20g3
**Status:** complete (2026-10-07)

## Goal

Store a record of what the NBA reference projection said about each PrizePicks
line before tip-off, so 20g4's forward ranking check has something to grade.
`NbaPropSource` implements the full `SportPropSource` (freezing and grading),
joins `PROP_SOURCES`, and `nba-prop-lines.yml` freezes predictions after each
snapshot.

**Why now:** the season opens 2026-10-20. Line history exists only from the
day the app stores it, and freezing starts the forward sample, so every week
this ships before opening night is a week the 27i rule can count.

## In scope

- `NbaPropSource` gains the five `SportPropSource` methods plus
  `model_version` and `over_probability_version`, then joins `PROP_SOURCES`.
- **Freezing:** each linked, full-game, modelled (`NbaPropMarket`) line in the
  current regular-season week, at its latest pre-tip snapshot, projected by
  `project_line` exactly as the game page serves it.
- **Grading inputs** (used by 20g4, built here because the protocol needs
  them): `frozen_lines` settled against `nba_player_game_stats`,
  `finished_periods`, `frozen_coverage`.
- A shared freeze CLI (`python -m app.ingest.prop_predictions --sport ...`),
  with `nfl_prop_predictions` kept as an unchanged thin entry point and a new
  `nba_prop_predictions` entry point beside it.
- A freeze step in `nba-prop-lines.yml` after each snapshot.

## Out of scope

- **20g4:** the ranking-check CLI and workflow Summary, `/nba/model`, any
  slice verdict. No picks, no edge, no signal color anywhere.
- **Play-in and playoff lines.** `PIN`/`PST` games have `week` NULL, and the
  shared pipeline's period is an integer, so they are never frozen or graded.
  Regular season only; a later item decides whether playoffs get a period.
- NBA prop board, projection changes, a new P(over) fit, schema changes.
- Any change to NFL's freeze output or its workflow.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Frozen row builder (pure)** - `app/core/nba_prop_predictions.py`:
  `prediction_row(line, projection, now) -> PropPredictionRow` from a stored
  line (id, market, odds type, line, fetched time) and its `NbaLineProjection`.
  `edge` is None (NBA serves a gap, not an edge); `quality_flags` are the
  projection's flags; `feature_snapshot` holds `games_in_sample`,
  `prior_minutes`, `gap`, `line`, `odds_type`, `market`, `segment`,
  `line_fetched_at`. An ineligible line freezes with a null projection and its
  flag, never skipped. *Done when:* `tests/test_nba_prop_predictions.py`
  passes, covering an assists line with P(over) (`nba-pover-v1`), a points
  line with no P(over) (version None), an ineligible line, and that the row
  matches what `project_line` returned field for field.

- [x] **Step 2 - Frozen line settlement (pure)** - in the same core module,
  `settle_frozen(market, line, box_row, game_has_box_scores) -> str`:
  - game has no box-score rows at all -> `stats_not_loaded`
  - no row for the player, or a DNP row -> `void_dnp` (PrizePicks voids a
    player who does not play)
  - a played row whose market value is None -> `missing_stat`
  - otherwise `prop_settlement.settle(value, line)`: `over`, `under`, `push`

  Values come from `line_only_value`, the one NBA settlement rule. *Done
  when:* tests cover each branch, a combo market (PRA) summing correctly, and
  a whole-number line pushing.

- [x] **Step 3 - Freeze queries** - in `app/repositories/nba.py`:
  - `get_current_week(db, now)`: `(season, week)` of the next `REG` game with
    `start_utc > now` (no NFL-style grace: `freeze_rows` already skips started
    games), else the latest loaded `REG` week, else None.
  - `get_week_modelled_lines(db, season, week)`: each linked provider prop on
    the week's `REG` games, latest snapshot before tip, with line id, game id,
    game date and start time, under `NBA_MODELLED_MARKET_FILTER`, full game
    only, every `sport_*` reference on `'nba'`.

  *Done when:* recorded-SQL tests (the `_RecordingSession` pattern in
  `tests/test_nba_repository.py`) show the `'nba'` filters, `game_type =
  'REG'`, the modelled filter, `segment = 'full_game'` and the pre-tip
  condition.

- [x] **Step 4 - Grading queries** - in `app/repositories/nba.py`:
  - `get_frozen_gradeable_lines(db, season) -> list[FrozenLine]`: each
    provider prop's latest frozen pre-tip row (line fetched and prediction
    generated before `start_utc`) on a completed `REG` game, joined to the
    player's box-score row and a per-game "has box scores" flag, settled by
    Step 2. Same `DISTINCT ON` order as NFL's.
  - `get_finished_weeks(db, season)`: weeks whose every `REG` game is
    `completed`, `postponed` or `canceled` (20b's rule), **and** whose every
    completed `REG` game has box-score rows, so a week never counts before
    its stats load.
  - `get_frozen_coverage(db, season)`: per week, (gradeable full-game
    modelled lines on completed `REG` games, how many have any frozen pre-tip
    row).

  *Done when:* recorded-SQL tests pin the filters above, and a mapping test
  shows a fake row turning into the expected `FrozenLine` with its outcome.

- [x] **Step 5 - `NbaPropSource` joins the registry** -
  `app/services/nba/prop_source.py` gains `model_version`
  (`NBA_PROJECTION_MODEL_VERSION`), `over_probability_version`
  (`nba-pover-v1` from the fit module), and the five methods. A small service
  function builds `FreezableGame`s for a week: lines from Step 3, prior games
  from `get_prior_games` once per distinct game date, `project_line` per line,
  rows from Step 1. `PROP_SOURCES` gets `"nba": NbaPropSource`. *Done when:*
  `prop_source("nba")` returns it; `tests/test_sport_registry.py` swaps its
  unknown-sport example for another code; a service test with fake repository
  data shows a started game skipped and an upcoming one frozen; the full
  `pytest` run passes, including `test_sport_props_pipeline.py` (the shared
  modules still never load `sport_registry` or NFL code).

- [x] **Step 6 - Freeze CLI and workflow** - move the body of
  `app/ingest/nfl_prop_predictions.py` into `app/ingest/prop_predictions.py`
  (`--sport`, `--dry-run`; summary label by sport, period label "week" for
  both). `nfl_prop_predictions` keeps its command line and log output and
  calls it with `nfl`; `nba_prop_predictions` is the NBA entry point. Add a
  "Freeze pre-tip predictions" step to `nba-prop-lines.yml` and update its
  header comment. *Done when:*
  - `python -m app.ingest.nfl_prop_predictions --dry-run` prints the same
    summary keys as on master
  - `python -m app.ingest.nba_prop_predictions --dry-run` reports
    `2026 week 1` with a frozen count for the stored opening-night lines and
    a `with_p_over_*` count (assists only)
  - a real run inserts rows; an immediate re-run inserts 0
  - `load_ranking_calls(db, prop_source("nba"), 2026)` runs without error
    against the database and reports nothing settled yet
  - the workflow YAML parses and its new step runs only after the snapshot
    step succeeds

## Files / areas

- New: `api/app/core/nba_prop_predictions.py`, `api/app/ingest/prop_predictions.py`,
  `api/app/ingest/nba_prop_predictions.py`, `api/tests/test_nba_prop_predictions.py`
- Changed: `api/app/repositories/nba.py`, `api/app/services/nba/prop_source.py`
  (or a sibling `services/nba/prop_predictions.py` for the week builder),
  `api/app/services/sport_registry.py`, `api/app/ingest/nfl_prop_predictions.py`,
  `.github/workflows/nba-prop-lines.yml`, `api/tests/test_nba_repository.py`,
  `api/tests/test_sport_registry.py`

## Data / contracts

No schema change. Rows go to `sport_prop_predictions` with `sport = 'nba'`.

**Load-bearing for 20g4:**
- **NBA frozen row:** `model_version` `nba-reference-v1`;
  `over_probability_version` `nba-pover-v1` when P(over) was served, else
  NULL; `projection`, `p_over`, `p_under` nullable; `edge` always NULL;
  `quality_flags` from `NbaProjectionFlag`; `feature_snapshot`:

  ```
  { games_in_sample, prior_minutes, gap, line, odds_type, market,
    segment: 'full_game', line_fetched_at }
  ```
- **Period:** the regular-season `sport_games.week`; current period is the
  week of the next `REG` game not yet started.
- **Settlement outcomes:** `over`, `under`, `push`, `void_dnp`,
  `missing_stat`, `stats_not_loaded`. Only `over` and `under` become calls.
- **Finished week:** every `REG` game `completed`/`postponed`/`canceled`, and
  every completed one has box scores.
- **`prop_source("nba")` resolves**, so `load_ranking_calls` works for NBA
  unchanged.

## Testing

- Test gate on. Logic tests: Step 1 row builder, Step 2 settlement, Steps 3-4
  recorded-SQL and row-mapping tests, Step 5 week builder and registry.
- Step 6 rides on the dry run, a real run, the idempotent re-run, and the NFL
  dry run matching master's output.
- `cd api && .venv\Scripts\python.exe -m pytest`. No web change.

## Notes for the AI

- **Freeze what the page serves.** Same `project_line`, same
  `get_prior_games` history depth, same latest-pre-tip line rule as
  `_game_prop_lines`. A test should make the page and the freeze agree on one
  line.
- Every `sport_*` reference carries `'nba'`; never read `PRE`; apply
  `NBA_MODELLED_MARKET_FILTER` to every reader that freezes or grades.
- The shared modules (`app/core/prop_*`, `app/services/prop_*`,
  `app/ingest/prizepicks_props.py`) must not import `sport_registry`. The new
  `app/ingest/prop_predictions.py` is an entry point and may.
- Freezing writes real rows on a real database. The dry run first; a real run
  before 2026-10-20 is legitimate (every opening-night line is pre-tip) and
  starts the sample.
- PrizePicks snapshots are free but rate-limited; this feature needs no new
  snapshot. Use the stored lines.
- **Week boundary, accepted:** only the current week freezes, so Monday's
  lines posted before Sunday's 22:15 UTC run wait for Monday's 16:30 UTC run.
  Monday games tip after 23:00 UTC, so they are still frozen before tip.
- Do not touch `nfl-prop-lines.yml`; the NFL entry point's command stays the
  same.

## Outcome (2026-10-07)

- **First freeze:** 2026 week 1 (opening night, 2026-10-20), 190 modelled lines
  frozen, all with a projection; 20 assists lines carry P(over) (12 demon, 5
  goblin, 3 standard); one whole-number assists line is flagged
  `integer_line`, the other 169 `no_over_probability`. A re-run inserted 0.
- **NFL unchanged:** `nfl_prop_predictions --dry-run` printed byte-identical
  output before and after the shared-CLI move (2026 week 5, 1300 frozen).
- **Grading inputs live:** `load_ranking_calls(db, prop_source("nba"), 2026)`
  runs; 2025-26 reads all 25 weeks finished; nothing is settled for 2026 yet.
- **Not in the spec, added in build:** `NbaFreezeLine` carries `game_date` and
  `start_utc`, and prior games are keyed by game date then player, because a
  player can play twice in one week.
- **Effective on push:** `nba-prop-lines.yml` freezes only once this commit is
  on the pushed default branch.
