# Feature: Game environment

**From build-plan:** feature 27e
**Status:** complete (moneyline scaling dropped for the three passing markets; game environment not adopted)

## Goal

Replace the NFL prop model's moneyline scaling with a game-environment
adjustment built from the implied team total and the expected margin, with a
separate direction and size per market. Fit that size on 2024, score it once
through the 27b harness on 2025 (stacked on production, which includes 27c and
27d), and adopt it only for markets that pass the pre-registered rule.

**What is wrong today** (`model_projection` in `app/core/nfl_projection.py`):
- **One direction for every market.** `projection *= 1 + clamp(p_win - 0.5, ±0.08)`
  raises every market for a favorite. That is the wrong sign for passing volume:
  a trailing team throws more, and a leading team runs more.
- **The moneyline says who wins, not how many points.** A 60% favorite in a
  38-point game and one in a 52-point game get the same bump.
- **It double-counts.** A player on a team that is favored every week already has
  that environment in his baseline, and the scaling adds it again.

**The variant.** Each team's implied total and expected margin come from the
game's spread and total:

    team_total      = (total + team_margin) / 2
    team_margin     = expected margin for the player's team (positive = favored)

Both are measured **against the player's own baseline games**, so only a
different-from-usual environment moves the projection:

    x_total  = team_total / baseline_team_total - 1
    x_margin = (team_margin - baseline_team_margin) / 7
    adjustment = clamp(b_total[market] * x_total + b_margin[market] * x_margin, ±0.15)

`baseline_team_total` and `baseline_team_margin` are averages over the same
games the baseline averages (closing lines from `nfl_games`). `b_total` and
`b_margin` are per-market slopes from a frozen 2024 fit (Step 3), never fitted
to 2025.

## Design reference

None. Backend and CLI only, plus one routine flag on the web if adopted
(Step 7).

## In scope

- **Environment on slate and replay rows.** Each baseline season carries the
  mean implied team total and margin of its games. Replay rows carry the game's
  closing spread and total. No behavior change.
- **A pure module,** `app/core/nfl_game_environment.py`: team lines from spread
  and total, the adjustment, the row transform, and the 2024 fit.
- **The season blend carries environment,** so a 27d-blended baseline is
  compared against its blended environment.
- **A 2024 fit CLI** that prints the slopes, then freezes them as constants.
- **A `game_environment` harness arm,** stacked on production.
- **One scored run on 2025,** with the verdict for each market under Results.
- **Conditional adoption** (Steps 6 and 7): only markets with an `adopt` verdict
  switch from moneyline scaling to the environment on `/nfl/slate`, with a model
  version bump. If none pass, Steps 6 and 7 are skipped, the result is recorded,
  and production is unchanged.

## Out of scope

- **Anytime TD.** It has its own backtest and 19n already rejected scoring
  environment for it. It keeps its current path, which ignores the moneyline.
- **Retuning** the cap, the `/7` margin scale, the slope-zeroing rule, or trying
  a second variant (for example, moneyline removed with no replacement). Each
  extra arm spends the 2025 holdout again.
- **Showing the adjustment** as a number on the board or evidence panel. The
  flag is enough until 27g gives it a display.
- **Weather, roof, pace, team efficiency.** 24c and 24e rejected them for game
  lines, and they are not in this item.
- Fantasy scoring (27f), P(over) (27g), and ranking (27h).

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

