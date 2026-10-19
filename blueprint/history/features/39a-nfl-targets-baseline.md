# Feature: Rec Targets baseline on 2024

**From build-plan:** feature 39a (NFL Rec Targets projection)
**Status:** complete 2026-10-18; reference arm selected, both candidates rejected on 2024
**Proposed branch:** `feature/nfl-targets-baseline`

## Goal

Choose a transparent Rec Targets projection on 2024 regular-season results
alone, using pre-week player history and a fixed order of candidate arms.
Freeze the selected configuration as `nfl-targets-v1` for 39b's probability
fit and 39c's serving work. This is development evidence, not a holdout
validation or a betting recommendation.

One feature with four reviewable build steps. No visual target or web change.

## In scope

- A pure targets projection and typed inputs, independent of the v4 model.
- A read-only repository loader using the slate's regular-season, pre-week
  cutoff and baseline-season chooser, with targets-specific missing-data rules.
- Three arms in fixed order: `reference`, `moneyline`, `recent_form`.
- Selection on 2024 using 27b's paired metrics and numerical adoption rule,
  applied sequentially against the last accepted arm.
- A CLI report, recorded results, and frozen settings for `nfl-targets-v1`.

## Out of scope

- Reading or scoring 2025 outcomes. That remains 39b's single probability
  display check, the NFL holdout's eighth read. 39a adds zero holdout reads.
- P(over), distribution fitting, line grading, payouts, picks and ranking.
- Moving `receiving_targets` into `NflPropMarket` or widening any modelled
  market filter. It remains line-only in production until 39c.
- Slate, prop board, game/player pages, API schemas, frozen predictions,
  27j, workflows, report snapshots and deployments (39c and 39d).
- Changes to v4's nine markets, versions, fit tables or forward sample.
- DVP, target share, snaps, injuries, depth, environment slopes, season
  blending, additional windows/weights, and position-specific arm selection.
- Schema migrations, provider requests, data backfills and ingest runs.

## Build loop

Build one step at a time, never the whole feature at once.

1. Lay out the step before code.
2. Implement only that step, with its tests.
3. Show the diff and evidence for its done-when.
4. The user reviews and approves before the next step, and may choose an
   optional checkpoint commit. `/complete` owns the feature-level commit.

Split any diff too large to read in one sitting. Do not begin implementation
as part of this spec-writing task.

## Build steps

- [x] **Step 1 - Pure targets inputs and candidate projections.** Add
  `app/core/nfl_targets_projection.py` with the typed history/input/output
  contracts and formulas below. Reuse `choose_baseline_season` and
  `MIN_BASELINE_GAMES`; keep targets-specific configuration separate from
  `NFL_PROJECTION_MODEL_VERSION`. Start with both selected adjustments off.

  *Done when:* unit tests prove season choice, the four-observation threshold,
  zero versus missing targets, pre-week filtering, stable recent-game order,
  early-season and cross-season history, the exact three arm values, home/away
  moneyline signs, the cap and missing-input fallback. The input is not mutated.
  All-ineligible input returns a null projection with an explicit reason.

  *Built and approved 2026-10-18:* added the pure module and 31 focused
  tests. The focused suite passed, and the full Verify command passed
  (612 web tests, production build, 2,703 API tests). Verify needed broader
  filesystem access after Vite's config loader hit a sandbox access error.
  Both candidate defaults remain off. No database replay or holdout read ran.

- [x] **Step 2 - Read-only replay inputs.** Add
  `app/repositories/nfl_targets.py` with `get_targets_replay_rows(db, season,
  week)`. Load this week's completed RB/WR/TE player-games and their actual
  `targets`, then batch their completed pre-week target history and as-of team
  context. Return the typed replay rows below. Keep outcomes separate from
  projection inputs; do not route through `_slate_line`, which only accepts
  production modelled markets.

  *Done when:* recorded-SQL and row-mapping tests prove `sport = 'nfl'` on
  every shared-table alias, `REG`/completed filters, strict pre-week history,
  the RB/WR/TE driver, one row per player-game, nullable targets, roster-side
  resolution and closing-probability conversion. A known target value with
  null `target_share` survives; no SQL coalesces null targets to zero. The
  existing slate/replay readers and market enums are unchanged.

  *Built and approved 2026-10-18:* added the dedicated read-only loader
  and 17 repository tests. The loader batches history for the week's distinct
  players and reuses the slate's bounded roster CTE. Missing and invalid
  targets remain available for coverage reporting. All 48 targets tests and
  the full Verify command passed (612 web tests, production build, 2,720 API
  tests). No database replay or holdout read ran.

