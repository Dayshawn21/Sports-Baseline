# Feature: Market-anchored ensemble

**From build-plan:** feature 26d (parent: 26. Tennis model validation)
**Status:** complete (2026-10-01; holdout and live gate scored once, adopted for ATP+WTA and CHALLENGER, served as `ensemble-v3`)
**Branch:** `feature/tennis-market-anchored-ensemble`

## Goal

Replace the hand-set tennis ensemble weights with a log-odds blend fitted on the
market, and adopt it only if it passes a rule fixed before the holdout is
scored.

26c rejected the live hand-set blend against the Pinnacle close (+0.0060 +/-
0.0008 log loss, 12,068 ATP+WTA holdout matches, 7.5 SE). Per 26c's rule
table, that justifies a market-anchored fit, scored on the same 2023-2025
holdout under its own pre-registered rule. This feature fits it, scores it once
on the holdout, checks that it carries over to the app's live inputs (26a), and
ships it to the predictor only if both gates pass.

**Likely outcome, stated up front:** computed ELO trails the close by +0.0636
and the close moves toward it only +0.46 points on average, so the fitted ELO
coefficient will probably be small. An adopted blend would sit close to the
market. **That shrinks moneyline edges, so best picks will surface fewer
moneyline plays.** That is the honest result of 26a and 26c, not a defect.

## Decisions this spec makes (confirm in review)

| # | Decision | Why |
|---|---|---|
| D1 | **The fitted blend has two inputs, the market and ELO. v6 LightGBM gets no weight.** It is still computed, stored in `p1_ml_prob`, shown on the match page and graded forward by 26a. | v6 cannot be scored historically (its training covers all stored history, 26c). Its live sample is about 440 settled ATP+WTA matches, too few to fit a weight, and 26a graded it the weakest component (+0.0207 +/- 0.0119 against the market). Keeping its hand-set 0.40/0.45 weight would mean "replacing hand-set weights" with mostly hand-set weights. **If you would rather keep v6 at a hand-set weight, say so: the fit then covers only the ELO-market split, and the rule changes.** |
| D2 | **Form:** `logit(p) = a * logit(market) + b * logit(elo)`, with no intercept. | p1 is the lower player id, so orientation carries no information. With no intercept the blend is symmetric: swapping players gives `1 - p`. `a = 1, b = 0` is exactly the market. |
| D3 | **The market input is the de-vigged Pinnacle close.** | This matches 26c's verdict baseline, and 26c's timing check showed the close sits nearest the app's own pre-start price (1.57 points mean gap, against 2.61 for the open). It is conservative: fitted against the close, ELO earns only the weight the close did not already absorb. |
| D4 | **Three fit groups:** ATP and WTA (main-tour scored categories, as in 26c), and CHALLENGER (Valuebetennis `Challenger`, both genres pooled). Each group's blend is adopted or rejected by its own verdict. | The live predictor blends under `ATP`, `WTA`, or the fallback for everything else (Challenger and WTA 125). |
| D5 | **Fit only on cases where ELO is reliable** (not gated by `elo_is_unreliable`). When served, a gated or missing ELO gives the market alone. | The same gates the app serves, as in 26c. Fitting through gated cases would blur `b`. |
| D6 | **Coefficients are frozen from the 2022 development fit** and never refit on holdout seasons, even after adoption. | Serving coefficients that saw the holdout would make the verdict meaningless. |
| D7 | **Live inputs stay TennisAbstract ELO.** The coefficient fitted on computed ELO is applied to the live TennisAbstract ELO, and the 26a live gate (L1) exists to catch that transfer failing. | Switching the live ELO source is a bigger change than this item. |

## Pre-registered rule

Fixed when this spec is approved, **before the 2022 fit is run**. Do not edit
it after the holdout run: a changed rule invalidates the verdict.

**What has been seen when it is fixed:** 26c's development and holdout reports
(aggregate log loss, calibration, ROI and CLV per tour, archived in
`blueprint/history/features/26c-historical-closing-line-backtest.md`). No
per-match holdout data and no fitted coefficient.

**This is the second read of the 2023-2025 holdout** (26c was the first).