- [x] **Step 1 - Environment on rows (no behavior change).** In
  `app/repositories/nfl.py`:
  - `_BASELINES_CTE` adds, over the player's baseline games that have both
    closing lines:
    - `environment_games`
    - `team_total`: `AVG((g.total_line + m) / 2)`
    - `team_margin`: `AVG(m)`

    Here `m` is `g.spread_line` when `s.team_id = g.home_team_id`, and
    `-g.spread_line` otherwise.
  - Each `baseline_seasons` entry gains `environment`
    (`{"games", "team_total", "team_margin"}`, or None with zero games). The
    selected season's value is copied to `row["environment"]`, the same way as
    `averages`.
  - `get_replay_rows` attaches `row["game_lines"] = {"home_spread_margin",
    "total"}`: the game's closing `spread_line` and `total_line`, or None if
    either is missing.

  *Done when:*
  - A repository test shows a two-season line whose `environment` differs by
    season, and whose selected `environment` matches the chosen season.
  - `/nfl/slate` JSON for weeks 2 and 3 of 2026 is byte-identical before and
    after (SHA-256), as in 27b and 27d.
  - `pytest` passes.

  *Built:* **the raw SHA-256 differed, but only in the order of tied lines.**
  - The slate query orders by `p.name, l.market, l.line, b.season`, with no
    unique tiebreaker, so adding columns changed the plan and reordered lines
    tied on player, market and line.
  - With each game's lines sorted by `line_id`, weeks 2 and 3 are identical to
    master.
  - The missing tiebreaker predates this feature and is left for a separate
    `/fix`.
- [x] **Step 2 - Pure environment math.** Add `app/core/nfl_game_environment.py`:
  - `ENVIRONMENT_ADJUSTMENT_MAX = 0.15`, `MARGIN_SCALE_POINTS = 7.0`
  - `team_lines(home_spread_margin, total, is_home) -> (team_total, team_margin)`
  - `environment_adjustment_pct(market, team_total, team_margin, environment,
    coefficients) -> float | None`: the formula above, in percentage points,
    rounded like `opponent_adjustment_pct`. None when any input is missing or
    the baseline team total is not positive.
  - `NflEnvironmentSlopes(total: float, margin: float)`, with coefficients as a
    `dict[NflPropMarket, NflEnvironmentSlopes]`, empty until Step 3.

  In `app/core/nfl_season_blend.py`, `season_blend_inputs` also blends
  `environment` with the same `g_cur` and `w * g_prev` weights, on
  `environment_games`. A missing side is handled the way `blend_usage` does it.

  *Done when:* unit tests cover:
  - a home favorite and an away underdog from the same game (margins mirror,
    team totals sum to the total)
  - a zero adjustment when the game matches the baseline environment
  - the sign per slope
  - the ±15% cap
  - None for missing lines, missing environment, or a zero baseline total
  - blended environment weights, and the one-side-missing cases
- [x] **Step 3 - Fit on 2024 and freeze.** A pure `fit_environment_slopes(samples)`
  in the core module, plus `python -m app.backtest.nfl_game_environment_fit
  [--season 2024]`, backed by a repository query for the season's REG
  player-games with the player's team and the closing lines.
  - **Samples:** per market in `REPLAY_MARKETS_BY_POSITION`, per player-game
    where the player has at least 4 other games that season with lines.
    - `y = actual / loo_mean - 1`
    - `x_total` and `x_margin` computed against the same leave-one-out games'
      mean environment
    - weight `loo_mean`, which keeps near-zero means from dominating; rows with
      `loo_mean <= 0` are skipped
  - **Fit:** weighted least squares with an intercept (the intercept absorbs
    skew and is discarded). A slope is kept only when it is at least 2 SE from
    zero, otherwise set to 0.
  - **SE type,** fixed at build time before the fit ran: the SE is clustered by
    player. A player's leave-one-out samples share games, so per-sample SEs
    would overstate the evidence and keep noisy slopes.
  - The CLI prints n, both slopes with SE, and the kept values per market.
    Those values go into `GAME_ENVIRONMENT_SLOPES` in the core module, with the
    fit date and season in a comment.

  *Done when:*
  - A unit test recovers known slopes from synthetic samples, and zeroes a slope
    whose SE is too large.
  - The 2024 CLI output and the frozen constants are recorded under Results
    **before** Step 5 runs.
- [x] **Step 4 - Wiring and the `game_environment` arm.**
  - `NflProjectionInput` gains `uses_game_environment: bool = False` and
    `environment_adjustment_pct: float | None = None`. With
    `uses_game_environment`, `model_projection` skips moneyline scaling and
    applies the environment adjustment when it is not None. The defaults keep
    today's output.
  - `apply_game_environment(row, markets) -> dict` (core) sets both keys on
    rows whose market is in `markets` (never anytime TD). `_slate_line` reads
    them from the row.
  - `ARMS["game_environment"]` is production's transform, then
    `apply_game_environment` for every non-TD market. The default `--arms`
    becomes `production,game_environment`.

  *Done when:*
  - A harness test shows a favorite's passing-attempts row losing its moneyline
    bump and taking the environment adjustment.
  - A row without game lines in the arm gets neither adjustment.
  - Anytime TD is unchanged.
  - A 27d-blended passing row is compared against its blended environment.
  - `pytest` is green.
