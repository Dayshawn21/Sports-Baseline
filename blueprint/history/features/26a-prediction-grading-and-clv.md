# Feature: Prediction grading and CLV

**From build-plan:** feature 26a
**Status:** complete

## Goal

Answer, with the data already stored, whether the tennis model is right. Score
each stored prediction's ELO, LightGBM, market, and ensemble probabilities against
settled results, and measure closing-line value: when the model disagreed with the
market, did the market move toward the model before the match started?

This is a read-only report with no model change. It gives items 26c and 26d
their scoring code, and tells us whether the ensemble adds anything over the
de-vigged market.

## In scope

- **Pure scoring code in `app/core/tennis_grading.py`:**
  - log loss and Brier, reusing `app.core.nfl_td_backtest.log_loss` and `brier`
  - a paired per-match loss difference with its standard error, so "the
    ensemble beats the market" comes with an error bar
  - calibration bins
  - a CLV summary
  - a completed-score check that excludes retirements and walkovers
- **A repository loader** that returns one graded row per settled match:
  - the **last prediction generated before `start_utc`**
  - the outcome
  - the market price when the prediction was made: the last `match_odds`
    moneyline row at or before `generated_at`, ties broken by the shared book
    priority
  - the closing price **from that same book**: its last moneyline row at or
    before `start_utc`
- **A command-line report,** run from `api/` as
  `python -m app.backtest.tennis_predictions`:
  - per tour (ATP, WTA, CHALLENGER), each component scored on the **common
    subset** where every compared component exists
  - the ensemble and ELO each paired against the market
  - calibration bins for the ensemble and the market
  - CLV overall, by tour, and for disagreements of 3 points or more
  - how many rows each filter excluded
- **Grading v6 only by default** (`ensemble-v1+lgbm-v6`), with a `--model-version`
  flag. Other versions are counted but not mixed in.

## Out of scope

- Any change to the model, the weights, or pick thresholds (26d).
- PrizePicks prop grading (26b), and historical odds import (26c).
- Storing pick snapshots, or grading the picks as shown on the page.
  Predictions are graded, not recomputed best picks. A pick-snapshot table would
  be a later, schema-changing item.
- An API endpoint or UI for the report. It stays a CLI, like the NFL backtests.
- A scheduled job. The report reads live tables whenever it is run.

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

- [x] **Step 1 - Pure grading core.** Add `app/core/tennis_grading.py`:
  - `ComponentScore`: n, log loss, Brier, mean predicted, actual rate.
  - `score_component`.
  - `paired_loss_difference`: mean per-match log-loss difference with its
    standard error.
  - `calibration_bins`: fixed 10-point bins, empty bins omitted.
  - `clv_summary`: over rows with a market price at prediction and at close,
    - how many moved and how many didn't
    - the share of moved rows that moved toward the model
    - the mean signed move toward the model, in probability points
    - an optional minimum model-versus-market gap
  - `is_completed_score`: every set is a finished set (6-x with x ≤ 4, 7-5 or
    7-6), and there are two or three sets for best-of-3 or three to five for
    best-of-5.

  *Done when:* unit tests pass, covering:
  - a perfect and a coin-flip forecast's log loss and Brier
  - the paired difference sign and standard error on a hand-worked example
  - bin edges, including a 1.0 probability
  - CLV toward, away and unmoved, and the minimum-gap filter
  - retirements (`3-6 3-5`, `7-5 2-6 0-0`), walkovers (empty score) and
    best-of-5 scores
