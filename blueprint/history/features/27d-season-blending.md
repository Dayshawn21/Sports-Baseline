# Feature: Season blending

**From build-plan:** feature 27d
**Status:** complete

## Goal

Replace the NFL prop baseline's four-game season switch with a games-weighted
blend of the current and previous season. Score it once through the 27b harness
on 2025, stacked on production (which already includes 27c's passing-completions
DVP), and adopt it only for markets that pass the pre-registered rule.

**What is wrong today** (`choose_baseline_season` in `app/core/nfl_baseline.py`,
applied in `_slate_line_rows`):
- **It is a switch, not a weight.** Until a player has 4 games in the line's
  season, the baseline is last season alone; from game 4 on, it is this season
  alone. Week 5's baseline throws away 17 games of last season for 4 of this one.
- **Early lines price on last season.** The 2026-09-25 review found about 95% of
  early-season lines on a previous-season baseline, which the stale flag then
  pushes down the rank.

**The variant:** per player, for every non-TD market,

    blended stat = (g_cur * cur + w * g_prev * prev) / (g_cur + w * g_prev)

where `g_cur` and `g_prev` are the games in the line's season and in the most
recent earlier season with games, and `w = PREVIOUS_SEASON_WEIGHT = 0.6`. So at
week 5 (4 current games against 17 previous) the current season carries 28%; by
week 12 (11 against 17) it carries 52%. The same weights blend the position
averages and the usage inputs, so every season-scoped input on the row describes
the same blend. `games` becomes `g_cur + g_prev` (raw, not weighted).

## Design reference

None. Backend and CLI only, plus one new baseline-reason label if adopted
(Step 6).

## In scope

- **Per-season inputs on slate rows.** `_slate_line_rows` keeps each season's
  averages, position averages and usage on the row (`baseline_seasons`) instead
  of discarding the unchosen ones. No behavior change.
- **A pure blend module,** `app/core/nfl_season_blend.py`: blend two seasons'
  averages and usage dicts, and a row transform.
- **A `season_blend` harness arm,** stacked on production.
- **One scored run on 2025,** with the per-market verdict under Results.
- **Conditional adoption** (Steps 5 and 6): only markets whose verdict is
  `adopt` switch to the blend on `/nfl/slate`, with a model version bump. If
  none pass, Steps 5 and 6 are skipped, the result is recorded, and nothing in
  production changes.

## Out of scope

- **Anytime TD.** It already blends up to three seasons (`TD_SEASON_WEIGHTS`)
  with its own log-loss backtest, and stays as is.
- **Retuning** `PREVIOUS_SEASON_WEIGHT`, a third season, recency weighting within
  a season, or a second variant. Each extra arm spends the 2025 holdout again.
- **Removing** `choose_baseline_season`. Anytime TD's label, failing markets and
  the stale-season flag still read it.
- **The stale-season rank tier.** Flags keep today's meaning (see Step 5), so a
  mostly-last-season blend still ranks below current-season edges.
- Game environment (27e), fantasy scoring (27f), P(over) (27g), ranking (27h).

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

- [x] **Step 1 - Keep every season on the row (no behavior change).** In
  `_slate_line_rows` (`app/repositories/nfl.py`), attach
  `baseline_seasons: dict[int, dict]` to each line: the existing per-season
  entries (`averages`, `position_averages`, `usage`, `position_usage`) that
  `seasons_by_line` already builds. The selected-season keys stay exactly as
  they are.

  *Done when:*
  - A test in `test_nfl_repository.py` shows a line with two season rows
    carrying both seasons under `baseline_seasons`, and the chosen season's
    values unchanged under `averages`.
  - `/nfl/slate` weeks 2 and 3 JSON is byte-identical before and after
    (SHA-256), as in 27b's Step 1.
  - `pytest` passes.
- [x] **Step 2 - Pure season blend.** Add `app/core/nfl_season_blend.py`:
  - `PREVIOUS_SEASON_WEIGHT = 0.6`
  - `blend_averages(current, previous, weight) -> dict`: the formula above per
    stat, in the `_averages` shape, `games` = raw sum. `fantasy_points` blends
    only the seasons where it is not None, and is None when both are.
  - `blend_usage(current, previous, weight) -> dict | None`: the same weighting
    on `usage_games`; None when both are None; the one present when only one is.
  - `season_blend_inputs(baseline_seasons, line_season) -> dict | None`: picks
    the line's season and the most recent earlier season with games, and returns
    blended `averages`, `position_averages`, `usage`, `position_usage`. None
    unless both exist, so the row keeps the chooser's pick. *(Changed in Step 5:
    the draft said "that season alone" for one season, which would pick a thin
    last season over a full one before it. The 2025 holdout never has a third
    season, so Step 4's numbers are unaffected, and Step 5's reproduction
    confirms it.)*
  - `apply_season_blend(row, line_season) -> dict`: the row with those four keys
    swapped in for `SEASON_BLEND_MARKETS` (empty until Step 5), never anytime TD.

  *Done when:* unit tests cover:
  - the week-5 case (4 current, 17 previous) giving 28% current weight
  - `games` is the raw sum
  - current-only (rookie) and previous-only (week 1) inputs return that season
  - a later-than-line season is ignored, and a gap year picks the most recent
    earlier season
  - fantasy None handling, usage None handling
  - anytime TD passes through unchanged