- [x] **Step 5 - Score it on 2025.** Run `python -m app.backtest.nfl_projections`
  once with the default arms.

  *Done when:*
  - The run completes for weeks 1-18.
  - Results holds the paired table, the verdict per market, the per-phase read
    (weeks 1-4, 5-10, 11-18, computed once from the cases' `week`), and the
    unpaired counts.
  - Results notes that this is the **fourth use of the 2025 holdout** (after
    F-02, 27c, and 27d).
  - If no market is `adopt`, Steps 6 and 7 are marked skipped with the reason,
    and the feature goes to `/complete` as "not adopted".
- [x] **Step 6 - Drop moneyline scaling for the adopted markets.** *(Rewritten
  2026-09-26 after Step 5, with the user's approval.)* The three adopted
  markets have zero environment slopes, so what passed is "no moneyline
  scaling", not an environment adjustment. Adopting the environment path as
  first specced would need a live spread/total loader and a
  `game_environment_adjusted` flag for an adjustment that is always 0. Missing
  or stale lines would also lower Trust for an input that is never used. The
  projection is the same either way, so:
  - `MONEYLINE_UNSCALED_MARKETS` in `app/core/nfl_projection.py`: passing
    attempts, completions and yards.
  - `NflProjectionInput` gains `moneyline_scaled: bool = True`, and
    `_slate_line` sets it to False for those markets. `model_projection` skips
    the moneyline bump, and `model_quality_flags` omits `market_missing` and
    `market_stale` (the line uses no market input).
  - The harness `production` arm picks this up through `_slate_line`, with no
    transform, so it keeps measuring what is served.
  - Bump `NFL_PROJECTION_MODEL_VERSION` to
    `opponent-dvp-tg-blend-usage-snap-v4`.
  - `apply_game_environment`, the fit, and `GAME_ENVIRONMENT_SLOPES` stay as the
    record and as the arm, but production does not call them.

  *Done when:*
  - A slate test shows a passing line unchanged by a 75% moneyline and free of
    market flags, and a receiving line still scaled and flagged `market_stale`
    when stale.
  - Re-running the harness `production` arm reproduces Step 5's
    `game_environment` MAE for the three passing markets and production's for
    the rest.
  - `/nfl/slate` for 2026 week 3 returns 200 with the new version.
- [x] **Step 7 - Web flag.** *Skipped:* Step 6 adds no flag, so the web needs no
  change.

## Files / areas

- `api/app/repositories/nfl.py` - environment aggregates, replay `game_lines`,
  and the 2024 fit query.
- `api/app/core/nfl_game_environment.py` (new) - the math, the transform, and
  the fit.
- `api/app/core/nfl_season_blend.py` - blend `environment`.
- `api/app/core/nfl_projection.py` - input fields, the `model_projection`
  branch, `MONEYLINE_UNSCALED_MARKETS`, the market flags, and the version.
- `api/app/services/nfl/slate.py` - pass the row keys and `moneyline_scaled`
  through.
- `api/app/backtest/nfl_projections.py` - the arm and the default arms.
- `api/app/backtest/nfl_game_environment_fit.py` (new) - the 2024 fit CLI.
- Tests:
  - `test_nfl_repository.py`
  - `test_nfl_game_environment.py` (new)
  - `test_nfl_season_blend.py`
  - `test_nfl_projection_harness.py`
  - `test_nfl_projection.py` (the moneyline drop and its flags)

## Data / contracts

No schema change. Closing `spread_line` and `total_line` cover all 272 REG games
in 2024 and 2025, and completed 2026 games.

```python
# app/core/nfl_game_environment.py
ENVIRONMENT_ADJUSTMENT_MAX = 0.15   # pre-registered 2026-09-26
MARGIN_SCALE_POINTS = 7.0           # one touchdown of expected margin

@dataclass(frozen=True)
class NflEnvironmentSlopes:
    total: float    # fractional change per unit x_total
    margin: float   # fractional change per 7 points of margin above baseline

GAME_ENVIRONMENT_SLOPES: dict[NflPropMarket, NflEnvironmentSlopes]  # frozen 2024 fit
```

**Load-bearing:**
- **Row keys:**
  - `environment` on each `baseline_seasons` entry and on the row:
    `{"games": int, "team_total": float, "team_margin": float} | None`
  - `game_lines`: `{"home_spread_margin": float, "total": float} | None`,
    NFLverse sign (positive = home favored)
  - `uses_game_environment` and `environment_adjustment_pct`

  27f arms read the same row.
- **Transform order is fixed:** `apply_team_game_dvp`, then
  `apply_season_blend`, then `apply_game_environment`.
- **Sign conventions:** the book stores the home spread as negative when the home
  team is favored, and NFLverse stores `spread_line` as positive when the home
  team is favored. `game_lines` always uses the NFLverse sign.

**The rule is 27b's, unchanged:** at least 300 paired cases, MAE at least 1.0%
lower, and the paired difference below zero by more than two standard errors,
per market.

## Testing

- The test gate is on:
  - Step 1 ships a repository test and a byte-identical slate check.
  - Steps 2 and 3 ship unit tests.
  - Step 4 ships a harness test.
  - Step 6, if it runs, ships a slate test.
  - Step 7 ships an `nflSignal` test, a build, and a screenshot.
- Run with `cd api && .venv\Scripts\python.exe -m pytest`.

## Results

### Step 3 - the 2024 fit

Run 2026-09-26, `python -m app.backtest.nfl_game_environment_fit --season 2024`,
before any 2025 score. 5,864 player-games had closing lines.

**Only the rushing margin slopes are kept.** Every other slope sits under 2
player-clustered SE and is zeroed.

| Market | n | Players | Total slope (SE) | Margin slope (SE) | Kept |
|---|---|---|---|---|---|
| passing yards | 601 | 52 | -0.142 (0.295) | +0.004 (0.038) | 0, 0 |
| passing attempts | 601 | 52 | -0.079 (0.270) | -0.025 (0.036) | 0, 0 |
| passing completions | 601 | 52 | -0.173 (0.295) | -0.003 (0.037) | 0, 0 |
| rushing yards | 2,004 | 159 | -0.254 (0.301) | +0.127 (0.041) | 0, **+0.127** |
| rushing attempts | 1,422 | 108 | -0.446 (0.280) | +0.120 (0.038) | 0, **+0.120** |
| receiving yards | 4,792 | 380 | +0.160 (0.204) | -0.038 (0.030) | 0, 0 |
| receptions | 4,802 | 382 | +0.112 (0.173) | -0.042 (0.026) | 0, 0 |
| fantasy points | 5,452 | 439 | +0.127 (0.162) | +0.008 (0.024) | 0, 0 |

**Against the directions written before the fit:**
- **Rushing matches.** A team favored by a touchdown more than usual runs about
  12% more.
- **Passing margin has the expected sign for attempts only** (-0.025), and is
  far from significant. The "trailing throws" effect is real in the NFL, but
  within one QB's season the margin varies too little for 52 QBs to show it.
- **Team total does not show up anywhere.** Within a player's season, the
  implied total varies little, so its SEs are wide (0.16 to 0.30). The passing
  and rushing total slopes even point negative.

**What the 2025 arm therefore tests:** six markets lose moneyline scaling with
nothing in its place, and the two rushing markets swap it for a margin slope.
Both are valid "replace" tests, as the Notes anticipated. The frozen values are
`GAME_ENVIRONMENT_SLOPES` in `app/core/nfl_game_environment.py`.

### Step 5 - the 2025 score

Run 2026-09-26 on 2025 REG weeks 1-18: `production` (with 27c and 27d) against
`game_environment`, in 3 min 33 s. **This is the fourth use of the 2025
holdout,** after F-02 (27b), 27c and 27d.

**Verdict: the three passing markets adopt, and every other market is
rejected.** The passing slopes were zeroed in Step 3, so **the passing gain comes
entirely from removing moneyline scaling.** The two rushing markets carry the
only fitted environment slopes, and both are rejected.

| Market | Paired n | MAE change | Diff / SE | Verdict |
|---|---|---|---|---|
| passing attempts | 582 | -5.92% | -0.513 / 0.084 (6.1 SE) | adopt |
| passing completions | 582 | -4.02% | -0.231 / 0.056 (4.1 SE) | adopt |
| passing yards | 582 | -1.86% | -1.275 / 0.619 (2.06 SE) | adopt, barely |
| receptions | 4,803 | -0.75% | -0.009 / 0.003 (3.0 SE) | reject, under 1% |
| fantasy points | 5,371 | -0.59% | -0.027 / 0.010 (2.7 SE) | reject, under 1% |
| receiving yards | 4,803 | -0.39% | -0.065 / 0.034 | reject |
| rushing yards | 1,963 | +0.16% | +0.028 / 0.054 | reject |
| rushing attempts | 1,395 | +0.43% | +0.015 / 0.016 | reject |

**Reading it:**
- **The moneyline bump was wrong for passing, as the 27a review suspected.**
  Production raised a favorite's passing volume by up to 8%, but favorites throw
  less once ahead. Passing-yards bias falls from +4.64 to +2.72, and
  `share_below` from 53.1% to 50.3%.
- **Passing gains hold in every phase** for attempts (-4.7%, -8.0%, -5.2%) and
  completions (-2.9%, -4.9%, -4.0%). Yards gain only in weeks 11-18 (-3.7%),
  and weeks 1-4 are slightly worse (+0.8%, well within noise).
- **Receiving, receptions and fantasy improve too, but by under 1%.**
  Receptions (3.0 SE) and fantasy (2.7 SE) are real but small. For these
  markets the moneyline bump points roughly the right way, but not by enough to
  matter.
- **The rushing margin slope did not transfer from 2024.** Rushing attempts are
  slightly worse (+0.43%), and weeks 5-10 are the worst phase (+1.1%). The
  replaced moneyline bump already pointed the same way (favorites run more), so
  swapping one for the other gained nothing.
- **Multiple comparisons:** eight markets were judged on a fourth use. Attempts
  at 6.1 SE and completions at 4.1 SE are very unlikely to be chance. Yards at
  2.06 SE only just clears, but moves the same way and shares the same
  mechanism. 27a's forward line grading confirms.
- **The scored set is identical:** 20,081 paired cases, none unpaired.

```
Variant game_environment against production, paired on player, game and market
  market                      n  prod MAE   var MAE   change     diff      SE  verdict
  fantasy_points           5371     4.625     4.597   -0.59%   -0.027   0.010  reject
  passing_attempts          582     8.668     8.155   -5.92%   -0.513   0.084  adopt
  passing_completions       582     5.754     5.522   -4.02%   -0.231   0.056  adopt
  passing_yards             582    68.718    67.442   -1.86%   -1.275   0.619  adopt
  receiving_yards          4803    16.384    16.319   -0.39%   -0.065   0.034  reject
  receptions               4803     1.270     1.260   -0.75%   -0.009   0.003  reject
  rushing_attempts         1395     3.499     3.514   +0.43%   +0.015   0.016  reject
  rushing_yards            1963    17.655    17.683   +0.16%   +0.028   0.054  reject

Unpaired: production-only 0, environment-only 0, paired 20081

By phase (paired)
  market                phase              n     prod      env   change     diff      SE
  fantasy_points        weeks 1-4       1094    4.844    4.821   -0.47%   -0.023   0.023
  fantasy_points        weeks 5-10      1711    4.669    4.649   -0.42%   -0.020   0.018
  fantasy_points        weeks 11-18     2566    4.501    4.467   -0.77%   -0.035   0.014
  passing_attempts      weeks 1-4        129    8.567    8.160   -4.74%   -0.406   0.179
  passing_attempts      weeks 5-10       182    7.970    7.331   -8.01%   -0.639   0.145
  passing_attempts      weeks 11-18      271    9.185    8.705   -5.23%   -0.480   0.125
  passing_completions   weeks 1-4        129    5.553    5.392   -2.89%   -0.161   0.119
  passing_completions   weeks 5-10       182    5.408    5.140   -4.94%   -0.267   0.100
  passing_completions   weeks 11-18      271    6.082    5.841   -3.96%   -0.241   0.082
  passing_yards         weeks 1-4        129   67.629   68.180   +0.81%   +0.551   1.329
  passing_yards         weeks 5-10       182   65.291   64.751   -0.83%   -0.541   1.101
  passing_yards         weeks 11-18      271   71.537   68.899   -3.69%   -2.638   0.901
  receiving_yards       weeks 1-4        967   17.111   17.091   -0.11%   -0.020   0.080
  receiving_yards       weeks 5-10      1535   16.402   16.344   -0.35%   -0.057   0.060
  receiving_yards       weeks 11-18     2301   16.066   15.977   -0.55%   -0.089   0.048
  receptions            weeks 1-4        967    1.358    1.345   -0.99%   -0.013   0.007
  receptions            weeks 5-10      1535    1.263    1.259   -0.37%   -0.005   0.005
  receptions            weeks 11-18     2301    1.237    1.226   -0.89%   -0.011   0.004
  rushing_attempts      weeks 1-4        270    3.701    3.717   +0.44%   +0.016   0.038
  rushing_attempts      weeks 5-10       452    3.318    3.354   +1.09%   +0.036   0.026
  rushing_attempts      weeks 11-18      673    3.541    3.541   +0.00%   +0.000   0.022
  rushing_yards         weeks 1-4        397   19.298   19.198   -0.52%   -0.101   0.134
  rushing_yards         weeks 5-10       628   17.918   18.027   +0.60%   +0.108   0.092
  rushing_yards         weeks 11-18      938   16.784   16.812   +0.17%   +0.028   0.076
```

## Notes for the AI

- **Pre-registered here, 2026-09-26, before any fit or score:**
  - the relative-to-baseline form
  - the ±15% cap and the /7 margin scale
  - the leave-one-out WLS fit on 2024, with the 2 SE zeroing rule
  - fitting every non-TD market

  Do not adjust any of them after seeing Step 3 or Step 5.
- **Why relative to the baseline.** An absolute team total would double-count a
  good offense that already has high totals in its baseline. The fit uses the
  same relative form as production, or the slopes would not transfer.
- **Why 2024 and not 2025.** 2025 is the holdout; fitting there leaks. Weekly
  stats start in 2024, so 2024 is the only clean fit season. Early-2024 players
  with fewer than 4 other games drop out, which is fine for a fit.
- **Expected directions, written before the fit:**
  - `b_margin` negative for passing attempts and completions (trailing throws)
  - `b_margin` positive for rushing attempts
  - `b_total` positive for yardage, receptions, and fantasy

  Record any fitted sign that disagrees. It stands, since it is data, but it is
  worth a sentence.
- **Replay substitution is 27b's:** the replay uses closing lines where the slate
  uses the latest pre-kickoff book lines. Closing lines are slightly sharper, so
  the arm's gain is an upper bound for live use.
- **A zeroed market still changes.** If both slopes for a market are zeroed, the
  arm simply removes moneyline scaling for it. That is still a valid test of
  "replace".
- **No baseline environment** (for example, a rookie with no games that have
  lines): an adopted market gets no adjustment and no moneyline scaling, and
  Step 6 flags it `environment_baseline_missing`. That flag is not routine, so
  the line does not read Ready.
- **Anytime TD** never goes through `apply_game_environment`. Assert it in tests.
- **Reuse:** `moneyline_is_stale`, `get_slate_matchup_context`'s book preference,
  the 27b metrics and verdict, and `nfl_game_context.py`'s fit style for WLS.
  Numpy is available; do not add a dependency.
- Standards: `X | None`, no `Any`, no em dashes, comment only the why,
  repositories own SQL, and `app/core` stays pure.