- [x] **Step 2 - Graded-prediction loader.** Add `get_graded_predictions(db)` to
  `app/repositories/predictions.py`, returning `GradedPrediction` rows (below):
  - one row per completed match with a winner and a non-null `start_utc`
  - the latest prediction with `generated_at < start_utc`, ties broken by `id`
  - the opening moneyline row: the latest with `fetched_at <= generated_at`,
    newest first, then `_BOOK_PRIORITY_SQL`
  - the closing moneyline row: that book's latest with
    `fetched_at <= start_utc`

  Add the pure `build_graded_prediction` mapper, which de-vigs both prices,
  sets `p1_won`, and sets `completed_score`.

  *Done when:*
  - Recorded-SQL tests show the prediction chosen strictly before the start,
    the opening price at or before `generated_at`, the closing price from the
    same book at or before the start, and the book tie-break.
  - Mapper tests cover both sides winning and a missing closing price.
  - A read-only run against the live database returns about 1,196 rows, the
    count of settled matches with a pre-start prediction on 2026-09-25, with
    the tour split and closing-price coverage printed.
- [x] **Step 3 - Report.** Add `app/backtest/tennis_predictions.py`, with a pure
  `report(rows, model_version)` and an async CLI `_main`, following
  `app/backtest/nfl_game_lines.py`. It prints:
  - exclusion counts (other model versions, retirements and walkovers, missing
    components)
  - a per-tour table of n, log loss and Brier for ELO, ML, market and ensemble
    on the common subset
  - ensemble-minus-market and ELO-minus-market paired differences with their
    standard errors
  - calibration bins
  - CLV overall, by tour, and with a gap of 3 points or more

  *Done when:*
  - A test on synthetic rows checks the section headers, the exclusion
    counts, and that the common subset drops rows missing any compared
    component.
  - `python -m app.backtest.tennis_predictions` runs against the live
    database, and its output is pasted into this spec's Results section.

## Files / areas

- `api/app/core/tennis_grading.py` (new) - pure scoring functions.
- `api/app/repositories/predictions.py` - `GradedPrediction`,
  `get_graded_predictions`, `build_graded_prediction`.
- `api/app/backtest/tennis_predictions.py` (new) - report and CLI.
- `api/tests/test_tennis_grading.py`, `api/tests/test_graded_predictions.py`,
  `api/tests/test_tennis_prediction_report.py` (new).

## Data / contracts

No schema change. The row shape is **load-bearing**, because 26c scores
historical rows through the same code and 26d fits on these rows:

```python
@dataclass(frozen=True)
class GradedPrediction:
    match_id: int
    tour: str                         # matches.tour: ATP | WTA | CHALLENGER
    start_utc: datetime
    generated_at: datetime            # the graded prediction, always < start_utc
    model_version: str
    p1_won: bool
    completed_score: bool             # False for retirements and walkovers
    elo_prob: float | None            # all p1-oriented
    ml_prob: float | None
    market_prob: float | None         # de-vigged, at prediction time, from match_odds
    ensemble_prob: float | None
    market_book: str | None           # the book both market prices come from
    closing_market_prob: float | None # de-vigged, same book, last pre-start row
```

`market_prob` is recomputed from `match_odds`, not taken from the stored
`predictions.p1_market_prob`. Before the odds fix, the stored value came from
whichever book won an arbitrary same-run tie, so comparing it with a closing price
from another book would record a book switch as a market move.

**CLV definition:**
- `gap = ensemble_prob - market_prob`
- `move = closing_market_prob - market_prob`
- A row moved toward the model when `sign(move) == sign(gap)` and
  `move != 0`. Rows where either is 0, or either price is missing, count as
  unmoved or unavailable, never as toward.

## Testing

- The test gate is on:
  - Step 1 ships pure unit tests.
  - Step 2 ships recorded-SQL and mapper tests.
  - Step 3 ships a report test on synthetic rows.
- Run with `cd api && .venv\Scripts\python.exe -m pytest`.
- Evidence beyond the tests:
  - Step 2's live row count.
  - Step 3's live report, pasted under Results.
- No web change.

## Results

`python -m app.backtest.tennis_predictions`, run 2026-09-25 against the stored
data (read-only):

