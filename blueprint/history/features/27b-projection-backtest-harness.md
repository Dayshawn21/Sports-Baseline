# Feature: NFL projection backtest harness

**From build-plan:** feature 27b
**Status:** complete

## Goal

Build the gate every NFL prop-projection change must pass. The harness replays
the 2025 regular season week by week: for every QB, RB, WR and TE game and every
market that position is bet on, it computes the projection `/nfl/slate` would
have served before that week, then scores it against what happened.

The scores are:
- error per market
- bias
- how often the result fell below the projection, which is the direct measure of
  the mean-versus-median OVER lean the review found

It needs no prop lines, which do not exist for 2025.

It ships with:
- a **pre-registered adoption rule** that 27c-27f must pass
- one comparison run now: production against production-without-usage, which
  settles finding **F-02**

It is read-only. It changes no projection.

## Design reference

None. This is a CLI report, with no UI.

## In scope

- **`get_slate_lines` takes its lines as a parameter.** Its SQL is split so the
  "which lines" CTE is swappable, with no behavior change. The slate keeps
  PrizePicks lines, and the replay drives the same query from player-games.
- **A replay loader, `get_replay_rows(db, season, week)`,** returning slate-shaped
  rows for every QB/RB/WR/TE player-game that week that recorded a stat, crossed
  with the markets for that position. Each row carries the actual stat value and
  the game's de-vigged closing moneyline.
- **A pure metrics module, `app/core/nfl_projection_backtest.py`:**
  - per-arm, per-market error, bias, and share below
  - a paired comparison between two arms
  - the adoption rule as a function
- **The harness, `python -m app.backtest.nfl_projections`.** It replays a season
  through the slate's own `_slate_line` for each arm and prints the tables and a
  verdict per market.
- **The first run, on 2025:** `production` against `usage_off`, with the result
  in Results and the evidence for F-02.

## Out of scope

- Any projection change: 27c-27f each bring their own arm and use this gate.
- Anytime TD, which has its own backtest (`python -m app.backtest.nfl_anytime_td`,
  19j-19n) scored on log loss.
- P(over) and distributions (27g).
- Removing the usage adjustment, even if `usage_off` passes. The harness reports
  the verdict; the change goes through a 27c-27f spec or a `/fix`, with your
  approval.
- Frozen projection snapshots (raised for 27g/27h).
- First-half, first-quarter and season segments.

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

- [x] **Step 1 - A swappable lines CTE in `get_slate_lines` (no behavior
  change).**
  - Extract the body into `_slate_line_rows(db, season, week, lines_cte, params)`.
  - `get_slate_lines` passes `_LATEST_LINES_CTE`, as today.
  - The lines CTE must expose `id, provider, market, segment, line, start_time,
    fetched_at, player_id, game_id, odds_type, raw_json` under the name
    `latest_lines`.

  *Done when:*
  - `pytest` passes.
  - `/nfl/slate` weeks 2 and 3 JSON is byte-identical before and after
    (SHA-256), as in 27a's step 1.
- [x] **Step 2 - Replay loader.** Add `get_replay_rows(db, season, week) ->
  list[ReplayRow]` to `app/repositories/nfl.py`:
  - **Driver CTE:** every `nfl_player_weekly_stats` row in the week's REG games
    for a QB, RB, WR or TE, crossed with that position's markets
    (`REPLAY_MARKETS_BY_POSITION`, below), exposed as `latest_lines` with
    synthetic values: `id` = a stable key, `line` 0, `segment` `full_game`,
    `odds_type` `standard`, `provider` `replay`.
  - Runs through `_slate_line_rows`, so the same as-of cutoff (`season < S OR
    (season = S AND week < W)`), baselines, matchup and usage apply.
  - **Also returns:**
    - each row's actual stat (via 27a's `STAT_COLUMN_BY_MARKET`)
    - the game's `market_home_probability(home_moneyline, away_moneyline)` from
      `nfl_games`, the closing line, since no live odds were stored for 2025

  *Done when:*
  - A recorded-SQL test shows the driver: the position filter, the week filter,
    the market fan-out, and the actuals join.
  - A live count for 2025 week 10 prints rows per market.
- [x] **Step 3 - Pure metrics and the adoption rule.** Add
  `app/core/nfl_projection_backtest.py`:
  - `market_metrics(cases) -> MarketMetrics`: n, MAE, RMSE, bias (mean of
    projection minus actual), and `share_below` (share of actuals strictly below
    the projection; about 50% for a median-like number).
  - `paired(production, variant) -> PairedDiff`: matched on (player, game,
    market). Mean of `|variant error| - |production error|`, its standard error,
    and the relative MAE change.
  - `adoption_verdict(diff) -> "adopt" | "reject" | "insufficient"`, with the
    rule below.

  *Done when:* unit tests cover:
  - MAE, RMSE and bias on a known set
  - `share_below` excluding exact ties
  - pairing dropping unmatched cases
  - each verdict branch, including exactly the 1% and 2-standard-error
    boundaries and the minimum n
