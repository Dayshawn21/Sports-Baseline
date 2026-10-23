# Feature: NBA over probability, second method - method and 2024-25 selection

**From build-plan:** feature 44a (parent 44, added 2026-10-23, option A)
**Status:** complete (owner approved via `/complete` on 2026-10-23); verified locally; backtest only, nothing served changed; 44b confirmation pending

## Goal

Build a sport-neutral P(over / under / push) method with two candidate
distribution families. Pre-register how a family is chosen per market and how
44b will confirm it. Then choose each market's family on 2024-25 alone, and
freeze that choice before any 2026-27 confirmation row exists. This is a
backtest only: nothing served changes.

Why: 20g1's ratio quantiles hid eight of nine NBA markets, for two different
reasons (small-count miscalibration, and large sums losing to a plain normal on
Brier), and they return no probability for whole-number lines.

## In scope

- **Shared distributions** in a new `app/core/count_over_probability.py`, pure,
  with no sport import:
  - **Negative binomial (`negbin`):** mean = projection, one dispersion `r`
    per market. Discrete, so P(over), P(under) and P(push) are exact for any
    line. Poisson is its large-`r` limit.
  - **Projection-scaled normal (`scaled_normal`):** variance `a + b *
    projection` per market (clamped to a positive floor), read with a
    continuity correction on integer outcomes, so it also yields P(push).
    This deliberately differs from the display rule's constant-sigma normal
    baseline. A constant-sigma candidate would tie that Brier gate by
    construction.
  - Fitters for each family's parameters from (projection, actual) pairs.
- **Pre-registration** (`app/core/nba_over_probability_v2.py`), committed
  as a checkpoint **before** any 2024-25 fit is run. Its commit hash is
  recorded in this spec. It holds:
  - `NBA_OVER_PROBABILITY_V2_VERSION = "nba-pover-v2"`
  - `TARGET_MARKETS`: the eight 20g1-hidden markets (`points`, `rebounds`,
    `threes_made`, `blocks`, `points_rebounds_assists`, `points_rebounds`,
    `points_assists`, `rebounds_assists`)
  - `CANDIDATE_ORDER = ("negbin", "scaled_normal")`
  - **The selection rule:** cross-fit 2024-25 by ISO-week parity (fit on even
    weeks and score odd, then the reverse, and pool both). Score at 20g1's
    synthetic x.5 lines under the display rule. A family is eligible only if
    it passes the rule on that cross-fit. The pick is the eligible family
    with the lower cross-fit Brier; an exact tie goes to the earlier family in
    `CANDIDATE_ORDER`. No eligible family means the market is
    `not_carried` and never reaches 44b.
  - **The confirmation rule for 44b:** the same display rule. Its constants
    are imported from `nba_over_probability`, unchanged, and a test pins
    them. The sample is 2026-27 (season 2026) `REG` weeks 1-4, scored only
    once every game in those weeks is final and has box scores loaded;
    earlier runs stop as `accruing`. It uses 20f eligibility and the
    reference projection, with the family and parameters frozen by this
    feature, fitted on all of 2024-25.
- **A dev CLI** `python -m app.backtest.nba_over_probability_v2_dev [--write]`:
  - It loads only seasons 2023 and 2024. It rejects any other season, and
    does so before importing the database module.
  - It prints each candidate's cross-fit table per market: cases, pairs,
    ECE, worst gap, Brier, normal Brier, verdict and failed checks. Then the
    selection, and descriptive whole-number-line context: P(push) predicted
    against observed at integer synthetic lines. That context is not part of
    the verdict.
  - `--write` freezes the selection into a generated module.
- **A generated selection module** `app/core/nba_over_probability_v2_fit.py`:
  - `FIT_SEASON = 2024`, `CONFIRMATION_SEASON = 2026`,
    `CONFIRMATION_WEEKS = (1, 2, 3, 4)`
  - `FIT_PROJECTION_MODEL_VERSION = "nba-reference-v1"`
  - per selected market: the family and parameters fitted on all of 2024-25
  - the `not_carried` markets
  - It is added to `GENERATED_FITS` in `.agents/hooks/protect-files.mjs` so
    it is never hand-edited.

## Out of scope

- **Reading 2025-26 or 2026-27 outcomes.** 44b runs the one confirmation.
- Any serving, freezing, ranking-check, page or `SPORT_STATUS` change (44c).
- **Assists:** they stay on `nba-pover-v1`. Whether whole-number assists
  lines get v2 is a 44c decision.
- Changing the projection, eligibility, display rule constants or synthetic
  lines.
- NHL, NFL or other sports. The core module is reusable, but each sport needs
  its own fit and check.
