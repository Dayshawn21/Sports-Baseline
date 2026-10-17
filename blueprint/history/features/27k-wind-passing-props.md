# Feature: Wind for passing props

**From build-plan:** feature 27k
**Status:** complete (not adopted: wind rejected in all three passing markets)

## Goal

Test whether strong wind lowers NFL passing volume and yardage enough to
improve the prop projection. Fit one wind slope per passing market on 2024,
score it once through the 27b harness on 2025 (stacked on production), and
adopt it only for markets that pass the pre-registered rule. A pass does not
go live automatically: live use costs the P(over) display and the 27j sample,
so it needs a separate yes (Step 6).

**Why only passing props.** Wind is already tested for game lines and rejected
there: 24e's total MAE went from 10.1891 at the close to 10.1949 with context
added. But the market prices a game total, not a QB's attempts. Player passing
props are the one place weather has never been tested.

**The variant** (pre-registered here, 2026-09-26, before any fit or score):

    excess_wind = max(0, wind_mph - 10) / 10        outdoor games with known wind
    excess_wind = 0                                 indoor (dome, closed roof)
    excess_wind = None                              outdoor with wind unknown
    adjustment  = clamp(b_wind[market] * excess_wind, +/-0.15)
    projection *= 1 + adjustment                    after every existing step

`b_wind` is the fractional change per 10 mph of wind above 10 mph, from a
frozen 2024 fit (Step 3), never fitted on 2025. An unknown-wind game gets no
adjustment, never a zero-wind one.

## In scope

- **Wind on replay and fit rows.** Replay rows and 2024 fit games carry the
  game's `roof` and observed `wind`. No behavior change.
- **A pure module,** `app/core/nfl_wind.py`: `excess_wind`, the adjustment, the
  row transform, the 2024 sample builder and fit.
- **A 2024 fit CLI** that prints the slopes, then freezes them as constants.
- **A `wind` harness arm,** stacked on production, for the three passing
  markets only.
- **One scored run on 2025,** with each market's verdict under Results.
- **Conditional live adoption** (Step 6): only with a passing market **and**
  the user's separate yes. Otherwise Step 6 is skipped and production is
  unchanged.

## Out of scope

- **Game lines and anytime TD.** 24e and 19n rejected weather for them.
- **Rushing, receiving, receptions, fantasy.** Rushing plausibly rises in wind
  and receiving falls, but each market tested spends the 2025 holdout again.
  A later item if passing shows a clear effect.
- **Temperature, precipitation, gusts.** One feature only. Retuning the 10 mph
  threshold, the /10 scale, or the cap after seeing results is not allowed.
