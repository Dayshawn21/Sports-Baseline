# Feature: Rec Targets over probability

**From build-plan:** feature 39b (second of 39's four parts)
**Status:** complete 2026-10-18; checked once on 2025, verdict hide (P(over) not shown)
**Proposed branch:** `feature/nfl-targets-over-probability`

## Goal

Turn the `nfl-targets-v1` projection (39a) into P(over line) for Rec Targets,
and decide once whether it may be shown. The method is 27g's: an empirical
distribution of `actual / projection`, read at any line with
`over_probability`. The fit is made on 2024 alone and scored once on 2025
under 27g's display rule, kept as Rec Targets' own constants. This is the
**2025 holdout's eighth read**, and it takes no projection verdict.

**Why:** a mean target count misreads over/under (39a's reference sits above
the actual in 54.2% of 2024 cases), and 39c's frozen predictions and 39d's
ranking check pick only on a side's probability. If the check hides P(over),
39c still serves the projection, gray, with no probability, as 20g1 left
eight NBA markets.

**Nothing is served.** A CLI report and a generated fit module; 39c reads it.

## Design reference

None. A CLI report and a generated module, no UI.

## In scope

- **Version, fixed now:** `NFL_TARGETS_OVER_PROBABILITY_VERSION =
  "nfl-targets-pover-v1"`, separate from `nfl-pover-v1`.
- **A pure module, `app/core/nfl_targets_over_probability.py`:** case
  building for any season from 39a's replay rows, a per-position fit, scoring
  on synthetic lines, and the display verdict with its own constants. It
  reuses unchanged `ratio_quantiles`, `over_probability`
  (`app/core/nfl_over_probability.py`), `synthetic_lines`, `calibrate`,
  `normal_over_probability` (`app/core/nfl_over_probability_calibration.py`)
  and `project_targets` with its defaults.
- **A fit CLI, `python -m app.backtest.nfl_targets_over_probability_fit`:**
  loads 2024 and 2025 replay rows through 39a's loader, fits on 2024, scores
  2025 once, prints the report, and with `--write` freezes the result.
- **One scored run**, its verdict under Results, plus a local interview guide
  update.

## Out of scope

- Serving or freezing anything: `NflPropMarket`, `MODELLED_MARKET_FILTER`,
  the slate, board, game and player pages, a reader helper for the fit,
  frozen rows, workflows (39c).
- 27j per-version grading and `/nfl/model` (39d).
- Any change to `nfl-targets-v1`, 39a's selector, its 2024-only CLI guard, or
  v4's markets, versions, fit table or frozen sample.
- A second method, a refit on 2025, a per-position verdict, or splits beyond
  position. If the pooled check hides, a new method is a new item tried on
  2024 first.
- Integer lines: they can push, which v1 does not model, so they read None
  (27g's rule). PrizePicks Rec Targets standard lines are x.5 in practice.
- Goblin and demon lines (39 is standard only); the synthetic lines still
  span 0.5x to 1.5x, as 27g's do, so calibration is judged across lines.
- Backfilling 2023 stats to thicken early 2024 weeks.

## Build loop

Build one step at a time, never the whole feature at once.

1. Lay out the step before code.
2. Implement only that step, with its tests.
3. Show the diff and the evidence for its done-when.
4. The user reviews and approves before the next step, and may choose an
   optional checkpoint commit. `/complete` owns the feature-level commit.

Never accept a step you haven't read. If a diff is too big to review, the
step was too big, so split it.

## Build steps

- [x] **Step 1 - Cases, fit, scoring and the display rule (pure).** In
  `app/core/nfl_targets_over_probability.py`:
  - `NFL_TARGETS_OVER_PROBABILITY_VERSION` and the rule constants below.
  - `targets_cases(rows, season) -> TargetsCaseSet`: for rows of one season,
    REG weeks 1-18, RB/WR/TE, unique keys (raise on a duplicate, a wrong
    season or position), project with `project_targets(row.input)` defaults,
    and keep rows with a valid actual and a non-null projection as 27b
    `ReplayCase`s (`market="receiving_targets"`). Coverage counts: driver
    rows, missing/invalid actual, no baseline, thin baseline, zero
    projection, cases. It never calls 39a's `validate_development_season`.
  - `fit_positions(cases) -> dict[str, PositionFit]`: per position, ratio
    quantiles of cases with a positive projection and the standard deviation
    of `actual - projection` (the normal baseline), from 2+ cases.
  - `score_cases(fits, cases) -> list[ScoredLine]`: each case with a fit at
    each `synthetic_lines(projection)`, fitted and normal P(over), and the
    over flag.
  - `targets_display_verdict(cases_n, report, normal_brier)`, recomputing the
    worst bin from `report.bins` with this module's minimum bin size.

  *Done when:* unit tests cover: a 2025 row accepted (no 2024-only guard) and
  a wrong-season, wrong-position or duplicate row rejected; null, invalid and
  thin-baseline rows counted and excluded; a zero projection kept out of fit
  and scoring and counted; quantiles and sigma on a known set; a position with
  no fit not scored; synthetic lines and the over flag for a known case; each
  verdict branch (299 / 300 cases, ECE exactly 0.02, a 200-pair bin exactly
  0.05 off, a 199-pair bin far off ignored, Brier equal to the normal's
  passing); a constants test pinning the rule values, the new version, and
  that it differs from `nfl-pover-v1`. No database access.

- [x] **Step 2 - The fit CLI and report (no live run).**
  `app/backtest/nfl_targets_over_probability_fit.py`, with no season option:
  loads 2024 weeks 1-18 and fits on them, then loads 2025 weeks 1-18 and
  scores them. The report prints:
  - a header naming the fit and scored seasons, both versions, the rule text,
    and "2025 holdout read 8 (no projection verdict)";
  - coverage per season (Step 1's counts);
  - the pooled verdict row: cases, pairs, ECE, worst gap, Brier, normal
    Brier, verdict, failed checks;
  - information only: the same row per position, per projection tercile
    (cut on 2025 cases), and at the synthetic line nearest the projection
    (mean predicted, observed, normal);
  - the pooled reliability bins.

  *Done when:* a report test on synthetic scored lines checks the verdict row,
  one position row and one nearest-line row; an empty 2025 case set prints
  `insufficient` with no metrics; `--help` exits without importing the
  database module (the 39a pattern). The CLI is not run against the database
  in this step.

- [x] **Step 3 - Run once and freeze.** `--write` renders
  `app/core/nfl_targets_over_probability_fit.py` (generated, never
  hand-edited): `FIT_SEASON = 2024`, `SCORED_SEASON = 2025`,
  `FIT_PROJECTION_MODEL_VERSION = "nfl-targets-v1"`,
  `OVER_PROBABILITY_VERSION`, `SHOWN: bool`, and `QUANTILES_BY_POSITION`
  (the 2024 fit, four decimals) only when shown, else empty. Run
  `--write` exactly once and paste the command, date, elapsed time and
  output under Results.

  *Done when:* a render test on a small fit checks the module text for both a
  shown and a hidden verdict; a test imports the generated module and checks
  its `FIT_PROJECTION_MODEL_VERSION` equals `NFL_TARGETS_MODEL_VERSION`, its
  version equals `NFL_TARGETS_OVER_PROBABILITY_VERSION`, and, if shown, RB,
  WR and TE each hold 41 non-decreasing quantiles; no production module
  imports the new modules; `NflPropMarket`, v4 and `nfl-pover-v1` are
  unchanged; the full Verify gate passes. Update the local, ignored employer
  interview guide from the measured result (fit and display check only;
  serving and grading still planned); never stage it.

## Files / areas

| Area | Change |
|---|---|
| `api/app/core/nfl_targets_over_probability.py` | New: cases, fit, scoring, verdict, version |
| `api/app/backtest/nfl_targets_over_probability_fit.py` | New: CLI, report, module renderer |
| `api/app/core/nfl_targets_over_probability_fit.py` | New, generated by Step 3 |
| `api/tests/test_nfl_targets_over_probability.py` | Step 1 tests |
| `api/tests/test_nfl_targets_over_probability_fit.py` | Step 2 and 3 tests |
| `blueprint/context/current-feature.md` | Step evidence and Results |
| `docs/SportApp-Employer-Interview-Guide.md` | Local only, Step 3, if present |

Read only: `app/core/nfl_targets_projection.py`,
`app/core/nfl_targets_backtest.py`, `app/repositories/nfl_targets.py`,
`app/core/nfl_over_probability.py`,
`app/core/nfl_over_probability_calibration.py`,
`app/core/nba_over_probability.py`, `app/backtest/nba_over_probability_fit.py`
(the layout to mirror).

## Data / contracts

No schema or API change.

**Load-bearing for 39c and 39d:**
- `NFL_TARGETS_OVER_PROBABILITY_VERSION = "nfl-targets-pover-v1"`; frozen
  Rec Targets rows carry it beside `nfl-targets-v1`, so 39d grades them as
  their own sample.
- **Groups are positions** (RB, WR, TE), one market, as 27g groups by market
  and position. 39c reads `QUANTILES_BY_POSITION[position]`.
- **The fit is read only while** `FIT_PROJECTION_MODEL_VERSION ==
  NFL_TARGETS_MODEL_VERSION` and `SHOWN` is true; otherwise P(over) is null,
  never 0.5 (27g's rule).
- **P(over) is `over_probability(quantiles, projection, line)`**: None for an
  integer line or a projection at or below zero.
- A line gets P(over) only on 39a's eligibility (a non-null
  `project_targets` result), the gate the check scored.
- **What is frozen is the scored 2024 fit**, never a refit on 2025.

**The pre-registered display rule** (fixed when this spec is approved, before
any fit is scored; 27g's values, Rec Targets' own constants). Rec Targets is
**shown** only when all hold on its pooled 2025 pairs (positions pooled):

1. at least 300 cases;
2. ECE of 0.02 or less across its synthetic-line pairs (10 bins);
3. no bin holding 200 or more pairs is off by more than 0.05;
4. Brier no worse than the normal baseline (per-position 2024 sigma) on the
   same pairs.

Below 300 cases the verdict is `insufficient`, otherwise `hide`. Position,
tercile and nearest-line rows are information only and never change it. The
check runs once; rerunning the same deterministic code (as `--write` does) is
the same read, any change to method or rule after the run is not allowed.

**Expected sample:** 2024 fits on 39a's 3,355 cases (RB 1,015, TE 765,
WR 1,575). 2025 scores every REG week, with week 1 baselines from 2024
(flagged `stale_baseline_season`, as serving would be).

## Testing

- Test gate on: Step 1 unit tests, Step 2 report and CLI tests, Step 3
  render and generated-module tests. Synthetic data and fixed dates only;
  no database or provider in tests, and no test reads 2025 outcomes.
- From `api/`: `.venv\Scripts\python.exe -m pytest tests/test_nfl_targets_over_probability.py tests/test_nfl_targets_over_probability_fit.py` after each step.
- Final Verify from the repo root with the API venv:
  `npm --prefix web run verify && cd api && python -m pytest` (or the two
  halves with the explicit venv interpreter).
- `/check` reads the CLI output and the generated module against this spec.
  No browser evidence; no web change.

## Notes for the AI

- **Holdout bookkeeping:** the 2025 replay has been read seven times (27b's
  F-02, 27c, 27d, 27e, 27f, 27g's fit, 27k). This is the eighth. No live CLI
  run before Step 3, and Step 3 runs it once. Do not query 2025 targets or
  outcomes to settle any design question.
- **Expect a hide.** Targets are small counts, and 27g's receptions hid on
  ECE and worst bin. That is the rule working; do not switch method,
  grouping or bins mid-feature, and do not report a per-position pass as a
  show.
- Leave 39a's `validate_development_season` and `select_baseline` alone; the
  2024-only guard still protects selection. Build cases in the new module.
- Load rows with 39a's `get_targets_replay_rows(db, season, week)` per week;
  its history query is strictly pre-week and stops at the target season, so
  2026 is never read.
- Mirror `app/backtest/nba_over_probability_fit.py` and its generated module;
  render with a function the test can call.
- Core stays pure, repositories own SQL, `X | None`, no `Any`, dataclasses
  inside, no em dashes, comment only the why. Nothing touches the Render
  request path.

## Results

**Run:** 2026-10-19 02:23 UTC (2026-10-18 Central), once, 17.1 s, no rerun.
**2025 holdout reads: 8** (this run); no projection verdict.

```text
cd api
.venv\Scripts\python.exe -m app.backtest.nfl_targets_over_probability_fit --write
```

**Verdict: hide.** Rec Targets P(over) is not shown. The generated
`app/core/nfl_targets_over_probability_fit.py` holds `SHOWN = False` and no
quantiles, so 39c serves the projection gray with a null P(over).

| Cases | Pairs | ECE | Worst bin | Brier vs normal | Failed on |
|---:|---:|---:|---:|---|---|
| 4,624 | 16,822 | 0.043 | 0.078 | 0.2022 vs 0.2033 | ECE, worst bin |

**Reading it:**
- **It beats the normal on Brier but is miscalibrated.** It fails on
  calibration, not sample: ECE is more than twice the 0.02 limit.
- **The 2024 shape does not carry to 2025.** At the line nearest the
  projection it predicts 0.434 over and 0.406 is observed (normal 0.488);
  every position overstates the over by 2.5 to 3.5 points. The mean still sits
  above the median, so the median gap is real, but larger in 2025.
- **No position passes on its own** (ECE 0.041 to 0.055), and every
  projection tercile fails, so the pooled hide is not one bad slice. These
  rows are information only and change nothing.
- **Small counts:** the lowest bins (predicted 0.05 and 0.17) go over 28% and
  25% of the time, the ratio-scaling failure 27g's receptions and 20g1's blocks
  showed.
- **What it means for 39c and 39d:** frozen Rec Targets rows carry a
  projection and no P(over), so 39d's ranking check would find no picks under
  27i's rule. A different method (count-aware, or a fit spanning more seasons)
  is a new item, developed on 2024 first; 2025 has now been read once for
  this projection.

**Coverage note:** the 2024 fit used 3,244 cases, not 39a's 3,355: 111
player-games project exactly 0 targets and cannot form a ratio. 2025 adds 139
no-baseline, 431 thin and 179 zero-projection exclusions from 5,373 rows.

**Checks:** 26 targets P(over) tests and the full Verify command pass (612 web
tests and build, 2,770 API tests). No production module imports the new
modules; `NflPropMarket`, `nfl-targets-v1`, v4 and `nfl-pover-v1` are
unchanged from `master`. The local interview guide was updated (fit and check
only; serving and grading still planned) and is not staged.

Output:

```text
NFL Rec Targets over probability fit: fitted on 2024, scored on the 2025 holdout
Projection nfl-targets-v1, P(over) nfl-targets-pover-v1; 2025 holdout read 8 (no projection verdict)

Show Rec Targets only with >= 300 cases, ECE <= 0.02, no bin of 200+ pairs off by more than 0.05, and Brier no worse than a normal on the same pairs, positions pooled (pre-registered 2026-10-18).

Coverage (driver rows, then what was dropped)
  season     rows  no actual  invalid  no base   thin  zero proj  cases
  2024       5200          0        0      511   1334        111   3244
  2025       5373          0        0      139    431        179   4624

Verdict (positions pooled)
  group                     cases   pairs     ECE   worst   Brier  normal  verdict   failed on
  receiving_targets          4624   16822   0.043   0.078  0.2022  0.2033  hide      ECE, worst gap

Information only; the verdict pools positions
  group                     cases   pairs     ECE   worst   Brier  normal  verdict   failed on
  RB                         1312    3906   0.041   0.070  0.2097  0.2150
  WR                         2172    8723   0.045   0.091  0.2012  0.2011
  TE                         1140    4193   0.055   0.105  0.1971  0.1971
  projection <= 1.86         1554    3094   0.063   0.131  0.2174  0.2209
  projection 1.86-4.13       1530    6028   0.035   0.062  0.2107  0.2117
  projection > 4.13          1540    7700   0.062   0.101  0.1894  0.1897

At the line nearest the projection (1.0 multiple): the median gap as a probability
  group                         n  predicted  observed  normal
  all positions              4624      0.434     0.406   0.488
  RB                         1312      0.408     0.383   0.486
  WR                         2172      0.431     0.404   0.489
  TE                         1140      0.471     0.436   0.486

Reliability, all positions
     bin n  predicted  observed
       118      0.053     0.280
       750      0.167     0.245
      3765      0.248     0.188
      2377      0.346     0.285
      2560      0.444     0.396
      1656      0.552     0.533
      2653      0.649     0.625
      1893      0.757     0.764
       970      0.833     0.797
        80      0.906     0.912

Wrote C:\Users\daysh\OneDrive\Desktop\SportAppV2\api\app\core\nfl_targets_over_probability_fit.py (SHOWN = False).
Elapsed seconds: 17.08
```