- [x] **Step 3 - The `season_blend` arm.** In `app/backtest/nfl_projections.py`,
  `ARMS` gains `season_blend`: production's transform, then the Step 2 blend for
  every non-TD market (not only `SEASON_BLEND_MARKETS`). The default `--arms`
  becomes `production,season_blend`; `usage_off` and `dvp_team_game` stay
  selectable.

  *Done when:*
  - A harness test runs a synthetic two-season row through both arms and shows
    the projection moving from the chosen season's value to the blend, with
    `games_in_sample` equal to the raw sum.
  - A passing-completions row keeps its team-game DVP in both arms (the blend
    stacks on 27c, it does not undo it).
  - `pytest` is green.
- [x] **Step 4 - Score it on 2025.** Run `python -m app.backtest.nfl_projections`
  once with the default arms.

  *Done when:*
  - The run completes for weeks 1-18.
  - Results holds the paired table, the verdict per market, a per-week-range
    read (weeks 1-4, 5-10, 11-18), computed once from the cases' `week` rather
    than added as a harness option, and a
    note that this is the third use of the 2025 holdout (after F-02 and 27c).
  - If no market is `adopt`, Steps 5 and 6 are marked skipped with the reason,
    and the feature goes to `/complete` as "not adopted".
- [x] **Step 5 - Adopt in the slate (only if Step 4 adopts a market).**
  - `SEASON_BLEND_MARKETS` in `app/core/nfl_projection.py`: exactly the adopted
    markets, never `anytime_touchdown`.
  - `build_slate` and the harness's `production` arm both call
    `apply_season_blend` after `apply_team_game_dvp`, so the harness keeps
    measuring what is served.
  - Blended lines report `baseline_reason = "current_previous_blend"` (new
    constant in `nfl_baseline.py`), `baseline_season` = the chooser's season,
    `games_in_sample` = the raw sum.
  - **Flags keep today's meaning:** `stale_baseline_season` and
    `partial_season_baseline` read the chooser's season and the current-season
    game count (carried on the row as `current_season_games`), so rank tiers
    do not change; `small_sample` reads the blended games.
  - Bump `NFL_PROJECTION_MODEL_VERSION` (to
    `opponent-dvp-tg-blend-usage-snap-v3`).

  *Done when:*
  - A slate test shows an adopted market reading the blend with the new reason,
    a non-adopted market and anytime TD reading the chosen season, and the
    stale flag on a 2-current-game line in both.
  - Re-running the harness's `production` arm reproduces Step 4's
    `season_blend` MAE for adopted markets and production's for the rest.
  - `/nfl/slate` for 2026 week 3 returns 200 with the new version string.