- New dependencies. The math uses the standard library (`math.lgamma`,
  `erf`); numpy only where already convenient.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.
   **Exception:** the step 2 checkpoint is required. It is the
   pre-registration timestamp.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Shared distributions** - `count_over_probability.py`: an
  `OverUnderPush` result (three probabilities summing to 1), `negbin` and
  `scaled_normal` readers taking `(params, projection, line)`, and fitters
  (`r` by method of moments with a positive floor and a Poisson fallback when
  the variance is at or below the mean; `a`, `b` by least squares of squared
  residuals on projection, floored). *Done when:* tests pass for both
  families:
  - hand-computed values (NB pmf and Poisson limit at small means)
  - x.5 lines give zero push; integer lines give the exact pmf mass
  - monotone in the line, and the three outputs sum to 1
  - a projection <= 0 returns None
  - fitters recover known parameters from synthetic draws within tolerance
  - a test fails if the module imports any `nba`/`nfl` module
- [x] **Step 2 - Pre-registration** - `nba_over_probability_v2.py` with the
  constants and rules above, plus the pure cross-fit splitter (ISO-week
  parity) and the selection function (eligibility, Brier, tie-break,
  `not_carried`). *Done when:*
  - tests pin the target markets, candidate order and confirmation weeks,
    and pin the display constants to 20g1's
  - selection tests cover the edge cases: both pass, one passes, neither
    passes, exact tie, under 300 cases
  - Verify passes, and a **checkpoint commit** exists, with its hash
    recorded here, before step 4 runs anything against the database
- [x] **Step 3 - Cross-fit scoring** - pure functions that fit each family
  on one parity, score the other at synthetic x.5 lines (reusing
  `synthetic_lines`, `calibrate`, `normal_over_probability` and
  `nba_display_verdict`), pool both halves, and report per market. The
  normal baseline's sigma comes from the same fitting half. *Done when:* tests
  on synthetic NB and normal data show the right family selected and a
  miscalibrated family hidden, and no case is ever scored by a fit that
  includes it.
- [x] **Step 4 - Dev CLI and run** - `nba_over_probability_v2_dev.py` with
  the report, the whole-number-line context and the season guard. *Done
  when:*
  - a CLI test proves any non-2024 season argument (or a 2025/2026 load) is
    rejected before the database import
  - a report-format test exists
  - one real run on 2024-25 is recorded below (the table and the selection),
    with zero 2025-26 or 2026-27 rows loaded (asserted by the seasons
    passed to `get_projection_history`)
- [x] **Step 5 - Freeze the selection** - `--write` renders the generated
  module, and the hook protects it. *Done when:*
  - the generated module exists and matches the step 4 run
  - a test re-renders from fixed inputs and pins the format
  - a test fails if `FIT_PROJECTION_MODEL_VERSION` differs from
    `NBA_PROJECTION_MODEL_VERSION`
  - Verify passes

## Files / areas

- New: `api/app/core/count_over_probability.py`,
  `api/app/core/nba_over_probability_v2.py`,
  `api/app/core/nba_over_probability_v2_crossfit.py` (step 3's scoring, kept
  out of the committed pre-registration module so that file stays frozen),
  `api/app/core/nba_over_probability_v2_fit.py` (generated),
  `api/app/backtest/nba_over_probability_v2_dev.py`
- New tests: `api/tests/test_count_over_probability.py`,
  `test_nba_over_probability_v2.py`, `test_nba_over_probability_v2_dev.py`
- Changed: `.agents/hooks/protect-files.mjs` (one entry in `GENERATED_FITS`)
- Read only: `nba_over_probability.py`, `nfl_over_probability_calibration.py`,
  `nba_projection_backtest.py`, `repositories/nba.py`
  (`get_projection_history`)

## Data / contracts

- **No schema, API or UI change.**
- **Load-bearing for 44b/44c and later sports:**
  - `OverUnderPush(p_over, p_under, p_push)`, and the reader signature
    `(params, projection, line) -> OverUnderPush | None`
  - the generated module's names
  - `nba-pover-v2` as the version 44c serves and freezes
  - 44b must read the family and parameters from the generated module,
    never refit
- **Load-bearing (pre-registration):** after the step 2 checkpoint, any change
  to the target markets, the candidate order, the selection rule or the
  confirmation rule needs a new version and a recorded reason. It must never be
  edited quietly.

## Testing

- Pure logic (steps 1-3) gets unit tests with fixed seeds and no database.
- The CLI season guard and report format get tests. The real database run is
  evidence recorded here, not a test.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- `core/` stays pure. The new core modules import nothing from `nba`/`nfl`
  except the NBA v2 module's imports of 20g1/20f constants and calibration
  helpers.