- [x] **Step 3 - Sequential scoring and the 2024 CLI.** Add pure replay and
  selection functions in `app/core/nfl_targets_backtest.py` and a thin CLI in
  `app/backtest/nfl_targets_projections.py`. Reuse 27b's `ReplayCase`,
  `market_metrics`, `paired` and `adoption_verdict`. Enforce one common eligible
  cohort for every arm, and the comparison order below. Do not expose an arm
  reorder or tuning option.

  *Done when:* synthetic tests cover both candidate verdicts, rejected and
  insufficient arms retaining the incumbent, recent form stacking only on
  an accepted moneyline adjustment, unique pairing keys, an empty week and
  an empty season. Report tests show metrics, paired results, coverage and
  the selected settings. `--help` works without a DB connection; the CLI
  and its run entry reject any season other than 2024 before DB access.
  Targeted tests pass without database or provider access.

  *Built 2026-10-18, awaiting review:* added the pure selector, the CLI and
  23 tests across `test_nfl_targets_backtest.py` and
  `test_nfl_targets_harness.py`. The selector chooses the eligible cohort
  once and scores every arm on it, compares moneyline against reference,
  then recent form against the accepted arm. The report shows both decisions
  and weekly exclusions. `--help` and `--season 2025` exit before any database
  module is imported. All 71 targets tests and the full Verify command passed
  (web verify and build, 2,743 API tests). No database replay or holdout read
  ran.

- [x] **Step 4 - Run 2024 and freeze the selected baseline.** Run the CLI
  once on all 2024 REG weeks 1-18, record its exact command, date, elapsed
  time, coverage, tables and selection under Results. Set the selected
  configuration constants in the projection module from those verdicts,
  with a test pinning the default projection to the selected arm. Record
  the chosen formula, eligibility and model version as 39b's handoff.

  *Done when:* the recorded tables explain both decisions, including a
  rejected or insufficient outcome; the default configuration matches them;
  no production caller imports the new projection; `NflPropMarket` and the
  v4 model/P(over) versions are unchanged. The full Verify gate passes.
  Update relevant passages of the local, ignored employer interview guide
  from measured evidence, identifying this as backtest-only and leaving
  serving/validation planned; never stage the guide.

  If no eligible cases exist, record the reason and stop this step without
  declaring a selected model ready for 39b. Do not backfill or change the
  cohort to manufacture a result. A transient DB failure can be retried with
  the identical configuration; record substantive reruns and their reason.

## Files / areas

| Area | Planned change |
|---|---|
| `api/app/core/nfl_targets_projection.py` | New pure history reduction and projections; own version and selected settings |
| `api/app/core/nfl_targets_backtest.py` | New pure eligibility, replay, sequential selection and coverage |
| `api/app/repositories/nfl_targets.py` | New batched SQL loader and typed row mapping |
| `api/app/backtest/nfl_targets_projections.py` | New read-only CLI and report formatting |
| `api/tests/test_nfl_targets_projection.py` | Projection/history cases |
| `api/tests/test_nfl_targets_repository.py` | Recorded SQL and mapping cases |
| `api/tests/test_nfl_targets_backtest.py` | Cohort, ordering and selection cases |
| `api/tests/test_nfl_targets_harness.py` | Report, CLI validation and synthetic orchestration |
| `blueprint/context/current-feature.md` | Step evidence, Results and 39b handoff |
| `docs/SportApp-Employer-Interview-Guide.md` | Local-only evidence-based update in Step 4, if present |

Existing helpers may be imported; do not refactor the shared projection
harness, slate query or prop pipeline for this isolated backtest.

## Data / contracts

No schema or public API change. These are load-bearing for 39b and 39c.

### Identity, observations and eligibility

- Market: stored string `receiving_targets`. Targets settle from
  `nfl_player_weekly_stats.targets`.
- Version: `NFL_TARGETS_MODEL_VERSION = "nfl-targets-v1"`, independent of
  `opponent-dvp-tg-blend-usage-snap-v4`. This version becomes fixed after
  Step 4; later projection changes need a new version and probability fit.