- [x] **Step 6 - Baseline label (only if Step 5 ran).** Add
  `current_previous_blend` to `BASELINE_REASON_LABELS` in
  `web/src/utils/nflLabels.ts` ("This season and last, weighted by games, last
  season counted at 0.6"), and to the reason list in the `web/src/types/nfl.ts`
  comment.

  *Done when:* `npm run build` and `npm run test` pass, and a screenshot of an
  adopted-market line shows the new label.

  *Built:* build and tests pass. **No screenshot is possible:**
  `BASELINE_REASON_LABELS` has not been rendered since the 2026-09-17 prop-board
  redesign (`dade9cb` removed its tooltip), so no page shows any baseline
  reason. The entry keeps the map complete; showing reasons again would be a
  separate `/fix`.

## Files / areas

- `api/app/repositories/nfl.py` - `baseline_seasons` on slate and replay rows.
- `api/app/core/nfl_season_blend.py` (new) - the blend and row transform.
- `api/app/backtest/nfl_projections.py` - the `season_blend` arm and default arms.
- If adopted: `api/app/core/nfl_projection.py`, `api/app/core/nfl_baseline.py`,
  `api/app/services/nfl/slate.py`, `web/src/utils/nflLabels.ts`,
  `web/src/types/nfl.ts`.
- Tests:
  - `test_nfl_repository.py` (per-season row)
  - `test_nfl_season_blend.py` (new)
  - `test_nfl_projection_harness.py` (the arm)
  - if adopted, a slate test for the market split and flags

## Data / contracts

No schema change.

```python
# app/core/nfl_season_blend.py
# Last season counts at the same discount anytime TD already gives it
# (TD_SEASON_WEIGHTS[1]); fixed before scoring, not fitted to 2025.
PREVIOUS_SEASON_WEIGHT = 0.6
```

**Load-bearing:**
- Slate and replay rows gain `baseline_seasons: dict[int, {"averages",
  "position_averages", "usage", "position_usage"}]`. 27e and 27f arms stack on an
  adopted 27d and read the same row.
- The blended dicts keep the `_averages` and `_usage` shapes, so `_slate_line`,
  `model_projection` and `usage_adjustment_pct` need no change.
- Transform order is fixed: `apply_team_game_dvp`, then `apply_season_blend`.
  They touch disjoint keys (opponent and league versus player-season inputs).

**The rule is 27b's, unchanged:** at least 300 paired cases, MAE at least 1.0%
lower, and the paired difference below zero by more than two standard errors,
per market.

## Testing

- The test gate is on:
  - Step 1 ships a repository test and a byte-identical slate check.
  - Step 2 ships unit tests.
  - Step 3 ships a harness test.
  - Step 5, if it runs, ships a slate test.
  - Step 6 rides on build, tests and a screenshot.
- Run with `cd api && .venv\Scripts\python.exe -m pytest`.

## Results

Run 2026-09-26 on 2025 REG weeks 1-18, `production` (which includes 27c's
passing-completions DVP) against `season_blend`, 2 min 51 s. **This is the third
use of the 2025 holdout,** after F-02 (27b) and 27c.

**Verdict: the three passing markets adopt.** Every other market is rejected.

| Market | Paired n | MAE change | Diff / SE | Verdict |
|---|---|---|---|---|
| passing attempts | 568 | -4.69% | -0.423 / 0.100 (4.2 SE) | adopt |
| passing completions | 568 | -4.09% | -0.244 / 0.068 (3.6 SE) | adopt |
| passing yards | 568 | -2.53% | -1.779 / 0.782 (2.3 SE) | adopt |
| receptions | 4,803 | -0.53% | -0.007 / 0.006 | reject, under 1% |
| receiving yards | 4,803 | -0.37% | -0.061 / 0.071 | reject |
| fantasy points | 5,371 | -0.26% | -0.012 / 0.019 | reject |
| rushing yards | 1,963 | +1.40% | +0.247 / 0.153 | reject, worse |
| rushing attempts | 1,395 | +2.54% | +0.089 / 0.035 (2.5 SE worse) | reject, worse |

**Reading it:**
- **Passing gains in every phase.** Attempts and completions improve in weeks
  1-4, 5-10 and 11-18 alike, most in weeks 5-10 (-8.3% and -7.5%), where
  production has just switched to a thin current season. QB volume is stable
  across seasons, so last season is real evidence. Passing-yards bias falls
  from +8.22 to +4.64.
- **The spec's expectation about weeks 1-4 was wrong.** Production uses 2024
  alone there, and the blend adds the 1-3 current games at full weight, so
  weeks 1-4 move as much as later weeks. They improve in every market.
- **Elsewhere the blend helps early and hurts late.** Receiving, receptions,
  fantasy and rushing all gain in weeks 1-4 and lose in weeks 11-18, where
  17 discounted 2024 games still carry about 40% against 11 or more 2025 ones.
  Roles change more between seasons for RB, WR and TE. Rushing loses from week
  5 on. The rule is judged on the whole season, so these reject; a
  phase-dependent weight is a new variant and is not tried here.
- **The OVER lean is unchanged or slightly worse** outside passing (`share_below`
  for receiving yards rises from 61.3% to 63.6%). The blend shifts the mean, not
  its skew; that remains 27g.
- **Multiple comparisons.** Eight markets were judged. Attempts at 4.2 SE and
  completions at 3.6 SE are unlikely to be chance; yards at 2.3 SE moves the
  same way. 27a's forward line grading confirms it.
- **The scored set barely shifts:** 262 blend-only cases (1.3%) and no
  production-only ones, against 20,039 paired.

Output (per-arm tables omitted; the paired and by-phase tables are the
evidence):

```
Variant season_blend against production, paired on player, game and market
  market                      n  prod MAE   var MAE   change     diff      SE  verdict
  fantasy_points           5371     4.625     4.613   -0.26%   -0.012   0.019  reject
  passing_attempts          568     9.021     8.597   -4.69%   -0.423   0.100  adopt
  passing_completions       568     5.966     5.722   -4.09%   -0.244   0.068  adopt
  passing_yards             568    70.336    68.557   -2.53%   -1.779   0.782  adopt
  receiving_yards          4803    16.384    16.322   -0.37%   -0.061   0.071  reject
  receptions               4803     1.270     1.263   -0.53%   -0.007   0.006  reject
  rushing_attempts         1395     3.499     3.588   +2.54%   +0.089   0.035  reject
  rushing_yards            1963    17.655    17.903   +1.40%   +0.247   0.153  reject

Unpaired: production-only 0, blend-only 262, paired 20039

By phase (paired)
  market                phase             n     prod    blend   change     diff      SE
  fantasy_points        weeks 1-4      1094    4.844    4.701   -2.96%   -0.143   0.024
  fantasy_points        weeks 5-10     1711    4.669    4.608   -1.30%   -0.061   0.043
  fantasy_points        weeks 11-18    2566    4.501    4.578   +1.70%   +0.077   0.026
  passing_attempts      weeks 1-4       127    8.700    8.561   -1.60%   -0.139   0.125
  passing_attempts      weeks 5-10      176    8.513    7.809   -8.27%   -0.704   0.207
  passing_attempts      weeks 11-18     265    9.512    9.139   -3.92%   -0.373   0.151
  passing_completions   weeks 1-4       127    5.706    5.599   -1.87%   -0.107   0.083
  passing_completions   weeks 5-10      176    5.684    5.261   -7.45%   -0.423   0.143
  passing_completions   weeks 11-18     265    6.278    6.088   -3.04%   -0.191   0.102
  passing_yards         weeks 1-4       127   69.503   68.450   -1.52%   -1.054   0.825
  passing_yards         weeks 5-10      176   67.202   64.364   -4.22%   -2.838   1.612
  passing_yards         weeks 11-18     265   72.817   71.394   -1.95%   -1.423   1.229
  receiving_yards       weeks 1-4       967   17.111   16.666   -2.60%   -0.445   0.089
  receiving_yards       weeks 5-10     1535   16.402   16.158   -1.49%   -0.244   0.162
  receiving_yards       weeks 11-18    2301   16.066   16.288   +1.38%   +0.222   0.095
  receptions            weeks 1-4       967    1.358    1.311   -3.45%   -0.047   0.007
  receptions            weeks 5-10     1535    1.263    1.250   -1.06%   -0.013   0.013
  receptions            weeks 11-18    2301    1.237    1.251   +1.19%   +0.015   0.008
  rushing_attempts      weeks 1-4       270    3.701    3.516   -4.99%   -0.184   0.037
  rushing_attempts      weeks 5-10      452    3.318    3.499   +5.47%   +0.181   0.076
  rushing_attempts      weeks 11-18     673    3.541    3.677   +3.85%   +0.136   0.048
  rushing_yards         weeks 1-4       397   19.298   18.712   -3.04%   -0.586   0.146
  rushing_yards         weeks 5-10      628   17.918   18.507   +3.28%   +0.588   0.365
  rushing_yards         weeks 11-18     938   16.784   17.156   +2.21%   +0.372   0.198
```

## Notes for the AI

- **`PREVIOUS_SEASON_WEIGHT = 0.6`, two seasons and the raw-sum `games` are
  pre-registered here, 2026-09-26, before any score.** Do not adjust them after
  seeing Step 4.
- **Loaded history is short.** Weekly stats cover 2024 onward, so every 2025
  replay blends 2025 with 2024, and the gap-year case never occurs in the
  holdout. It exists for 2026 live lines only.
- **Where the blend moves the number.** Written before the run: "Weeks 1-4
  barely change." That was wrong (see Results): production uses 2024 alone
  there and the blend adds the current games, so every phase moves.
- **The scored set can shift slightly.** A player with 3 current and 2 previous
  games is unrated in production (3 games) and rated in the blend (5). The
  paired comparison matches on (player, game, market), so only common cases
  are judged; report the unpaired counts if they exceed a few percent.
- **Regression weight saturates.** `model_projection` shrinks by
  `min(1, games / 4)`, so with raw-sum games nearly every blended row is at full
  weight. That is expected.
- **Reuse:** `_averages` and `_usage` shapes, `_slate_line`,
  `apply_team_game_dvp`, the 27b metrics and verdict. Do not re-query per
  season; Step 1 only keeps what the query already returns.
- Standards: `X | None`, no `Any`, no em dashes, comment only the why,
  repositories own SQL, and `app/core` stays pure.
