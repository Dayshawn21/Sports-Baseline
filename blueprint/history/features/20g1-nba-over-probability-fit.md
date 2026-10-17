# Feature: NBA over-probability fit

**From build-plan:** feature 20g1 (first of 20g's four parts)
**Status:** complete (2026-10-06)

## Goal

Turn the NBA reference projection (20f) into a probability that the result
lands over a line, per market, and decide which markets may use it. NFL's 27g
is the model: an empirical distribution of `actual / projection`, read at any
line.

**Why:** 20f's holdout showed the reference is nearly unbiased but sits above
the median in every market (`share_below` 52% to 58%, blocks 68%), so a mean
alone misreads over/under. The shared ranking rule (27i) also picks only on a
side's probability, so 20g3's frozen predictions and 20g4's ranking check need
P(over) to grade anything.

The fit is made on the 2024-25 development season and scored on the 2025-26
holdout under a calibration rule fixed in this spec. Markets that pass are
frozen into a generated module. **Nothing is served:** 20g2 shows it, 20g3
freezes it.

## Design reference

None. A CLI report and a generated module, no UI.

## In scope

- **Versions, fixed now:** `NBA_PROJECTION_MODEL_VERSION = "nba-reference-v1"`
  (the 20f reference arm, as 20g2 will serve it) and
  `NBA_OVER_PROBABILITY_VERSION = "nba-pover-v1"`.
- **A pure module, `app/core/nba_over_probability.py`:** per-market fit
  (ratio quantiles plus the normal baseline's sigma), holdout scoring on
  synthetic lines, and NBA's own display verdict. It reuses 27g's
  sport-agnostic pieces unchanged: `ratio_quantiles` and `over_probability`
  (`app/core/nfl_over_probability.py`), and `synthetic_lines`, `calibrate`
  and `normal_over_probability` (`app/core/nfl_over_probability_calibration.py`).
- **A fit CLI, `python -m app.backtest.nba_over_probability_fit`:** replays
  20f's reference arm on 2024-25 (fit) and 2025-26 (score), prints each
  market's calibration and verdict, and with `--write` freezes the passing
  markets' 2024-25 tables into `app/core/nba_over_probability_fit.py`.
- **One scored run**, with the verdicts under Results.

## Out of scope

- Serving P(over) anywhere, the `NbaPropMarket` enum, game-page cards (20g2).
- Frozen predictions, `NbaPropSource`, workflows (20g3).
- Ranking, picks, break-even comparison, the model page (20g4).
- Double-double (no mean projection; 20f excluded it).
- Integer lines: they can push, which v1 does not model, so they read None
  (as NFL's). PrizePicks posted 4 integer standard lines among the 194
  opening-night NBA lines.
- Splits beyond market (position, minutes, home or away). The report shows
  calibration by prior-minutes bucket for information only.
- A second distribution method for a market that hides. A later item may try
  one, on the development season first.
- Refitting on 2025-26 for serving: the frozen table is the 2024-25 fit that
  was scored, so what is served is exactly what passed.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Fit, scoring and the display rule (pure)** - in
  `app/core/nba_over_probability.py`:
  - `NBA_OVER_PROBABILITY_VERSION`, and `NBA_PROJECTION_MODEL_VERSION` beside
    `REFERENCE_ARM` in `app/core/nba_projection_backtest.py`.
  - `fit_markets(cases) -> dict[str, MarketFit]`: per market, the ratio
    quantiles of `actual / projection` (cases with a positive projection) and
    the standard deviation of `actual - projection` for the normal baseline.
  - `score_cases(fits, cases) -> list[ScoredLine]`: for each case with a fit,
    each of its `synthetic_lines(projection)`, the fitted P(over), the normal
    P(over), and whether the actual went over.
  - `nba_display_verdict(cases_n, report, normal_brier)` with NBA's own
    constants (rule below). The worst-bin check is computed here from
    `report.bins` with NBA's own minimum bin size, so a change to NFL's 27g
    constants cannot move NBA's rule.

  *Done when:* unit tests cover: quantiles and sigma on a known set; a case
  with a zero projection skipped by the fit and by scoring; a market with no
  fit not scored; synthetic lines and the over flag for a known case; each
  verdict branch (299 / 300 cases, ECE exactly 0.02, a 200-pair bin exactly
  0.05 off, a 199-pair bin far off ignored, Brier equal to the normal's
  passing); a constants test pinning the rule values and both versions.

- [x] **Step 2 - The fit CLI and report** -
  `app/backtest/nba_over_probability_fit.py` (no `--write` yet): loads history
  for 2023 to 2025 once, builds 20f's reference cases for 2024 and 2025, fits
  on 2024, scores 2025, and prints:
  - a header naming the fit and scored seasons, both versions, the rule text,
    and "holdout read 2 (no projection verdict)";
  - per market: cases, pairs, ECE, worst gap, Brier, normal Brier, verdict,
    and which checks failed;
  - per market at the synthetic line nearest the projection: mean predicted
    P(over), observed rate, and the normal's (the median gap, as a
    probability);
  - per market and prior-minutes bucket (20 to under 28, 28+): ECE, for
    information.

  *Done when:* a report test on synthetic scored lines checks one market row,
  one nearest-line row and a verdict; the live run completes and its timing is
  noted.

- [x] **Step 3 - Freeze the passing markets** - `--write` renders
  `app/core/nba_over_probability_fit.py` (generated, never hand-edited):
  `FIT_SEASON = 2024`, `SCORED_SEASON = 2025`,
  `FIT_PROJECTION_MODEL_VERSION`, `OVER_PROBABILITY_VERSION`,
  `SHOWN_MARKETS`, and `QUANTILES_BY_MARKET` for shown markets only (four
  decimals, as 27g's). Run once with `--write`; paste the output under
  Results.

  *Done when:* a test imports the generated module and checks its
  `FIT_PROJECTION_MODEL_VERSION` equals `NBA_PROJECTION_MODEL_VERSION`,
  `SHOWN_MARKETS` is a subset of the backtest markets, every shown market has
  41 non-decreasing quantiles, and a hidden market has none; a render test on
  a small fit checks the module text; the full suite passes.

## Files / areas

- New: `api/app/core/nba_over_probability.py`,
  `api/app/backtest/nba_over_probability_fit.py`,
  `api/app/core/nba_over_probability_fit.py` (generated),
  `api/tests/test_nba_over_probability.py`,
  `api/tests/test_nba_over_probability_fit.py`
- Changed: `api/app/core/nba_projection_backtest.py` (the projection version
  constant)
- Read only: `api/app/core/nfl_over_probability.py`,
  `api/app/core/nfl_over_probability_calibration.py`,
  `api/app/backtest/nba_projections.py`, `api/app/repositories/nba.py`

## Data / contracts

No schema change, no API change.

**Load-bearing for 20g2 to 20g4:**
- `NBA_PROJECTION_MODEL_VERSION = "nba-reference-v1"`: the reference arm's
  20-game mean, on 20f's eligibility (10 prior played games, 20 prior
  minutes). 20g2 serves exactly this and stamps frozen rows with it.
- `NBA_OVER_PROBABILITY_VERSION = "nba-pover-v1"`.
- **The generated fit is read only while** its `FIT_PROJECTION_MODEL_VERSION`
  equals `NBA_PROJECTION_MODEL_VERSION`; any projection change hides P(over)
  until a new fit is scored (27g's rule).
- **P(over) is read with 27g's `over_probability(quantiles, projection,
  line)`**: None for an integer line or a projection at or below zero, never
  0.5.
- A line gets a projection and P(over) only on 20f's eligible player-games
  (the same gate the fit was scored on).

**The pre-registered display rule** (fixed when this spec is approved, before
any fit is scored). A market is **shown** only when all hold on its 2025-26
scored pairs:

1. at least 300 cases;
2. ECE of 0.02 or less across its synthetic-line pairs;
3. no bin holding 200 or more pairs is off by more than 0.05 (mean predicted
   against observed);
4. Brier no worse than the normal baseline on the same pairs.

Below 300 cases the verdict is `insufficient`, otherwise `hide`. Each market
is scored once, with the method fixed here; rerunning the same deterministic
fit (Step 3's `--write` after Step 2's run) is the same read, not a second
one. These are 27g's values, kept as NBA's own constants.

## Testing

- Test gate on: Step 1 unit tests, Step 2 a report test, Step 3 a
  generated-module test and a render test.
- `cd api && .venv\Scripts\python.exe -m pytest` after each step.
- No web change.

## Notes for the AI

- **Holdout bookkeeping:** this is the 2025-26 holdout's second read (20f's
  descriptive reference run was the first) and takes no projection verdict.
  Fit nothing on 2025-26.
- Build cases with 20f's `replay_cases(history, season, ARMS[REFERENCE_ARM])`
  from one `get_projection_history(db, (2023, 2024, 2025))` load.
- **Counts are small integers** (blocks, threes, assists): ratio scaling
  smoothed NFL's receptions into a hide. Expect some NBA markets to hide; that
  is the rule working, not a bug. Do not switch methods mid-feature.
- `synthetic_lines` only produces x.5 lines, so holdout pairs never push.
- Reuse 27g's functions without editing them; NBA owns only its fit, scoring,
  verdict and constants.
- The generated module mirrors `app/core/nfl_over_probability_fit.py`'s
  layout; render it with a function the test can call.
- `X | None`, no `Any`, dataclasses inside, `app/core` pure, no em dashes,
  comment only the why.

## Results

Run 2026-10-06, `python -m app.backtest.nba_over_probability_fit --write`
(17.9 s). Fitted on 2024-25's 17,010 eligible player-games, scored on
2025-26's 17,346. **Holdout reads: 2** (20f's descriptive reference run,
then this fit's scoring); no projection verdict. Step 3's `--write` run
printed a byte-identical report, so it is the same read.

**Verdict: one market shows, assists.** Eight hide.

| Market | Cases | ECE | Worst bin | Brier vs normal | Verdict | Failed on |
|---|---|---|---|---|---|---|
| assists | 17,346 | 0.0196 | 0.043 | 0.2003 vs 0.2007 | **show** | |
| rebounds | 17,346 | 0.007 | 0.075 | 0.1912 vs 0.1922 | hide | worst bin |
| threes made | 16,290 | 0.019 | 0.086 | 0.2073 vs 0.2101 | hide | worst bin |
| points | 17,346 | 0.007 | 0.051 | 0.1892 vs 0.1871 | hide | worst bin, Brier |
| blocks | 17,070 | 0.081 | 0.142 | 0.2124 vs 0.2150 | hide | ECE, worst bin |
| pts + reb + ast | 17,346 | 0.004 | 0.036 | 0.1668 vs 0.1640 | hide | Brier |
| pts + reb | 17,346 | 0.003 | 0.016 | 0.1741 vs 0.1719 | hide | Brier |
| pts + ast | 17,346 | 0.005 | 0.144 | 0.1793 vs 0.1765 | hide | worst bin, Brier |
| reb + ast | 17,346 | 0.006 | 0.046 | 0.1781 vs 0.1777 | hide | Brier |

**Reading it:**
- **Assists passes narrowly** (ECE 0.0196 against 0.02, Brier 0.00035 under
  the normal's).
- **The median gap is real and the fit captures it.** At the line nearest
  the projection, predicted P(over) is within 0.007 of the observed rate in
  eight of nine markets (points 0.467 vs 0.469, threes 0.417 vs 0.419); a
  normal says about 0.50 everywhere.
- **Combos lose to the normal on Brier**: their sums are closer to
  symmetric, as NFL's passing markets were (27g).
- **Small counts break the ratio scaling.** Several markets fail on one
  thin middle bin (points: 1,479 pairs predicted 0.723, observed 0.671), and
  blocks is clearly off (0.250 predicted, 0.315 observed at the projection).
- **What it means for 20g2 to 20g4:** P(over) exists for assists only, so
  frozen probabilities and the ranking check's picks would come from assists
  lines alone; other markets serve a projection without P(over). A
  count-aware or different method for the hidden markets is a new item, tried
  on 2024-25 first.

**History depth (found in Step 2):** this run loads 2023-24 to 2025-26, 20f's
harness loads one prior season, so 32 of 17,346 holdout player-games (players
who missed 2024-25) are eligible here and not in 20f's run. It changes no
verdict, but "the last 20 prior played games" depends on how much history is
loaded; 20g2 should fix it (all stored seasons, as this fit's holdout used).

Output (the eight hidden markets' reliability tables are omitted):

```
NBA over probability fit: fitted on 2024-25, scored on the 2025-26 holdout
Projection nba-reference-v1, P(over) nba-pover-v1; holdout read 2 (no projection verdict)

Show a market only with >= 300 cases, ECE <= 0.02, no bin of 200+ pairs off by more than 0.05, and Brier no worse than a normal on the same pairs (pre-registered 2026-10-06).

  market                      cases   pairs     ECE   worst   Brier  normal  verdict   failed on
  points                      17346   86714   0.007   0.051  0.1892  0.1871  hide      worst gap, Brier
  rebounds                    17346   79862   0.007   0.075  0.1912  0.1922  hide      worst gap
  assists                     17346   65349   0.020   0.043  0.2003  0.2007  show      
  threes_made                 16290   44066   0.019   0.086  0.2073  0.2101  hide      worst gap
  blocks                      17070   23115   0.081   0.142  0.2124  0.2150  hide      ECE, worst gap
  points_rebounds_assists     17346   86730   0.004   0.036  0.1668  0.1640  hide      Brier
  points_rebounds             17346   86730   0.003   0.016  0.1741  0.1719  hide      Brier
  points_assists              17346   86729   0.005   0.144  0.1793  0.1765  hide      worst gap, Brier
  rebounds_assists            17346   86330   0.006   0.046  0.1781  0.1777  hide      Brier

At the line nearest the projection (1.0 multiple): the median gap as a probability
  market                          n  predicted  observed  normal
  points                      17346      0.467     0.469   0.498
  rebounds                    17346      0.454     0.454   0.496
  assists                     17346      0.450     0.454   0.496
  threes_made                 16290      0.417     0.419   0.490
  blocks                      17070      0.250     0.315   0.447
  points_rebounds_assists     17346      0.477     0.479   0.499
  points_rebounds             17346      0.475     0.475   0.499
  points_assists              17346      0.472     0.479   0.499
  rebounds_assists            17346      0.464     0.463   0.498

ECE by prior minutes (information only; the verdict pools them)
  market / prior minutes                 pairs     ECE
  points / 20-28 min                     42649   0.031
  points / 28+ min                       44065   0.033
  rebounds / 20-28 min                   37139   0.018
  rebounds / 28+ min                     42723   0.022
  assists / 20-28 min                    27950   0.027
  assists / 28+ min                      37399   0.033
  threes_made / 20-28 min                18974   0.017
  threes_made / 28+ min                  25092   0.027
  blocks / 20-28 min                     10794   0.075
  blocks / 28+ min                       12321   0.085
  points_rebounds_assists / 20-28 min    42665   0.034
  points_rebounds_assists / 28+ min      44065   0.035
  points_rebounds / 20-28 min            42665   0.032
  points_rebounds / 28+ min              44065   0.033
  points_assists / 20-28 min             42664   0.036
  points_assists / 28+ min               44065   0.036
  rebounds_assists / 20-28 min           42280   0.026
  rebounds_assists / 28+ min             44050   0.028

Reliability, assists
     bin n  predicted  observed
       162      0.091     0.296
      6528      0.176     0.191
     12248      0.247     0.223
      8838      0.341     0.325
      9146      0.449     0.452
      7187      0.555     0.557
      7019      0.641     0.661
      8422      0.755     0.788
      5799      0.833     0.789
```

The generated `app/core/nba_over_probability_fit.py` holds assists only, at
four decimals.