- Positions: RB, WR and TE. One case per `(player_id, game_id,
  "receiving_targets")`; no duplicate rows or position-specific winners.
- Driver: completed 2024 REG player-games with a stored weekly-stat row.
  No historical PrizePicks lines exist for these games. Each case is a
  synthetic full-game, standard slot, not an observed provider listing.
  Never require a positive actual or a current-season target-volume minimum.
- History: completed REG weekly-stat rows satisfying
  `season < S OR (season = S AND week < W)`, including already-loaded older
  seasons. No target-week games contribute, even if played earlier that week.
  Do not load newer seasons and filter them after the query.
- A target observation is a finite nonnegative value. Zero is a known count;
  null, negative or nonfinite values are unknown/invalid and excluded, counted
  separately. `target_share` is not required. Missing stat rows are not
  synthesized as zero games; this replay has the same stat-row selection
  limitation as 27b, and is not a sample of every player who took a snap.
- Apply `choose_baseline_season` to per-season counts of valid target
  observations. Require at least `MIN_BASELINE_GAMES = 4` in its chosen season
  for scoring or a usable projection. No position-average imputation.
- Recent history is the newest five valid observations across eligible prior
  seasons, ordered by season, week, kickoff (null last), then game id, all
  descending. With four available, use those four. The window is fixed at five
  to match the slate's existing recent-form evidence window.
- Early 2024 weeks may lack qualifying history because older data is not
  stored. Print that coverage loss; do not use full-season 2024 averages or
  backfill another season in this feature.

Typed dataclasses, with no DB or Pydantic dependencies in core:

| Shape | Fields / meaning |
|---|---|
| `TargetsObservation` | `game_id`, `season`, `week`, `start_utc: datetime | None`, `targets: float | None` |
| `TargetsProjectionInput` | Target `season`, `week`, immutable sequence of observations, `home_market_prob: float | None`, `player_is_home: bool | None` |
| `TargetsProjection` | `projection: float | None`, `baseline_season: int | None`, `baseline_reason`, `games_in_sample`, `recent_games`, quality flags |
| `TargetsReplayRow` | `player_id`, `game_id`, `week`, `position`, projection input, `actual: float | None` |

Keep actuals out of `TargetsProjectionInput`. Null/invalid actuals exclude the
case from every arm's score, counted in coverage. Missing moneyline data never
removes an otherwise eligible case. No real line, edge or P(over) is required.

### Candidate formulas, fixed before scoring

Let `B` be the unrounded mean of valid target counts in the chosen baseline
season, and `R` the unrounded mean of the recent history above.

```text
team_probability = home_market_prob           if player's as-of team is home
team_probability = 1 - home_market_prob       if player's as-of team is away
factor = 1 + clamp(team_probability - 0.5, -0.08, +0.08)
factor = 1                                   if probability or team side is unknown

reference   = round(B, 2)
moneyline   = round(B * factor, 2)
recent_base = 0.5 * B + 0.5 * R
recent_form = round(recent_base * accepted_factor, 2)
```