```text
Tennis prediction grading - ensemble-v1+lgbm-v6
  settled matches with a pre-start prediction: 1196
  excluded, other model versions:              94
  excluded, retirements and walkovers:         31
  graded:                                      1071  (market price at prediction: 732, same-book close: 732)

Model components (log loss, Brier; lower is better)
  group           n                elo                 ml           ensemble
                        logloss  brier     logloss  brier     logloss  brier
  ATP           178    0.5600   0.1886    0.5828   0.1992    0.5624   0.1897
  WTA           211    0.5238   0.1740    0.5363   0.1807    0.5236   0.1739
  ATP+WTA       389    0.5404   0.1807    0.5576   0.1892    0.5413   0.1811
  CHALLENGER    439    0.6816   0.2401    0.6438   0.2267    0.6423   0.2253

Against the market (same matches for every column)
  group           n                elo                 ml           ensemble             market
                        logloss  brier     logloss  brier     logloss  brier     logloss  brier
  ATP           122    0.5495   0.1843    0.5727   0.1936    0.5502   0.1837    0.5405   0.1794
  WTA           152    0.5083   0.1677    0.5128   0.1714    0.5038   0.1658    0.5014   0.1638
  ATP+WTA       274    0.5267   0.1751    0.5395   0.1813    0.5244   0.1737    0.5188   0.1708
  CHALLENGER    291    0.6587   0.2313    0.6302   0.2207    0.6238   0.2175    0.6165   0.2140

Paired log-loss difference vs market (negative = beats the market; +/- one standard error)
  ATP        n=122   elo +0.0090 +/- 0.0143   ml +0.0321 +/- 0.0186   ensemble +0.0097 +/- 0.0102
  WTA        n=152   elo +0.0069 +/- 0.0123   ml +0.0115 +/- 0.0154   ensemble +0.0024 +/- 0.0096
  ATP+WTA    n=274   elo +0.0079 +/- 0.0093   ml +0.0207 +/- 0.0119   ensemble +0.0056 +/- 0.0070
  CHALLENGER n=291   elo +0.0423 +/- 0.0160   ml +0.0137 +/- 0.0156   ensemble +0.0074 +/- 0.0095

Calibration (predicted vs actual p1 win rate, matches with every component)
  ATP+WTA    ensemble  0.0-0.1: 0.09/0.00 (n=2)  0.1-0.2: 0.16/0.11 (n=9)  0.2-0.3: 0.25/0.16 (n=25)  0.3-0.4: 0.35/0.25 (n=36)  0.4-0.5: 0.45/0.45 (n=49)  0.5-0.6: 0.55/0.57 (n=28)  0.6-0.7: 0.65/0.67 (n=43)  0.7-0.8: 0.75/0.92 (n=37)  0.8-0.9: 0.85/0.90 (n=31)  0.9-1.0: 0.92/0.93 (n=14)
  ATP+WTA    market    0.0-0.1: 0.06/0.00 (n=1)  0.1-0.2: 0.15/0.09 (n=11)  0.2-0.3: 0.26/0.16 (n=31)  0.3-0.4: 0.35/0.32 (n=37)  0.4-0.5: 0.44/0.32 (n=31)  0.5-0.6: 0.55/0.64 (n=39)  0.6-0.7: 0.64/0.74 (n=38)  0.7-0.8: 0.76/0.82 (n=44)  0.8-0.9: 0.86/0.93 (n=30)  0.9-1.0: 0.92/0.92 (n=12)
  CHALLENGER ensemble  0.1-0.2: 0.18/0.00 (n=4)  0.2-0.3: 0.26/0.13 (n=23)  0.3-0.4: 0.35/0.24 (n=37)  0.4-0.5: 0.45/0.64 (n=66)  0.5-0.6: 0.55/0.57 (n=60)  0.6-0.7: 0.65/0.63 (n=65)  0.7-0.8: 0.75/0.76 (n=29)  0.8-0.9: 0.83/1.00 (n=7)
  CHALLENGER market    0.0-0.1: 0.08/0.00 (n=1)  0.1-0.2: 0.16/0.14 (n=7)  0.2-0.3: 0.25/0.16 (n=31)  0.3-0.4: 0.35/0.48 (n=42)  0.4-0.5: 0.45/0.46 (n=48)  0.5-0.6: 0.55/0.55 (n=64)  0.6-0.7: 0.65/0.76 (n=51)  0.7-0.8: 0.75/0.73 (n=37)  0.8-0.9: 0.84/0.88 (n=8)  0.9-1.0: 0.91/1.00 (n=2)

Closing-line value (did the same book's price move toward the ensemble before the start?)
  all                        eligible  732  moved  319  toward model  185 (58.0%)  mean move toward +0.36 pts
  all, gap >= 3 pts          eligible  493  moved  225  toward model  133 (59.1%)  mean move toward +0.47 pts
  ATP                        eligible  133  moved   51  toward model   27 (52.9%)  mean move toward +0.15 pts
  ATP, gap >= 3 pts          eligible   78  moved   31  toward model   16 (51.6%)  mean move toward +0.27 pts
  WTA                        eligible  164  moved   36  toward model   25 (69.4%)  mean move toward +0.21 pts
  WTA, gap >= 3 pts          eligible   94  moved   18  toward model   13 (72.2%)  mean move toward +0.23 pts
  ATP+WTA                    eligible  297  moved   87  toward model   52 (59.8%)  mean move toward +0.18 pts
  ATP+WTA, gap >= 3 pts      eligible  172  moved   49  toward model   29 (59.2%)  mean move toward +0.25 pts
  CHALLENGER                 eligible  435  moved  232  toward model  133 (57.3%)  mean move toward +0.48 pts
  CHALLENGER, gap >= 3 pts   eligible  321  moved  176  toward model  104 (59.1%)  mean move toward +0.59 pts
```