- **Holdout discipline:** 2025-26 has been read twice (20f, 20g1). This feature
  reads it zero times. Never pass 2025 or 2026 to `get_projection_history`
  here. Selection uses 2024-25 alone; 2023-24 is only early-window input.
- Run the database step with the Windows selector event loop (as the existing
  CLIs do) from `api/` with the venv Python.
- Case counts: 2025-26 held 17,346 eligible cases per market under 20f, and
  2024-25 should be similar (each cross-fit half about half that). The step
  4 run states the real counts. Blocks and threes have fewer synthetic pairs.
- ISO-week parity puts adjacent weeks in opposite halves (week 53 and week 1
  can share a parity). That only shifts a few days between halves and causes
  no leakage, because each case is still scored by a fit that excludes it.
- Match the existing modules' comment density. Keep the "why" comments that
  explain the pre-registration and the baseline-tie trap; skip narration.
- No em dashes in new text.
- **Interview guide:** update it at `/complete` only if the run produces a
  notable finding. It is untracked; never stage it.

## Results

- **Pre-registration commit:** `ebd4aea953fb897294859d91025616b8d56276d5`
  (2026-10-23 10:13 -0500), on `feature/44a-nba-pover-method`, before any
  2024-25 fit was run. It fixes the target markets, `CANDIDATE_ORDER`, the
  selection rule and the 2026-27 confirmation rule in
  `api/app/core/nba_over_probability_v2.py`.

- **2024-25 cross-fit run (step 4, 2026-10-23):**
  `python -m app.backtest.nba_over_probability_v2_dev`, with seasons 2023 and
  2024 loaded, reading 0 rows of 2025-26 and 0 of 2026-27. It took 50 s.
  2024-25 held 17,010 eligible cases per market (threes 15,981, blocks
  16,753).

| Market | negbin ECE / worst / Brier | scaled_normal ECE / worst / Brier | Normal Brier | Selected |
|---|---|---|---|---|
| points | 0.024 / 0.103 / 0.1888 hide | 0.014 / 0.029 / 0.1870 show | 0.1875 | scaled_normal |
| rebounds | 0.004 / 0.034 / 0.1896 show | 0.023 / 0.046 / 0.1902 hide | 0.1917 | negbin |
| threes_made | 0.005 / **0.052** / 0.2057 hide | 0.046 / 0.072 / 0.2077 hide | 0.2090 | not carried |
| blocks | 0.024 / 0.079 / 0.1997 hide | 0.093 / 0.128 / 0.2080 hide | 0.2157 | not carried |
| pts + reb + ast | 0.026 / 0.084 / 0.1665 hide | 0.011 / 0.022 / 0.1643 show | 0.1646 | scaled_normal |
| pts + reb | 0.026 / 0.065 / 0.1738 hide | 0.010 / 0.025 / 0.1719 show | 0.1723 | scaled_normal |
| pts + ast | 0.027 / 0.126 / 0.1787 hide | 0.010 / 0.025 / 0.1765 show | 0.1769 | scaled_normal |
| reb + ast | 0.011 / 0.056 / 0.1769 hide | 0.016 / 0.033 / 0.1769 show | 0.1780 | scaled_normal |

- **Reading it (development evidence, not confirmation):**
  - The large-sum markets pick `scaled_normal`, and rebounds picks `negbin`.
  - Threes missed only on the worst bin (0.052 against 0.05). The rule is
    applied as registered, with no tuning.
  - Blocks still fails in both families.
  - The `scaled_normal` Brier margins over the constant-sigma normal are
    small (0.0003 to 0.0011), so 44b's Brier gate could fail on noise for
    those markets.
  - Whole-number push rates are close for the selected families (for
    example, points 0.048 predicted against 0.049 observed, rebounds 0.135
    against 0.130). This is information only.
- **Frozen fit (step 5):**
  - `--write` re-ran the same replay. Its report matched the step 4 run
    exactly, and it wrote `api/app/core/nba_over_probability_v2_fit.py`.
  - Parameters fitted on all of 2024-25:
    - points: `scaled_normal` a 14.188, b 2.257
    - rebounds: `negbin` r 15.399
    - pts + reb + ast: `scaled_normal` a 35.549, b 1.696
    - pts + reb: `scaled_normal` a 26.251, b 1.899
    - pts + ast: `scaled_normal` a 20.829, b 1.957
    - reb + ast: `scaled_normal` a 1.343, b 1.464
    - threes_made and blocks: not carried
  - The hook refuses an `Edit` of the module (exit 2).