- **Seasons:** fit on development 2022; score the holdout 2023-2025 once.
  Eligibility, exclusions and ELO replay are 26c's, unchanged (`exclusion()`,
  `build_cases()`).
- **Metric:** paired per-match log-loss difference with its standard error
  (`paired_loss_difference`).
- **Per group (ATP+WTA together; CHALLENGER separately), adopt only if all
  three pass:**

  | Gate | Data | Comparison | Passes when |
  |---|---|---|---|
  | **H1, beats the hand-set blend** | holdout | fitted minus 26c's `blend_prob` | `d + 2*se < 0` |
  | **H2, no worse than the close** | holdout | fitted minus the close | `d - 2*se <= 0` |
  | **L1, carries to live inputs** | 26a settled live rows: TennisAbstract ELO, the market price at prediction, generated before start, any `ensemble-v*` version, one row per match (the latest pre-start) | fitted minus that market | `d - 2*se <= 0` |

- ATP and WTA share one verdict (pooled, as 26c's), even though each has its
  own coefficients.
- **A reject is final** for these coefficients. The ensemble then stays
  hand-set (`ensemble-v2`), and 26d closes as not adopted.
- **Context only, never decisive:** per-tour splits, calibration bins, the
  fitted minus stored live ensemble on L1's rows, and flat-stake ROI at
  3 points of disagreement.

## In scope

- A pure apply function and a generated, frozen coefficient file in `app/core/`.
- A fit CLI that fits the 2022 coefficients and writes that file.
- A scoring CLI for the holdout (H1, H2) and the live gate (L1).
- **Only if adopted:** the predictor serves the fitted blend as `ensemble-v3`,
  the grader and `/tennis/model` default to it, and the match page labels the
  coefficients honestly.

## Out of scope

- Any weight for v6 (D1), and retraining v6.
- Changing ELO constants, 26c's eligibility filter, its seasons or its report.
- Fitting on the open price, or on any holdout season.
- Best-pick thresholds, Kelly, confidence tiers and props: they read
  `p1_win_prob` unchanged.
- Switching live ELO to computed ELO (D7).
- The bankroll builder's return (open question 14).
- A schema change. `ensemble_weights` is JSONB and already holds a dict.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at
   the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Pure apply function.** Add `app/core/tennis_market_blend.py`:
  - `BlendCoefficients(market: float, elo: float)` (frozen dataclass)
  - `market_anchored_prob(coefs, market_prob, elo_prob) -> float`: D2's
    formula. `elo_prob` None means the market alone. Inputs are clipped to
    `[1e-6, 1 - 1e-6]` before the logit, and the output to `[0.01, 0.99]` as
    `blend()` does.

  *Done when:* unit tests show that `a = 1, b = 0` returns the market; swapping
  the players gives `1 - p`; a missing ELO returns the market; a hand-worked
  case matches to 1e-9; and extreme inputs stay finite and inside the clamp.

- [x] **Step 2 - Reliability on the case.** Add `elo_reliable: bool` to 26c's
  `ClosingLineCase`, set in `build_cases` from the same `elo_is_unreliable`
  call that already gates the blend (False when ELO or the close is missing).
  Additive only: 26c's report output does not change.

  *Done when:* a test shows `elo_reliable` is False for a player under 10
  prior matches and for a 15-point ELO-market gap, and True otherwise. 26c's
  existing tests pass unchanged.

- [x] **Step 3 - Fit and frozen file.** Add
  `app/backtest/tennis_market_blend_fit.py`:
  - `fit_group(cases) -> FitResult`: unpenalized, intercept-free logistic
    regression (Newton's method in numpy, see Results) on
    `[logit(close), logit(elo)]`, over
    2022 eligible cases with `elo_reliable`, plus standard errors from the
    observed information matrix
  - prints, per group, n, `a` and `b` with standard errors, and in-sample
    paired differences against the close and the hand-set blend (development
    only, labeled in-sample)
  - `--write` renders `app/core/tennis_market_blend_fit.py` (generated, with a
    do-not-edit header, as `nfl_over_probability_fit.py` is), holding
    `FIT_SEASONS`, `FIT_COEFFICIENTS: dict[str, BlendCoefficients]` keyed
    `ATP` / `WTA` / `CHALLENGER`, and the group sizes
  - never reads holdout-season cases. They are filtered out before fitting.

  *Done when:*
  - a test fits synthetic cases generated from known `a, b` and recovers them
    within 3 SE
  - a test checks that holdout-season cases never reach the fit
  - a test round-trips `render_module` through `exec`
  - the live development run is pasted under Results, and the generated file
    is written

- [x] **Step 4 - Holdout scorer (H1, H2).** Add
  `app/backtest/tennis_market_blend.py` with the pre-registered constants at
  the top, a pure `verdict_h1` and `verdict_h2`, and a `report(cases,
  holdout: bool)`. It reuses `load_valuebetennis`, `build_cases` and
  `exclusion`. Without `--holdout` it scores 2022 only (in-sample, labeled
  so). It prints per-group n, log loss and Brier for the fitted blend, the
  hand-set blend and the close; the two paired differences; calibration bins;
  and the ROI context.

  *Done when:*
  - tests check both verdict functions at exactly 2 SE and on either side
  - a test checks that the default run prints no holdout-season numbers
  - a test on synthetic cases checks the headers and that gated cases score as
    the market
  - the development run is pasted under Results

- [x] **Step 5 - Live gate (L1).** In the same module, add `--live`: load 26a's
  graded rows with the existing `tennis_predictions` loader (any `ensemble-v*`
  version, latest pre-start row per match), apply the frozen coefficients to
  `elo_prob` and the recomputed `market_prob` with the live gate
  (`elo_is_unreliable`), and print L1 per group, plus the stored ensemble as
  context.

  *Done when:*
  - a test on synthetic `GradedPrediction` rows checks the version filter, the
    one-row-per-match rule and `verdict_l1` at 2 SE
  - a read-only live run prints row counts per group, and they are recorded in
    Notes (expected about 440 ATP+WTA; **not a verdict yet**: L1 runs with
    the holdout in Step 6)

- [x] **Step 6 - Verdict run, once.** With the code as reviewed and a clean
  `api/app` tree, run `--holdout` once and `--live` once.

  *Done when:*
  - both outputs are pasted under Results with the date and commit
  - a verdict table states H1, H2 and L1 per group, and the adoption result
  - **if no group is adopted, stop here.** Steps 7 and 8 are skipped (marked
    so), and 26d goes to `/complete` as "not adopted"

- [x] **Step 7 - Serve it (only if a group is adopted).**
  - `blend()` uses `market_anchored_prob` with `FIT_COEFFICIENTS[group]` when
    the tour group is adopted and a market price exists. ELO missing or gated
    gives the market alone. v6 gets no weight (D1). The stale and overround
    flags are still raised but no longer change the probability.
  - No market: the hand-set path, unchanged.
  - A non-adopted group keeps the hand-set path.
  - `ensemble_weights` stores the coefficients actually applied (`{"market":
    a, "elo": b}`, or `{"market": 1.0}` when ELO is dropped).
  - The model version becomes `ensemble-v3+lgbm-<v>`, and
    `tennis_predictions.DEFAULT_MODEL_VERSION` (and therefore `/tennis/model`)
    follows it. This also ends today's drift, where live rows are
    `ensemble-v2` but the grader defaults to `ensemble-v1`.

  *Done when:*
  - ensemble tests cover an adopted group with a reliable ELO (equal to
    `market_anchored_prob`), gated ELO (equal to the market), no market (the
    hand-set result, unchanged), and a non-adopted group (unchanged)
  - a test pins the version string
  - a one-off `predict_today` run shows `ensemble-v3` rows whose ensemble sits
    within a few points of the market

- [x] **Step 8 - Honest label on the match page (only if adopted).** The
  component table's weight column reads "coef" for `ensemble-v3` predictions
  (log-odds coefficients are not shares and do not sum to 1), and "weight"
  otherwise. This is a pure helper in `web/src/utils/tennisMatch.ts`.

  *Done when:* a Vitest test covers both labels, `npm run build` passes, and a
  screenshot of a v3 match page shows the coefficients under "coef".

## Files / areas

- `api/app/core/tennis_market_blend.py` (new) - `BlendCoefficients`, `market_anchored_prob`.
- `api/app/core/tennis_market_blend_fit.py` (new, generated) - frozen 2022 coefficients.
- `api/app/backtest/tennis_closing_lines.py` - `elo_reliable` on `ClosingLineCase` (additive).
- `api/app/backtest/tennis_market_blend_fit.py` (new) - the fit CLI.
- `api/app/backtest/tennis_market_blend.py` (new) - H1/H2/L1 scorer and the rule constants.
- Only if adopted: `api/app/services/tennis/ensemble.py`, `api/app/ingest/predictions.py`, `api/app/backtest/tennis_predictions.py`, `web/src/utils/tennisMatch.ts` and the component that reads the label.
- Tests: `api/tests/test_tennis_market_blend.py`, `test_tennis_market_blend_fit.py`, additions to `test_tennis_closing_lines.py` and `test_ensemble*.py`, and `web/src/utils/tennisMatch.test.ts`.

## Data / contracts

No schema change.

```python
@dataclass(frozen=True)
class BlendCoefficients:
    market: float   # a, on logit(de-vigged market)
    elo: float      # b, on logit(elo); 0 means market only
```

**Load-bearing:**
- `FIT_COEFFICIENTS` keyed `ATP` / `WTA` / `CHALLENGER` in the generated
  `tennis_market_blend_fit.py`. Item 17 and any later tennis refit read it.
  Regenerating it is a new model version.
- `ensemble-v3` rows store coefficients, not shares, in `ensemble_weights`.
  Readers must branch on `model_version` (Step 8 does).
- `ClosingLineCase.elo_reliable`. Later backtests that fit on 26c's cases use
  it.
- **`hand_set_blend` (Step 7) is ensemble-v2, frozen.** `blend()` serves the
  fitted blend when a market price exists and calls `hand_set_blend` otherwise.
  26c's `build_cases` calls `hand_set_blend` directly, so 26c's archived numbers
  and 26d's H1 baseline stay reproducible (26c's development report was re-run
  after Step 7 and matched its archive). Never retune `hand_set_blend` in place.

**Step 7 live check (2026-10-01, read-only `predict_today`, not persisted):**
74 predictions for today and tomorrow, all `ensemble-v3+lgbm-v6`. 59 have a
market price: 43 take the fitted blend and 16 the market alone (ELO missing or
gated). The ensemble sits a median 1.0 point from the market (max 5.4). The
15 with no market take the hand-set path, as before.

## Testing

- The test gate is on. Steps 1 to 5 and 7 to 8 ship tests; Step 6 is a
  recorded run.
- Run with `cd api && .venv\Scripts\python.exe -m pytest` and
  `cd web && npm run test && npm run build`.
- Tests use synthetic cases, never the Valuebetennis downloads or the live
  database.
- Evidence beyond the tests: the development fit, the development scorer
  report, the live row counts, and the one holdout and live verdict run, all
  under Results.

## Notes

- **Live sample on 2026-10-01** (settled, pre-start prediction with both
  TennisAbstract ELO and a market price): ATP 146 + WTA 167 under
  `ensemble-v1+lgbm-v6`, 38 + 38 under v5, and 28 + 25 under v2. That is about
  440 ATP+WTA matches before de-duplication. CHALLENGER is about 430. L1 is a
  low-power safety check, not proof of transfer.
- **L1 row counts (2026-10-01, Step 5; counted, not scored):** 1,480 graded
  rows load; 836 are L1-eligible (completed score, TennisAbstract ELO and a
  market price at prediction, latest pre-start row per match).

  | Verdict group | Tours | Rows |
  |---|---|---|
  | ATP+WTA | ATP 208, WTA 230 | 438 |
  | CHALLENGER | CHALLENGER | 398 |

  By version: `ensemble-v1+lgbm-v6` 605, `v1+lgbm-v5` 79, `v1+lgbm-none` 48,
  `v2+lgbm-none` 49, `v2+lgbm-v6` 55.
- **L1's gate is the 15-point gap only.** 26a's graded rows carry no
  prior-match counts, so the live gate's under-10-matches rule cannot be
  replayed on them. On main-tour players it rarely applies, but L1 may serve
  ELO in a few cases the app would gate.
- **Pre-existing drift:** `app/ingest/predictions.py` writes `ensemble-v2+lgbm-*`
  since `ca2a658` (2026-09-28), while `DEFAULT_MODEL_VERSION` and the
  `/tennis/model` page still grade `ensemble-v1+lgbm-v6`. Step 7 fixes it only
  if 26d is adopted. Otherwise record it for a `/fix`.

## Results

### Development fit (2026-10-01, Step 3)

`python -m app.backtest.tennis_market_blend_fit --write`, 2022 only. Wrote
`app/core/tennis_market_blend_fit.py`.

```
Coefficients (+/- one standard error)
  ATP        n=1107   a (market) 1.1392 +/- 0.1803   b (elo) -0.0782 +/- 0.1748
  WTA        n=881    a (market) 1.4605 +/- 0.2059   b (elo) -0.4226 +/- 0.1985
  CHALLENGER n=5734   a (market) 1.1105 +/- 0.0787   b (elo) +0.0833 +/- 0.0794

In-sample paired log-loss difference (development only, NOT a verdict; gated cases served as the market)
  ATP        n=1706   vs close -0.0003 +/- 0.0005   vs hand-set blend -0.0051 +/- 0.0023
  WTA        n=1561   vs close -0.0017 +/- 0.0014   vs hand-set blend -0.0120 +/- 0.0037
  CHALLENGER n=10452  vs close -0.0011 +/- 0.0004   vs hand-set blend -0.0056 +/- 0.0010
```

**Reading (in-sample, not a verdict):**
- **No group gives ELO a meaningful positive weight.** ATP's `b` is zero
  within error. WTA's is **negative** (-0.42, 2.1 SE), and Challenger's is
  +0.08 (1 SE).
- **`a + b` is about 1.04-1.19 in every group,** so the fit mostly extremizes
  the close slightly. In the reliable-ELO cases (gap under 15 points) ELO and
  the close move together, so `a` and `b` trade off, hence the wide standard
  errors.
- **A negative `b` means "lean away from ELO."** The rule allows it. It was
  not anticipated in the spec, and is recorded here before the holdout run.

**Decided 2026-10-01, before the holdout:** the user kept the approved form,
negative `b` allowed, rather than constraining `b >= 0` after seeing the
in-sample fit.

### Development scorer (2026-10-01, Step 4)

`python -m app.backtest.tennis_market_blend`, 2022 only (in-sample).

```
Log loss and Brier (lower is better; same matches in every column)
  group            n             fitted     hand-set blend              close
  ATP           1706    0.5787   0.1986    0.5838   0.2004    0.5790   0.1986
  WTA           1561    0.5824   0.2005    0.5944   0.2051    0.5841   0.2010
  ATP+WTA       3267    0.5805   0.1995    0.5889   0.2026    0.5814   0.1998
  CHALLENGER   10452    0.5798   0.1987    0.5853   0.2008    0.5809   0.1990

Paired log-loss difference (negative = the fitted blend is better; +/- one standard error)
  ATP        n=1706   vs hand-set blend -0.0051 +/- 0.0023   vs close -0.0003 +/- 0.0005
  WTA        n=1561   vs hand-set blend -0.0120 +/- 0.0037   vs close -0.0017 +/- 0.0014
  ATP+WTA    n=3267   vs hand-set blend -0.0084 +/- 0.0022   vs close -0.0010 +/- 0.0007
  CHALLENGER n=10452  vs hand-set blend -0.0056 +/- 0.0010   vs close -0.0011 +/- 0.0004

Flat-stake ROI at the close (fitted - close >= 3 pts, either side; never decisive)
  ATP        picks 0
  WTA        picks   414  won   257  units    +17.35  ROI +4.2%
  ATP+WTA    picks   414  won   257  units    +17.35  ROI +4.2%
  CHALLENGER picks  1998  won  1597  units     -5.48  ROI -0.3%
```

**Reading:** these are in-sample, so they describe the fit, not its value.
ATP's blend never differs from the close by 3 points, so it makes no picks.
WTA's +4.2% on 414 picks is the in-sample face of its negative ELO weight and
says nothing until the holdout.

### Verdict run (2026-10-01, Step 6, the one scored run)

Run once each, with the code at commit `ea71fe9` (clean `api/app` and
`api/tests` trees).

**Holdout:** `python -m app.backtest.tennis_market_blend --holdout`

```
Tennis market-anchored blend (26d) - HOLDOUT seasons 2023, 2024, 2025
  Data: Valuebetennis open data (valuebetennis.com), CC BY 4.0. Pinnacle closing odds.
  Coefficients fitted on [2022]; gated or missing ELO is served as the close.
  HOLDOUT: scored once, the second read of 2023-2025 (26c was the first).

Frozen coefficients (logit(p) = a * logit(close) + b * logit(elo))
  ATP        a 1.1392   b -0.0782
  CHALLENGER a 1.1105   b +0.0833
  WTA        a 1.4605   b -0.4226

Log loss and Brier (lower is better; same matches in every column)
  group            n             fitted     hand-set blend              close
  ATP           6215    0.5863   0.2018    0.5902   0.2033    0.5864   0.2018
  WTA           5853    0.5856   0.2013    0.5934   0.2045    0.5852   0.2012
  ATP+WTA      12068    0.5860   0.2016    0.5918   0.2039    0.5858   0.2015
  CHALLENGER   34259    0.6077   0.2103    0.6140   0.2128    0.6082   0.2104

Paired log-loss difference (negative = the fitted blend is better; +/- one standard error)
  ATP        n=6215   vs hand-set blend -0.0039 +/- 0.0013   vs close -0.0001 +/- 0.0003
  WTA        n=5853   vs hand-set blend -0.0078 +/- 0.0022   vs close +0.0004 +/- 0.0008
  ATP+WTA    n=12068  vs hand-set blend -0.0058 +/- 0.0012   vs close +0.0002 +/- 0.0004
  CHALLENGER n=34259  vs hand-set blend -0.0063 +/- 0.0006   vs close -0.0006 +/- 0.0003

Calibration, ATP+WTA (bin: mean predicted / actual p1 win rate)
  fitted  0.0-0.1: 0.06/0.04 (n=404)  0.1-0.2: 0.15/0.15 (n=798)  0.2-0.3: 0.25/0.26 (n=1296)  0.3-0.4: 0.35/0.35 (n=1774)  0.4-0.5: 0.45/0.44 (n=1768)  0.5-0.6: 0.55/0.53 (n=1794)  0.6-0.7: 0.65/0.65 (n=1769)  0.7-0.8: 0.75/0.74 (n=1335)  0.8-0.9: 0.85/0.85 (n=804)  0.9-1.0: 0.93/0.94 (n=326)
  close   0.0-0.1: 0.07/0.04 (n=329)  0.1-0.2: 0.16/0.14 (n=752)  0.2-0.3: 0.25/0.25 (n=1283)  0.3-0.4: 0.35/0.35 (n=1785)  0.4-0.5: 0.45/0.43 (n=1862)  0.5-0.6: 0.55/0.54 (n=1933)  0.6-0.7: 0.65/0.66 (n=1826)  0.7-0.8: 0.75/0.74 (n=1299)  0.8-0.9: 0.85/0.86 (n=749)  0.9-1.0: 0.93/0.96 (n=250)

Flat-stake ROI at the close (fitted - close >= 3 pts, either side; never decisive)
  ATP        picks 0
  WTA        picks  1824  won  1119  units     -9.52  ROI -0.5%
  ATP+WTA    picks  1824  won  1119  units     -9.52  ROI -0.5%
  CHALLENGER picks  7504  won  5820  units   -162.07  ROI -2.2%

Holdout gates (pre-registered at 2 standard errors; L1 comes from --live)
  ATP+WTA    H1 vs hand-set blend -0.0058 +/- 0.0012 -> pass   H2 vs close +0.0002 +/- 0.0004 -> pass
  CHALLENGER H1 vs hand-set blend -0.0063 +/- 0.0006 -> pass   H2 vs close -0.0006 +/- 0.0003 -> pass
```

**Live:** `python -m app.backtest.tennis_market_blend --live`

```
Tennis market-anchored blend (26d) - LIVE gate L1 on 26a's settled predictions
  TennisAbstract ELO and the one-book market at prediction time; any ensemble version, latest pre-start row.
  Gate: the 15-point ELO-market gap only (graded rows carry no prior-match counts).

Fitted minus the market at prediction (negative = fitted better; +/- one standard error)
  ATP        n=208    vs market -0.0010 +/- 0.0016   context: vs stored ensemble -0.0051 +/- 0.0085 (n=208)
  WTA        n=230    vs market +0.0023 +/- 0.0035   context: vs stored ensemble -0.0056 +/- 0.0108 (n=230)
  ATP+WTA    n=438    vs market +0.0008 +/- 0.0020   context: vs stored ensemble -0.0054 +/- 0.0070 (n=438)
  CHALLENGER n=398    vs market -0.0005 +/- 0.0030   context: vs stored ensemble -0.0116 +/- 0.0093 (n=398)

Live gate (pre-registered at 2 standard errors)
  ATP+WTA    L1 vs market +0.0008 +/- 0.0020 -> pass
  CHALLENGER L1 vs market -0.0005 +/- 0.0030 -> pass
```

**Verdict (pre-registered rule):**

| Group | H1 vs hand-set blend | H2 vs close | L1 vs live market | Result |
|---|---|---|---|---|
| ATP+WTA | -0.0058 +/- 0.0012, **pass** (4.8 SE) | +0.0002 +/- 0.0004, **pass** | +0.0008 +/- 0.0020, **pass** | **adopted** |
| CHALLENGER | -0.0063 +/- 0.0006, **pass** (10.5 SE) | -0.0006 +/- 0.0003, **pass** | -0.0005 +/- 0.0030, **pass** | **adopted** |

**What it means:**
- **The fitted blend replaces a worse forecast, not a market-beater.** It is
  clearly better than the hand-set blend, and level with the close
  (ATP+WTA +0.0002 +/- 0.0004). It is the close, slightly extremized, and
  well calibrated.
- **Its disagreements with the market are not bettable.** Betting 3+ point
  gaps at the close lost 0.5% on 1,824 WTA picks and 2.2% on 7,504 Challenger
  picks. ATP's blend never moves 3 points from the close.
- **WTA's negative ELO weight held up on the holdout only as a forecast** (WTA
  +0.0004 +/- 0.0008 against the close), not as an edge.