**Reading, with about 270 to 290 matches per market comparison and one month of
data. Nothing here is settled:**

- **The market beats every model component on log loss**, in every group. The
  gaps are small and within about one standard error for the ensemble: ATP+WTA
  +0.0056 +/- 0.0070, Challenger +0.0074 +/- 0.0095. There is no evidence yet
  that the ensemble adds accuracy over the de-vigged market.
- **v6 LightGBM is the weakest component on ATP and WTA.** It is +0.0207 +/-
  0.0119 behind the market on ATP+WTA, about 1.7 standard errors, and worse than
  plain ELO. The ensemble scores close to ELO.
- **On Challenger, ELO is clearly worst:** +0.0423 +/- 0.0160 against the market.
- **CLV is the one positive sign.** Of 319 prices that moved before the start,
  185 (58.0%) moved toward the ensemble. Against a 50% null, that is about 2.9
  standard errors (binomial, n = 319). It holds for 3-point-plus disagreements
  too (59.1% of 225).
- **But the moves are small.** The mean move toward the model is +0.36 points,
  far below a typical moneyline margin of 4 to 5 points. On this evidence, betting
  the opening price where the model disagrees would not beat the vig.
- **These are signals for 26c and 26d, not decisions.** 26c's multi-year
  closing-line backtest is where adoption is decided.

## Notes for the AI

- **Repositories own SQL.** The loader lives in `app/repositories/`. The
  backtest and core modules make no queries of their own.
- **Keep `app/core/tennis_grading.py` pure:** no database, no clock, no model
  loading.
- **Reuse, don't copy.** Import `log_loss` and `brier` from
  `app.core.nfl_td_backtest`, and `_BOOK_PRIORITY_SQL` from
  `app.repositories.matches`. Item 17 can later move them to a shared module.
- **A prediction generated at or after `start_utc` is never graded.** On
  2026-09-25 that filter drops 397 of 1,593 settled matches.
- **Opening and closing prices must come from the same book.** A DraftKings
  price against a Bet365 price is a book difference, not a market move.
- **Challenger predictions before 2026-09-25 carry WTA-model ML probabilities.**
  Report Challenger separately and do not pool it with ATP and WTA.
- **Small sample.** About 1,200 matches over one month. Report the standard
  errors, and don't phrase any difference as settled unless it exceeds about two
  of them.
- Never call the Odds-API.io API; everything reads stored tables.