- [x] **Step 4 - The harness.** Add `app/backtest/nfl_projections.py`, with
  `--season` (default 2025) and `--arms` (default `production,usage_off`).
  - **For each week:** load replay rows, then for each arm transform the row
    (`production` unchanged; `usage_off` sets `usage` to None) and project
    through `_slate_line(row, season, home_prob)`.
  - **Scores only rows `edge_is_comparable` would rate** (4 or more games in the
    baseline), so it measures the lines that get edges.
  - **Prints:**
    - per arm: a table by market and position (n, MAE, RMSE, bias,
      `share_below`)
    - per variant: the paired difference and verdict by market, with the rule
      text

  *Done when:*
  - A report test on synthetic cases checks one metrics row, one paired row and
    a verdict.
  - The live 2025 run completes.
  - Its output is pasted under Results, with the F-02 conclusion stated.

## Files / areas

- `api/app/repositories/nfl.py` - `_slate_line_rows`, `get_replay_rows`.
- `api/app/core/nfl_projection_backtest.py` (new) - metrics, pairing, verdict.
- `api/app/backtest/nfl_projections.py` (new) - the harness.
- Tests:
  - `test_nfl_repository.py` (the replay loader)
  - `test_nfl_projection_backtest.py` (new)
  - `test_nfl_projection_harness.py` (new)

## Data / contracts

No schema change.

**Load-bearing, since 27c-27f each add an arm and cite this rule:**

```python
# app/core/nfl_projection_backtest.py
REPLAY_MARKETS_BY_POSITION = {
    "QB": ("passing_yards", "passing_attempts", "passing_completions", "rushing_yards", "fantasy_points"),
    "RB": ("rushing_yards", "rushing_attempts", "receiving_yards", "receptions", "fantasy_points"),
    "WR": ("receiving_yards", "receptions", "fantasy_points"),
    "TE": ("receiving_yards", "receptions", "fantasy_points"),
}

@dataclass(frozen=True)
class ReplayCase:
    player_id: int
    game_id: int
    week: int
    position: str
    market: str
    projection: float
    actual: float

Verdict = Literal["adopt", "reject", "insufficient"]
```

**Pre-registered adoption rule, fixed 2026-09-26, before any variant is
scored.** A variant is adopted for a market only when all of these hold:

1. at least 300 paired 2025 cases in that market
2. MAE improves by at least 1.0% relative to production
3. the paired mean absolute-error difference is below zero by more than two
   standard errors

It is rejected otherwise, and "insufficient" when n is below 300. Each variant
is scored once on 2025. Adopted variants stack in build-plan order (27c, then
27d on top of it, and so on), and each is confirmed forward through 27a's line
grading. The 2025 holdout has now been used once (F-02), so later arms say so in
their Results.

## Testing

- The test gate is on:
  - Step 3 ships unit tests.
  - Step 4 ships a report test.
  - Step 2 ships a recorded-SQL test.
  - Step 1 is proven by the suite plus byte-identical slate JSON.
- Run with `cd api && .venv\Scripts\python.exe -m pytest`.
- No web change.

## Results

Run 2026-09-26 on 2025 REG weeks 1-18, `production` against `usage_off`
(`python -m app.backtest.nfl_projections`, 2 min 54 s, about 10 s a week).
This is the first use of the 2025 holdout.

**F-02 is settled: keep the usage adjustment.** Removing it makes both markets
it touches worse. It is rejected on the 1% rule, and the difference sits well
past two standard errors in production's favor:

| Market | Paired n | MAE change without usage | Diff / SE |
|---|---|---|---|
| receiving yards | 4,803 | +0.93% | +0.152 / 0.022 (about 7 SE worse) |
| receptions | 4,803 | +0.70% | +0.009 / 0.001 (about 9 SE worse) |

Every other market is identical in both arms, as expected, because usage
applies only to receiving yards and receptions. The downward skew F-02
describes is real, but it moves the projection closer to the result, not
further away. Without usage, receiving-yards bias grows from +0.52 to +0.72.

**The OVER lean is confirmed for every market.** `share_below` runs 54% to 64%
against about 50% for a median-like number. The largest gaps are:
- RB receiving yards: 64.1%
- WR fantasy: 61.7%
- WR receiving yards: 61.4%
- RB rushing yards: 60.9%

