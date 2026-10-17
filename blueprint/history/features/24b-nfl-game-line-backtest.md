# Feature 24b: Game-line backtest

**From build-plan:** feature 24b
**Status:** completed (2026-09-19)

## Final outcome

All three markets were rejected by the pre-registered rule on the 2022-2025
holdout: moneyline (blend log loss 0.6101 vs market 0.6082), spread (blend MAE
9.51 vs line 9.49, only 2 picks at a 3-point disagreement), and total (fitted
blend weight 0, a tie). Team ELO and the scoring rating may appear in 24d only
as context beside the market, never as an edge. The backtest command,
`python -m app.backtest.nfl_game_lines`, remains the gate for every 24c signal.

## Goal

Measure whether team ELO (24a) plus a simple scoring rating adds anything to the
closing market for NFL moneyline, spread, and total, using a fit/holdout split
and an adoption rule written down before the holdout is scored. The output is a
decision per market: adopted (24d may show model edges) or rejected (24d shows
model numbers as display only, or not at all).

## In scope

- Configurable ELO constants so the backtest can fit them, with `nfl-elo-v1`
  behavior unchanged.
- Pure game-line math: ELO margin, de-vigged closing home win probability,
  blends, and error metrics.
- A pure pre-game scoring rating (offense and defense points per team) for the
  total arm, since ELO measures relative strength only.
- A backtest command over 2014-2025 closing lines, fitted on 2014-2021 and scored
  once on the 2022-2025 holdout, reported overall and for weeks 1-4 versus 5+.
- A recorded decision per market after one holdout run.

## Out of scope

- Storing a tuned ELO version, or freezing adopted constants into production
  code. Both follow the decision, as their own reviewed change.
- Any API or UI (24d).
- EPA, pace, weather, rest, or QB inputs (24c, each through this backtest).
- Betting-return or Kelly simulation. Hit rates are reported against the
  -110 breakeven, not converted to profit.