`accepted_factor` is `factor` only if the moneyline candidate was accepted;
otherwise 1. The recent window (5), weight (0.5) and moneyline cap (0.08,
27b's existing model cap) are fixed here, not fitted or searched. Round once
at the end, and score the same two-decimal number a later caller will serve.

The moneyline input follows 27b: de-vig NFLverse's stored home/away closing
moneylines via `market_home_probability`. This is a pre-kickoff proxy, not a
historical snapshot as of the start of the week. Label this limitation in
the report and Results; no fabricated fetched timestamp or freshness claim.
Future serving will use fresh pre-kickoff book probabilities under 39c.
Only finite probabilities strictly between 0 and 1 are usable.

Resolve the player's side by the slate's as-of weekly-roster rule, including
CUT/RET and its never-rostered fallback. Reuse the existing repository helper
where possible. Do not infer the side from the target game's outcome stats.
An unresolved or nonparticipant team gives no moneyline adjustment and is
counted in coverage; mutable player-team fallback remains a stated replay
limitation. Missing context never silently means home.

### Comparison and selection rule

Pre-registered here on 2026-10-18, before any 39a result is scored:

1. The season-average `reference` starts as incumbent.
2. Compare `moneyline` against `reference` on all common eligible 2024 cases.
   Accept it only under 27b's rule below; otherwise retain `reference`.
3. Compare `recent_form` against that incumbent, retaining any accepted
   moneyline factor. Accept it only under the same rule.
4. Freeze the final incumbent's configuration for all three positions.

Reuse 27b's rule unchanged numerically: at least 300 paired cases, relative
MAE improvement of at least 1.0%, and mean paired
`|candidate error| - |incumbent error|` strictly below zero by more than 2 SE.
Below 300 is `insufficient`; otherwise failure is `reject`. Both retain the
incumbent. Do not select by RMSE, bias, position slices or the lowest observed
MAE outside this sequence. An all-zero incumbent MAE cannot be improved.

All arms score the identical eligible keys. Assert unique keys before using
`paired`, which otherwise silently collapses duplicate reference keys. Report
pooled-market decisions; position and week tables are descriptive only.
Accepting on 2024 chooses a development baseline, not an out-of-sample verdict.

### CLI and frozen handoff

```text
cd api
.venv\Scripts\python.exe -m app.backtest.nfl_targets_projections --season 2024
```

The default and sole accepted CLI season in 39a is 2024; no `--write`, tuning,
arm selection or production mode. The loader can accept another explicit
season for reuse by 39b, but 39a's CLI/run entry cannot execute it. No call to
the old `nfl_projections` CLI, whose default season is 2025.

Print version, season, rule, exact formulas/order, the closing-line limitation,
per-arm n/MAE/RMSE/bias/share-below by market and position, both paired rows
with named incumbents, and final settings. Include weekly coverage: total
driver rows, missing/invalid actuals, missing/thin baseline, scored cases,
missing moneyline and unresolved side. Context counts may overlap; exclusions
must reconcile to the driver total. Empty data produces a clear no-selection
report, never metrics on an empty list or a success claim.

Freeze named booleans for selected moneyline scaling and recent-form blending
in `nfl_targets_projection.py`. Expose one `project_targets` function with the
selected configuration by default and explicit candidate settings for replay.
39b must fit this exact selected projection and eligibility; 39c must call the
same function. An insufficient candidate leaves the valid reference available;
zero eligible cases do not establish a usable model.

## Testing

- Every logic-bearing step ships its passing unit tests. Use synthetic
  histories/results and fixed dates; no real DB or external APIs in tests.
- Projection: season switching at four known observations, no future/current
  week leakage, null/zero separation, deterministic recent ordering, exact
  rounding, moneyline sign/cap/fallback, and no accidental v4 adjustment.
- Repository: recorded SQL plus row mappings, sport and time bounds, nullable
  values and historical-team behavior. Live evidence belongs to Step 4.
- Selection: shared cohort, duplicate rejection, adoption threshold/strict SE
  behavior through reused 27b functions, each sequential path and empty data.
- CLI: report contents and pre-connection rejection of 2025 or another season.
  The test may use synthetic season labels; it never reads holdout data.
- Run affected tests during each step from `api/` with
  `.venv\Scripts\python.exe -m pytest` and the named target test files.
- Final Verify, as documented in `AGENTS.md`, with the API venv active:
  `npm --prefix web run verify && cd api && python -m pytest`.
  In this PowerShell shell use a compatible invocation or run the same halves
  sequentially with the explicit venv interpreter, requiring both to pass.
- `/check` observes the CLI output and frozen settings against this spec.
  There is no browser or screenshot requirement for this backend-only feature.

## Results

**Run:** 2026-10-19 01:45 UTC (2026-10-18 Central), once, 32.6 s, no rerun.

```text
cd api
.venv\Scripts\python.exe -m app.backtest.nfl_targets_projections --season 2024
```

**Coverage, 2024 REG weeks 1-18:**

| Driver rows | Missing / invalid actual | No baseline | Thin baseline | Scored |
|---:|---:|---:|---:|---:|
| 5,200 | 0 / 0 | 511 | 1,334 | 3,355 |

- Missing moneyline, unresolved side, null and invalid history: all 0.
- A read-only count confirmed 5,200 completed 2024 RB/WR/TE stat rows
  (the roster join drops none), none with null targets or a missing closing
  moneyline.
- No 2023 stats are stored (seasons 2024 to 2026 only), so week 1 has no
  baseline and weeks 2-4 score nothing; week 5 is the first scored week (150).
  Not backfilled, per the spec. The same count query listed per-season row
  totals, including 2025's; no 2025 target value or outcome was read.

**Per-arm metrics (pooled, n = 3,355; bias = projection minus actual):**

| Arm | MAE | RMSE | Bias | Share below |
|---|---:|---:|---:|---:|
| reference | 1.698 | 2.351 | -0.165 | 54.2% |
| moneyline | 1.720 | 2.386 | -0.166 | 53.7% |
| recent_form (unscaled) | 1.691 | 2.337 | -0.125 | 54.1% |

By position, reference MAE: RB 1.267 (1,015), TE 1.701 (765), WR 1.974
(1,575). Descriptive only.

**Sequential decisions:**

| Candidate vs incumbent | n | MAE change | Paired diff | SE | Verdict |
|---|---:|---:|---:|---:|---|
| moneyline vs reference | 3,355 | +1.28% | +0.022 | 0.005 | reject |
| recent_form vs reference | 3,355 | -0.40% | -0.007 | 0.006 | reject |

- **Moneyline** made errors worse, beyond noise, at every position.
- **Recent form** was slightly closer but missed both the 1.0% MAE bar and
  the 2 SE bar, so it is rejected. Comparing it against the reference was
  correct because moneyline had been rejected.

**Selected:** `reference`. `SELECTED_MONEYLINE_SCALING = False` and
`SELECTED_RECENT_FORM = False` stay as already set;
`test_default_projection_is_the_reference_arm_selected_on_2024` pins the
default to that arm.

**Limitations:** development selection on 2024, not validation; synthetic
standard slots, not historical PrizePicks listings; the moneyline input is
NFLverse's closing price, not a week-start snapshot; early weeks are thin
because no 2023 history is stored.

**Checks:** 72 targets tests and the full Verify command pass (web verify
and build, 2,744 API tests). No production module imports the new projection;
`NflPropMarket`, `opponent-dvp-tg-blend-usage-snap-v4` and `nfl-pover-v1`
are unchanged from `master`. **2025 holdout reads by 39a: 0.**

### 39b handoff

- **Version:** `nfl-targets-v1`, now fixed.
- **Formula:** `round(B, 2)`, where `B` is the unrounded mean of valid
  (finite, nonnegative) target counts in the season `choose_baseline_season`
  picks from per-season valid counts. No moneyline, recent-form, DVP or usage
  adjustment.
- **Eligibility:** RB, WR, TE; completed REG weekly-stat history strictly
  before the target week; at least `MIN_BASELINE_GAMES = 4` valid counts in
  the chosen season, otherwise a null projection.
- **Call:** `project_targets(input)` with its defaults. 39b fits P(over) on
  exactly this projection and eligibility on 2024, and checks its display
  gate once on 2025 (the NFL holdout's eighth read). 39c serves the same call.

## Notes for the AI

- Core stays pure; repositories own SQL; CLI owns DB/session setup and printing.
  Python 3.11, full types, `X | None`, no `Any`, no new heavy dependencies.
- Preserve all sport/provider filters and import boundaries. The dedicated
  loader needs no `sport_game_odds` query and spends no provider quota.
- The existing usage average requires both `targets` and `target_share`.
  Do not reuse it as a targets baseline or widen its filter for this feature.
- Do not widen `REPLAY_MARKETS_BY_POSITION`, `STAT_COLUMN_BY_MARKET`,
  `NflPropMarket`, `MODELLED_MARKET_FILTER` or production readers to make this
  backtest work. No production wiring is part of a development-arm acceptance.
- Preserve `nfl-pover-v1` and every v4 frozen row. 39b chooses a separate
  targets probability version, 39c serves/freezes it, and 39d separates grading.
- Do not inspect 2025 results to settle design questions. Formula changes after
  review require an explicit spec amendment before scoring; never hide a tried
  arm or call 2024 selection validation.
- Never run a model replay on a production request path. This CLI stays local
  and read-only; Render's 512 MB request constraint is unchanged.
- No plan, overview, source, branch or commit changes during `/feature`.
  Stop with the concrete spec for review, as the feature skill requires.