- **L1 is weak evidence**, as expected at n=438 and 398: the fit is level with
  the live market within about 1 SE, and ahead of the stored ensemble on every
  group by about 0.7 to 1.2 SE (context only).
- **Product consequence for Step 7:** served as `ensemble-v3`, the ensemble
  sits within a point or two of the market, so moneyline edges and best-pick
  moneyline plays largely disappear. That is the intended, honest outcome.

The fit uses Newton's method in numpy rather than scikit-learn: scikit-learn
1.8 warns on every unpenalized fit, and two coefficients need no library.

## Notes for the AI

- **Do not run `--holdout` before Step 6**, and run it once. If something is
  found broken afterwards, record the rerun as a second, labeled run; never
  overwrite the first.
- **Never fit on holdout seasons.** The fit filters them out before the
  regression, and a test proves it.
- **Keep `app/core/` pure.** scikit-learn and file I/O stay in `app/backtest/`;
  the generated coefficient file holds constants only.
- **Reuse, don't copy:** `build_cases`, `exclusion`, `load_valuebetennis` and
  the 26c constants; `paired_loss_difference`, `score_component` and
  `calibration_bins`; `elo_is_unreliable`; and 26a's `tennis_predictions`
  loader.
- Phrase results by the rule, not by eye. Development numbers are in-sample
  and must be labeled so.
- Credit Valuebetennis (CC BY 4.0) in both CLI headers.
- Standards: `X | None` in new code, no `Any`, no em dashes, comment only the
  why.