- **A relative-to-baseline form** (27e's). See Notes: wind averages near zero
  over a season, so the absolute form was chosen up front.
- **A historical forecast backfill.** Past forecasts are not stored; the
  backtest uses observed wind (see Notes).
- P(over) refit and ranking changes, unless Step 6 runs.

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

- [x] **Step 1 - Wind on rows (no behavior change).** In
  `app/repositories/nfl.py`:
  - The `get_replay_rows` outcomes query also selects `g.roof` and `g.wind`,
    and each replay row gains
    `row["game_weather"] = {"roof": str | None, "wind": int | None}`.
  - `get_environment_fit_games` also selects `g.roof` and `g.wind`, and
    `NflEnvironmentGame` gains `roof: str | None = None` and
    `wind: int | None = None`. The 27e fit reads neither, so its output is
    unchanged.

  *Done when:*
  - A repository test shows an outdoor game's row carrying its roof and wind,
    and a dome game's carrying `roof="dome"`.
  - `python -m app.backtest.nfl_game_environment_fit --season 2024` prints the
    same slopes as the 27e archive.
  - `pytest` passes.

  *Built:* seven of eight markets match the 27e archive exactly. Fantasy
  differs slightly (total SE 0.160 vs 0.162, margin +0.005 vs +0.008), and
  master's code gives the same new numbers, so it predates this branch
  (probably 27f's switch to PrizePicks fantasy points). Fantasy slopes are
  zeroed either way.
- [x] **Step 2 - Pure wind math and fit.** Add `app/core/nfl_wind.py`:
  - `WIND_THRESHOLD_MPH = 10`, `WIND_SCALE_MPH = 10.0`,
    `WIND_ADJUSTMENT_MAX = 0.15`, `WIND_MARKETS` (passing attempts, completions,
    yards).
  - `excess_wind(roof, wind) -> float | None`, reusing `INDOOR_ROOFS` and
    `OUTDOOR_ROOFS` from `app/core/nfl_game_context.py`. A NULL or unrecognized
    roof is None, as 24e treats it as unknown.
  - `wind_adjustment_pct(market, excess, slopes) -> float | None`, in
    percentage points, rounded like `opponent_adjustment_pct`.
  - `wind_samples(games, market)`: per player-game with at least
    `MIN_BASELINE_GAMES` other games that season, `y = actual / loo_mean - 1`,
    `x = excess_wind`, weight `loo_mean`. Unknown-wind games are skipped as
    samples but still count in the leave-one-out mean, which is the baseline
    production would have used.
  - `fit_wind_slope(samples)`: weighted least squares with an intercept,
    player-clustered SE, the same math as `fit_environment_slopes` with one
    regressor. Kept only when at least 2 SE from zero, otherwise 0. If sharing
    code with `fit_environment_slopes` is cleaner, generalize it to k
    regressors and prove the 27e fit output is unchanged.

  *Done when:* unit tests cover:
  - indoor, open, outdoors, unknown roof, and unknown wind
  - 10 mph gives 0, 20 mph gives 1.0
  - the sign of the slope and the +/-15% cap
  - a synthetic fit that recovers a known slope, and one zeroed for a large SE
  - unknown-wind games skipped as samples but kept in the LOO mean
- [x] **Step 3 - Fit on 2024 and freeze.** `python -m app.backtest.nfl_wind_fit
  [--season 2024]` prints, per market: n, players, the count of samples with
  excess wind above 0, the slope with SE, and the kept value. The kept values
  go into `WIND_SLOPES: dict[NflPropMarket, float]` in `app/core/nfl_wind.py`,
  with the fit date and season in a comment.

  *Done when:*
  - The 2024 CLI output and the frozen constants are recorded under Results
    **before** Step 5 runs.
  - If all three slopes are zeroed, Steps 4 and 5 still run (the arm then
    equals production and the verdict is a formal reject), so the record is
    complete. Say so under Results.
- [x] **Step 4 - Wiring and the `wind` arm.**
  - `NflProjectionInput` gains `wind_adjustment_pct: float | None = None`.
    `model_projection` applies it last, after every existing step. The default
    keeps today's output.
  - `apply_wind(row, markets) -> dict` (core) sets `wind_adjustment_pct` on
    rows whose market is in `markets`, from `row["game_weather"]`. `_slate_line`
    passes it through.
  - `ARMS["wind"]` is `_production`, then `apply_wind` for `WIND_MARKETS`. The
    default `--arms` becomes `production,wind`.

  *Done when:*
  - A harness test shows a 25 mph outdoor passing-yards row reduced by the
    frozen slope, and a dome row, an unknown-wind row and a receiving row
    unchanged.
  - Anytime TD is unchanged.
  - `/nfl/slate` JSON for 2026 weeks 2 and 3 is identical before and after,
    with lines sorted by `line_id` (the tie-order caveat from 27e).
  - `pytest` passes.
- [x] **Step 5 - Score it on 2025.** Run `python -m app.backtest.nfl_projections`
  once with the default arms.

  *Done when:*
  - The run completes for weeks 1-18.
  - Results holds the paired table and verdict per market, the unpaired
    counts, and, as context only, the same table restricted to cases with
    excess wind above 0.
  - Results notes that this is the **seventh use of the 2025 holdout**.
  - If no market is `adopt`, Step 6 is marked skipped with the reason and the
    feature goes to `/complete` as "not adopted".
- [x] **Step 6 - Live use (conditional, needs a separate yes).** *Skipped:*
  no market passed in Step 5, so production, P(over) and 27j are unchanged.
  The spec as written: Only when a
  market passed. Before building, show the user the cost and ask:
  - bumping `NFL_PROJECTION_MODEL_VERSION` to `...-v5` hides P(over) until
    `python -m app.backtest.nfl_over_probability_fit --write` is re-run against
    the new version, and
  - it restarts 27j's verdict sample, delaying 27h.

  If approved, rewrite this step in detail first (as 27e did). Rules fixed now:
  - the slate reads the newest stored forecast from `get_slate_weather`,
    `wind_mph` only
  - `outdoor` venues only; `dome` and `retractable` get no adjustment, because
    a forecast cannot tell whether the roof will close
  - no forecast means no adjustment
  - 27i's `feature_snapshot` records the wind used

  *Done when:* defined in the rewrite.

## Files / areas

- `api/app/repositories/nfl.py` - roof and wind on replay rows and fit games.
- `api/app/core/nfl_game_environment.py` - two optional fields on
  `NflEnvironmentGame` (and, if shared, the generalized fit).
- `api/app/core/nfl_wind.py` (new) - the math, transform, samples, fit and
  frozen slopes.
- `api/app/core/nfl_projection.py` - `wind_adjustment_pct` on the input and in
  `model_projection`.
- `api/app/services/nfl/slate.py` - pass `wind_adjustment_pct` through.
- `api/app/backtest/nfl_projections.py` - the arm and default arms.
- `api/app/backtest/nfl_wind_fit.py` (new) - the 2024 fit CLI.
- Tests: `test_nfl_repository.py`, `test_nfl_wind.py` (new),
  `test_nfl_projection_harness.py`, and `test_nfl_game_environment.py` if the
  fit is generalized.

## Data / contracts

No schema change. `nfl_games.roof` and `wind` (observed, 24e and 19n) are
filled for 2024 and 2025 completed games. `nfl_game_weather_snapshots.wind_mph`
is the live forecast.

```python
# app/core/nfl_wind.py
WIND_THRESHOLD_MPH = 10        # pre-registered 2026-09-26
WIND_SCALE_MPH = 10.0
WIND_ADJUSTMENT_MAX = 0.15
WIND_MARKETS = frozenset({PASSING_ATTEMPTS, PASSING_COMPLETIONS, PASSING_YARDS})
WIND_SLOPES: dict[NflPropMarket, float]   # frozen 2024 fit, Step 3
```

**Load-bearing:**
- **Row keys:** `game_weather: {"roof": str | None, "wind": int | None}` on
  replay rows (observed); Step 6 would fill the same key from the forecast.
  `wind_adjustment_pct: float | None` on any row.
- **Transform order:** `apply_team_game_dvp`, `apply_season_blend`, then
  `apply_wind`. The adjustment is applied last in `model_projection`.
- **The rule is 27b's, unchanged:** per market, at least 300 paired cases, MAE
  at least 1.0% lower, and the paired difference below zero by more than 2 SE,
  over **all** paired passing cases, not only windy ones.

## Testing

- The test gate is on:
  - Step 1 ships a repository test and the unchanged 27e fit output.
  - Step 2 ships unit tests.
  - Step 4 ships a harness test and the unchanged-slate check.
  - Step 6, if it runs, ships its own slate tests.
- Steps 3 and 5 are local-database runs with the output recorded under Results.
- Run with `cd api && .venv\Scripts\python.exe -m pytest`.

## Results

### Step 3 - the 2024 fit

Run 2026-09-26, `python -m app.backtest.nfl_wind_fit --season 2024`, before
any 2025 score. 5,864 player-games: 2,008 indoor, 852 windy outdoors, 101
with wind unknown.

**Only passing yards is kept.** Attempts and completions sit under 1 SE and
are zeroed.

| Market | n | Players | Windy | Slope (SE) | Kept |
|---|---|---|---|---|---|
| passing attempts | 589 | 52 | 87 | -0.083 (0.088) | 0 |
| passing completions | 589 | 52 | 87 | -0.081 (0.079) | 0 |
| passing yards | 589 | 52 | 87 | -0.245 (0.078), 3.1 SE | **-0.245** |

**Against the directions written before the fit:** all three signs match
(negative). Yards falls about three times as fast as attempts or
completions, so wind mostly costs yards per throw, not throws.

**What the 2025 arm therefore tests:** passing yards only, cut 2.45% per mph
above 10. The 15% cap binds from about 16 mph. Attempts and completions have
zero slopes, so their arm equals production and they are formal rejects.
The frozen values are `WIND_SLOPES` in `app/core/nfl_wind.py`.

```
NFL wind fit, 2024 REG
player-games: 5864 total, 2008 indoor, 852 windy outdoors, 101 wind unknown
x = max(0, wind - 10) / 10 mph outdoors, 0 indoors; kept only when at least 2 player-clustered SE from zero.
  market                      n players  windy    slope      SE     keep
  passing_attempts          589      52     87   -0.083   0.088   +0.000
  passing_completions       589      52     87   -0.081   0.079   +0.000
  passing_yards             589      52     87   -0.245   0.078   -0.245
```

### Step 5 - the 2025 score

Run 2026-09-26 on 2025 REG weeks 1-18: `production` against `wind`, one pass
that also produced the windy-only context table. **This is the seventh use of
the 2025 holdout,** after F-02, 27c, 27d, 27e, 27f (projection verdicts) and
27g (a display fit).

**Verdict: rejected in every market. Wind is not adopted.**

| Market | Paired n | MAE change | Diff / SE | Verdict |
|---|---|---|---|---|
| passing yards | 582 | -0.73% | -0.495 / 0.331 (1.5 SE) | reject |
| passing attempts | 582 | 0.00% | zero slope | reject |
| passing completions | 582 | 0.00% | zero slope | reject |

Every other market is untouched by the arm (0.00%, formal reject).

**Reading it:**
- **Passing yards moves the right way but misses both bars:** 0.73% against
  1.0%, and 1.5 SE against 2.
- **Windy games alone (context only, never a verdict):** 88 QB-games, MAE
  63.19 to 59.91 (-5.2%, 1.5 SE). The effect looks real where it applies, but
  only 88 of 582 QB-games (15%) had wind above 10 mph, so it cannot move the
  whole market's accuracy by 1%. This is the dilution the Notes anticipated.
- **Bias:** passing-yards bias falls from +2.72 to -0.10, and `share_below`
  from 50.3% to 49.0%. The arm removes the remaining OVER lean, but the rule
  judges MAE.
- **The scored set is identical:** 20,081 paired cases, none unpaired.

```
Variant wind against production, paired on player, game and market
  market                      n  prod MAE   var MAE   change     diff      SE  verdict
  fantasy_points           5371     4.603     4.603   +0.00%   +0.000   0.000  reject
  passing_attempts          582     8.155     8.155   +0.00%   +0.000   0.000  reject
  passing_completions       582     5.522     5.522   +0.00%   +0.000   0.000  reject
  passing_yards             582    67.442    66.947   -0.73%   -0.495   0.331  reject
  receiving_yards          4803    16.384    16.384   +0.00%   +0.000   0.000  reject
  receptions               4803     1.270     1.270   +0.00%   +0.000   0.000  reject
  rushing_attempts         1395     3.499     3.499   +0.00%   +0.000   0.000  reject
  rushing_yards            1963    17.655    17.655   +0.00%   +0.000   0.000  reject

Unpaired: production-only 0, wind-only 0, paired 20081

Context only: cases with excess wind above 0
  market                      n  prod MAE   var MAE   change     diff      SE  verdict
  passing_attempts           88     7.639     7.639   +0.00%   +0.000   0.000  insufficient
  passing_completions        88     5.190     5.190   +0.00%   +0.000   0.000  insufficient
  passing_yards              88    63.187    59.911   -5.18%   -3.275   2.177  insufficient
```

The rule is final for this variant. Do not retune the threshold, scale, or
cap, or rescore on the windy subset: the post-hoc windy read is recorded here
only.

## Notes for the AI

- **Pre-registered here, 2026-09-26, before any fit or score:** the 10 mph
  threshold, the /10 scale, the +/-15% cap, the absolute form, the three
  markets, the leave-one-out WLS fit on 2024 with the 2 SE zeroing rule, and
  the Step 6 live rules. Do not adjust any of them after Step 3 or Step 5.
- **Expected directions, written before the fit:** negative for passing yards
  and completions (wind shortens and spoils throws), smaller and possibly
  negative for attempts (teams run more). Record any fitted sign that
  disagrees; it stands.
- **Why absolute, not relative to the baseline.** Excess wind is 0 in most
  games, so a player's baseline average is near 0 and subtracting it adds
  noise and a baseline query change (and a season-blend change) for little
  gain. The small cost: a QB with many windy home games has a slightly
  deflated baseline, so the adjustment slightly double-counts for him. The fit
  uses the same absolute form, so the slope absorbs that on average.
- **The dilution is real and accepted.** Most paired cases have zero excess
  wind and identical projections, so a strong effect in windy games may still
  miss the 1.0% MAE bar over all passing cases. That is the honest test of
  whether wind moves the whole market's accuracy. The windy-only table is
  context, never a verdict.
- **Observed, not forecast.** NFLverse `wind` is what happened at the game, so
  the backtest sees better weather information than a pre-game projection.
  Any gain is an upper bound. A live adoption is confirmed forward by 27a's
  line grading and 27j.
- **Retractable roofs differ between backtest and live.** The backtest knows
  the actual roof state (`open` counts as outdoor); live cannot, so Step 6
  gives retractable venues no adjustment. Live is therefore slightly more
  conservative than what was scored.
- **Seventh use of the 2025 holdout** (F-02, 27c, 27d, 27e, 27f for
  projections, 27g for a display fit). Three markets are judged. Treat a pass
  near 2 SE with caution.
- **27e's warning applies.** 52 QBs in 2024 could not show the trailing-throws
  margin effect. Wind varies far more within a QB's season than implied margin
  does, which is why this is worth one test, but a zeroed fit is a live outcome.
- **Anytime TD** never goes through `apply_wind`. Assert it in tests.
- **Reuse:** `INDOOR_ROOFS` and `OUTDOOR_ROOFS` from `nfl_game_context.py`,
  `fit_environment_slopes`' math, `MIN_BASELINE_GAMES`, the 27b metrics and
  `adoption_verdict`, and `get_slate_weather` for Step 6. Numpy is available;
  add no dependency.
- Standards: `X | None`, no `Any`, no em dashes, comment only the why,
  repositories own SQL, and `app/core` stays pure.