- The 19n spread-sign bug (see Notes). It gets its own `/fix`.
- 2012-2013 (ELO burn-in) and 2026 (in progress).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Configurable ELO.** Add a frozen `NflEloConfig` (`k`,
  `home_field`, `season_regression`) to `app/core/nfl_elo.py` with `NFL_ELO_V1`
  holding today's constants; `update`, `expected_home_win_probability`,
  `regress_to_mean`, and `replay` take it with `NFL_ELO_V1` as the default.
  *Done when:* existing ELO tests pass unchanged, a new test shows a different
  config changes ratings, and `python -m app.ingest.nfl_team_elo` rewrites the
  table with the same hash as 24a (`9ea455e0c24e0cc17b0d6aa6eeac9334`, or the
  current hash taken just before the step if Tuesday's cron added scores).

- [x] **Step 2 - Game-line math.** `app/core/nfl_game_lines.py`: `elo_margin`
  (ELO difference including home field, divided by 25, as expected home
  points), `market_home_probability` (de-vigged closing moneylines through
  `core/odds.py`), `blend`, `mae`, and `pick_record` (hits, misses, pushes for
  picks where the model differs from the line by at least a threshold). Reuse
  `log_loss` and `brier` from `nfl_td_backtest`.
  *Done when:* focused tests cover each function, including pushes, a missing
  moneyline, and the NFLverse sign (positive `spread_line` = home favored).

- [x] **Step 3 - Scoring ratings for totals.** `app/core/nfl_scoring_ratings.py`:
  offense and defense ratings in points above league average, updated after
  each final game by a learning rate, regressed between seasons like ELO, with
  the league average taken only from games before the one predicted. `replay`
  yields expected home and away points per game.
  *Done when:* tests cover the update direction, season regression, a
  scheduled game, and the same leakage contract as the ELO replay.

- [x] **Step 4 - Backtest cases.** Repository `get_game_line_games` (regular
  season, date order, scores, closing lines, moneylines). Backtest module
  `app/backtest/nfl_game_lines.py` turns those games plus a given ELO config
  and scoring learning rate into one case per game: season, week bucket,
  outcomes, market values, and model values, with a market left `None` when
  its line is missing.
  *Done when:* a repository test pins the SQL order and filter, and a case
  test shows missing lines drop from only that market and 2012-2013 and 2026
  never become cases.

- [x] **Step 5 - Fit, score, report.** On 2014-2021 only, grid-fit the ELO
  config by ELO log loss, the scoring learning rate by total MAE, then each
  arm's blend weight per week bucket: moneyline by log loss, spread by margin
  MAE, total by total-points MAE. Blends are linear in the arm's own unit
  (probability or points) toward the market value. Score 2022-2025 once and print one table
  per arm (market, model alone, blend) overall and by bucket, plus the
  adoption verdict computed by the rule below.
  *Done when:* `python -m app.backtest.nfl_game_lines --dry-run-fit` prints
  the fitted configuration without scoring the holdout, and a test proves the
  fitted configuration does not change when every holdout outcome is flipped.

- [x] **Step 6 - Run once and record the decision.** Run the full backtest a
  single time and paste the output and verdicts below under **Decision**.
  *Done when:* the output and a per-market adopted or rejected verdict are
  recorded, with no retuning after the holdout was seen.

## Pre-registered adoption rule

Fixed now, before any holdout number exists. Holdout is 2022-2025.

| Market | Adopted only if, on the holdout |
|---|---|
| Moneyline | Blend beats de-vigged market on **both** log loss and Brier overall, and is not worse on log loss in either week bucket |
| Spread | Blend margin MAE beats closing-line MAE, **and** picks at a 3-point disagreement hit at least 52.4% (the -110 breakeven) over at least 100 non-push picks |
| Total | Same as spread, using total points and the closing total |

A fitted blend weight of 0 ties the market and counts as rejected. The
1.5-point threshold is reported for context only; it cannot adopt a market.
Grids are fixed here too:

- ELO `k`: 15, 20, 25; `home_field`: 24, 36, 48, 60; `season_regression`:
  0.25, 1/3, 0.5
- Scoring learning rate: 0.05, 0.1, 0.15, 0.2
- Blend weight: 0.0 to 1.0 in steps of 0.1

## Files / areas

- `api/app/core/nfl_elo.py` - config dataclass
- `api/app/core/nfl_game_lines.py` (new), `api/app/core/nfl_scoring_ratings.py` (new)
- `api/app/repositories/nfl.py` - `get_game_line_games`
- `api/app/backtest/nfl_game_lines.py` (new)
- Tests: `test_nfl_elo.py`, `test_nfl_game_lines.py` (new),
  `test_nfl_scoring_ratings.py` (new), `test_nfl_repository.py`

## Data / contracts

No schema change. `nfl_team_elo` keeps storing `nfl-elo-v1`; a tuned config is
only stored after an adopted decision, as a separate change.

**`NflEloConfig`** (load-bearing, 24d and any `nfl-elo-v2` read it):
`k: float`, `home_field: float`, `season_regression: float`.

**Backtest case** (backtest-internal): `game_key`, `season`, `week_bucket`
(`"1-4"` | `"5+"`), `home_won: bool | None` (None on a tie),
`home_margin`, `total_points`, `market_home_probability | None`,
`spread_line | None`, `total_line | None`, `elo_home_probability`,
`elo_margin`, `model_total`.

## Testing

- The test gate is on. Every function in the two new core modules gets focused
  tests; the config change keeps the 24a tests green unchanged.
- The holdout-independence test (Step 5) is the key guard: fitting must be a
  function of fit seasons alone.
- Integration: the Step 1 table hash and the Step 6 run are local-database
  checks with printed output as evidence.
- Final gate: `.venv\Scripts\python.exe -m pytest` from `api/`. No web change.

## Notes for the AI

- **NFLverse `spread_line` is the expected home margin: positive means the home
  team is favored.** Verified on 2012-2025: 2,272 home moneyline favorites
  carry a positive line and 7 a negative one, and the line's MAE against actual
  home margin is 10.0 versus 14.4 with the sign flipped. `implied_team_points`
  in `core/nfl_game_script.py` assumes the opposite; do not reuse it here.
- A spread pick "covers" when `home_margin - spread_line` has the sign of the
  model's disagreement; exactly zero is a push and is excluded from hit rate.
- Ties (a handful of games) are excluded from the moneyline arm only.
- Market seeding of week-1 ratings was considered and dropped: a spread fixes
  only the gap between two teams, not either team's level. The per-bucket
  blend weight does the same job (leaning on the market early when rosters
  changed) and is measured directly by the weeks 1-4 row.
- Closing lines are pre-game by definition; every model input is replayed from
  games strictly before the one predicted.
- `core/` stays pure. The backtest module may use numpy or scipy, as
  `nfl_anytime_td.py` uses scikit-learn.
- Do not look at holdout numbers before Step 6, and do not change a grid or
  the rule after it.

## Decision

Recorded 2026-09-19 from the single holdout run
(`python -m app.backtest.nfl_game_lines`). No grid, rule, or code changed after
it.

```
Fit 2014-2021: ELO k 20, home field 36, season regression 0.333; scoring learning rate 0.05
Blend weights (model share): moneyline 1-4 0.5, moneyline 5+ 0.1, spread 1-4 0.3, spread 5+ 0.1, total 1-4 0.0, total 5+ 0.0

MONEYLINE (log loss: market, model alone, blend)
set          games    market    model    blend  Br market  Br blend
2022-2025     1084    0.6082   0.6378   0.6101     0.2105    0.2113
  wk 1-4       254    0.6415   0.6594   0.6451     0.2253    0.2270
  wk 5+        830    0.5980   0.6312   0.5994     0.2059    0.2065
Verdict: rejected

SPREAD (MAE: market, model alone, blend)
set          games    market    model    blend  hit rate (W-L-P)
2022-2025     1087    9.4945   9.9430   9.5056  model@1.5 0.483 (314-336-17)  blend@1.5 0.593 (16-11-1)  model@3 0.493 (171-176-8)  blend@3 1.000 (2-0-0)
  wk 1-4       256    9.7539   9.9891   9.7454  model@1.5 0.538 (84-72-7)  blend@1.5 0.615 (16-10-1)  model@3 0.557 (49-39-3)  blend@3 1.000 (2-0-0)
  wk 5+        831    9.4146   9.9288   9.4317  model@1.5 0.466 (230-264-10)  blend@1.5 0.000 (0-1-0)  model@3 0.471 (122-137-5)  blend@3   -   (0-0-0)
Verdict: rejected

TOTAL (MAE: market, model alone, blend)
set          games    market    model    blend  hit rate (W-L-P)
2022-2025     1087   10.1891  10.4951  10.1891  model@1.5 0.503 (331-327-5)  blend@1.5   -   (0-0-0)  model@3 0.512 (168-160-5)  blend@3   -   (0-0-0)
  wk 1-4       256   10.3750  10.2720  10.3750  model@1.5 0.563 (85-66-1)  blend@1.5   -   (0-0-0)  model@3 0.569 (41-31-1)  blend@3   -   (0-0-0)
  wk 5+        831   10.1318  10.5639  10.1318  model@1.5 0.485 (246-261-4)  blend@1.5   -   (0-0-0)  model@3 0.496 (127-129-4)  blend@3   -   (0-0-0)
Verdict: rejected
```

**All three markets rejected.**

| Market | Why |
|---|---|
| Moneyline | Blend worse than the de-vigged market on log loss (0.6101 vs 0.6082) and Brier (0.2113 vs 0.2105), and worse in both week buckets |
| Spread | Blend MAE worse than the closing line (9.5056 vs 9.4945); only 2 picks reached a 3-point disagreement, far under 100 |
| Total | Fitted weight 0.0 in both buckets, so the blend equals the closing total: a tie, rejected |

**What it means for 24d:** ELO and the scoring rating are not bettable edges
against closing lines. Model spread, win probability, and total may be shown
as context beside the market, never as an edge or a ranked play.

**Post-hoc observations, not evidence.** The model alone did better than the
market in weeks 1-4 on totals (MAE 10.27 vs 10.38; 3-point picks 41-31) and
had a 3-point spread record of 49-39 there. Both are subgroups found after the
fact, under 100 picks, and inside the noise of a fair coin, so they adopt
nothing. If worth pursuing, they become a pre-registered hypothesis scored
only on seasons not yet played (2026 onward), never refitted on 2022-2025.