Mean bias is small except for passing yards (+8.2) and attempts (+1.3), so the
skew comes from mean against median, not from a shifted mean. That is the case
for 27g's distributions, and for 27d/27e on passing.

Output (the `usage_off` per-arm table is omitted: it matches production
except in the receiving rows, which the paired table covers):

```
NFL projection backtest, 2025 (model opponent-dvp-usage-snap-v1)

Arm production: projection minus actual (bias > 0 and share below > 50% mean the projection runs high)
  market / position                   n      MAE     RMSE     bias    below
  fantasy_points / all             5371     4.62     6.46    +0.21    59.5%
  fantasy_points / QB               568     6.84     8.66    +0.53    54.8%
  fantasy_points / RB              1395     4.60     6.53    +0.02    59.3%
  fantasy_points / TE              1160     3.73     5.32    -0.05    57.8%
  fantasy_points / WR              2248     4.54     6.30    +0.39    61.7%
  passing_attempts / QB             568     9.02    11.94    +1.28    55.1%
  passing_completions / QB          568     6.07     7.99    +0.90    54.0%
  passing_yards / QB                568    70.34    92.37    +8.22    53.9%
  receiving_yards / all            4803    16.38    23.88    +0.52    61.3%
  receiving_yards / RB             1395    10.00    15.09    +0.26    64.1%
  receiving_yards / TE             1160    15.12    21.30    -0.31    57.9%
  receiving_yards / WR             2248    21.00    29.04    +1.11    61.4%
  receptions / all                 4803     1.27     1.74    +0.07    58.1%
  receptions / RB                  1395     1.07     1.46    +0.04    59.9%
  receptions / TE                  1160     1.24     1.72    -0.01    53.8%
  receptions / WR                  2248     1.41     1.90    +0.13    59.2%
  rushing_attempts / RB            1395     3.50     4.85    -0.08    57.8%
  rushing_yards / all              1963    17.66    26.60    -0.13    60.0%
  rushing_yards / QB                568    11.70    15.95    +0.62    57.8%
  rushing_yards / RB               1395    20.08    29.87    -0.44    60.9%

Variant usage_off against production, paired on player, game and market
  market                      n  prod MAE   var MAE   change     diff      SE  verdict
  fantasy_points           5371     4.625     4.625   +0.00%   +0.000   0.000  reject
  passing_attempts          568     9.021     9.021   +0.00%   +0.000   0.000  reject
  passing_completions       568     6.067     6.067   +0.00%   +0.000   0.000  reject
  passing_yards             568    70.336    70.336   +0.00%   +0.000   0.000  reject
  receiving_yards          4803    16.384    16.536   +0.93%   +0.152   0.022  reject
  receptions               4803     1.270     1.278   +0.70%   +0.009   0.001  reject
  rushing_attempts         1395     3.499     3.499   +0.00%   +0.000   0.000  reject
  rushing_yards            1963    17.655    17.655   +0.00%   +0.000   0.000  reject
```

(Single-position "all" rows that duplicate their position row are trimmed here.)

## Notes for the AI

- **Exactly the served projection, with two known differences:**
  - the moneyline is 2025's de-vigged closing line, not a live fetch
  - injuries and depth feed nothing (they are display-only), so omitting them
    changes nothing

  Everything else goes through `_slate_line` untouched.
- **The weekly stats include defense (LB, CB, and so on),** so filter to QB, RB,
  WR and TE in the driver. 2025 has about 2,500 WR, 1,600 RB and 1,300 TE
  player-games.
- **Selection:** only players who recorded a stat are replayed. PrizePicks voids
  players who sit, so this matches what gets graded. A blocking TE with snaps and
  no stat row is not replayed, and that is acceptable here.
- **Early weeks lean on 2024,** which has no 2023 behind it. So 2025 weeks 1-4
  run on a full 2024 season, which is realistic, not a flaw.
- **Performance:** 18 weeks × about 1,000 player-games × 3-5 markets, fanned out
  by season in SQL. Keep one query per week. If a week takes over 30 seconds,
  report it rather than restructure.
- **Do not tune anything to 2025.** Any fitted constant in 27c-27f fits on 2024.
- **Reuse:**
  - `market_home_probability` from `app.core.nfl_game_lines`
  - `STAT_COLUMN_BY_MARKET` from `app.core.nfl_line_grading`
  - `_slate_line` and `edge_is_comparable` as they are
- Standards: `X | None`, no `Any`, no em dashes, comment only the why,
  repositories own SQL, and `app/core` stays pure.
