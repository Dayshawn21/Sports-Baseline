# Feature: Matchup by team-game

**From build-plan:** feature 27c
**Status:** complete

## Goal

Rebuild the NFL defense-versus-position (DVP) adjustment on per-game position
totals, with real game counts and a recent window. Then score it once through the
27b harness on 2025, and adopt it only for markets that pass the pre-registered
rule.

**What is wrong today** (`opponent_position_baselines` in
`app/repositories/nfl.py`):
- **It averages player rows, not games.** A defense's "WR receiving yards
  allowed" is the mean per WR row, so a game where it faced four WRs weighs four
  times, and a defense that faces many WR3s looks stingy per player.
- **Its game count is a row count.** `COUNT(*)` over player rows gives about
  three "games" per real WR game, so `OPPONENT_MIN_SAMPLE_GAMES` (4) and
  `OPPONENT_FULL_WEIGHT_GAMES` (12) trip after one to four real games.
- **It pools every loaded season equally,** so a 2024 defense counts as much as
  last week's.

**The variant:** for each defense and position, sum the position's stats per
team-game, then average the most recent 17 team-games before the slate week (one
season's worth, reaching into the prior season early on). The league reference is
the mean of the same team-game totals across every defense's window, so the ratio
is centered. The ratio, the ±10% cap and the sample-weight constants stay exactly
as they are.

## Design reference

None. Backend and CLI only, plus at most one label in the evidence panel if
adopted (Step 6).

## In scope

- **A team-game totals loader,** `get_team_game_position_totals(db, season,
  week)`: per defense and position, every completed pre-week REG team-game's
  summed stats, newest first, uncapped.
- **A pure DVP module,** `app/core/nfl_team_game_dvp.py`: the 17-game window
  average per defense and position, and the league reference per position.
- **A `dvp_team_game` harness arm,** fed by the replay loader attaching the
  team-game averages to each row.
- **One scored run on 2025,** with the per-market verdict under Results.
- **Conditional adoption** (Steps 5 and 6): only markets whose verdict is
  `adopt` switch to team-game DVP on `/nfl/slate`, with a model version bump.
  If none pass, Steps 5 and 6 are skipped, the result is recorded, and nothing in
  production changes.

## Out of scope

- **Anytime TD.** Its DVP stays on the current per-player baseline whatever the
  verdict. It has its own log-loss backtest (19j-19n), and team-game TD totals
  through `1 - exp(-rate)` are not the same quantity.
- **Retuning** the cap (`OPPONENT_ADJUSTMENT_MAX`), the sample constants, or the
  17-game window. Nothing is fitted to 2025.
- **A second variant** (for example a different window or season weighting).
  Each extra arm spends the 2025 holdout again.
- **Removing** `opponent_position_baselines`. Anytime TD and any market that
  fails still read it.
- Season blending (27d), game environment (27e), fantasy scoring (27f), P(over)
  (27g).
- The display-only "allowed" history (`get_slate_opponent_position_history`),
  which already groups by game and stays as is.

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

- [x] **Step 1 - Team-game totals loader.** Add
  `get_team_game_position_totals(db, season, week) -> dict[tuple[int, str],
  list[NflTeamGameTotals]]` to `app/repositories/nfl.py`:
  - one query, grouped by `s.opponent_team_id`, `p.position`, `g.id` only (not
    by the offense team code, which can split a game in two)
  - REG, `status = 'completed'`, `s.opponent_team_id IS NOT NULL`,
    `p.position IS NOT NULL`, and the shared as-of cutoff (`season < S OR
    (season = S AND week < W)`)
  - the nine stat sums, with `fantasy_points` NULL when every row is NULL
  - ordered newest first per key, no cap

  *Done when:*
  - A recorded-SQL test in `test_nfl_repository.py` shows the grouping, the
    filters, the cutoff and the ordering, and that two rows of one game fold
    into one `NflTeamGameTotals`.
  - A live call for 2025 week 10 prints, for a few defenses, the WR team-game
    count and the mean team-game WR receiving yards (roughly 130 to 200 is
    plausible).
- [x] **Step 2 - Pure team-game DVP.** Add `app/core/nfl_team_game_dvp.py`:
  - `NflTeamGameTotals` (frozen dataclass: `game_id`, `season`, `week`, the nine
    stats, `fantasy_points: float | None`)
  - `window_averages(totals, window=DVP_TEAM_GAME_WINDOW) -> dict | None`: the
    mean of the newest `window` team-games, in the `_averages` dict shape that
    `NflHistoricalAverages(**...)` accepts, with `games` = team-games used;
    None when there are none
  - `league_averages(totals_by_key, window) -> dict[str, dict]`: per position,
    the mean over every defense's windowed team-games pooled, `games` = the
    pooled count
  - `fantasy_points` averages only the non-NULL games, and is None when all are
    NULL

  *Done when:* unit tests cover:
  - the window takes the newest 17 and no more, and fewer when fewer exist
  - `games` counts team-games, not player rows
  - the league reference pools windows, so a defense with 17 games weighs more
    than one with 3
  - the fantasy NULL handling
  - an empty input returns None and an empty league map
- [x] **Step 3 - The `dvp_team_game` arm.**
  - `get_replay_rows` calls the Step 1 loader once per week and attaches
    `team_game_opponent_averages` (the defense's window for the player's
    position, or None when the opponent is unknown) and
    `team_game_league_averages` to each row.
  - `ARMS` gains `dvp_team_game`, which swaps those two into
    `opponent_averages` and `league_position_averages`. Nothing else in the row
    changes, so `_slate_line` runs untouched.
  - The default `--arms` becomes `production,dvp_team_game`; `usage_off` stays
    selectable.

  *Done when:*
  - A harness test runs a synthetic row through both arms and shows
    `opponent_adjustment_pct` moving from the per-player ratio to the team-game
    ratio, with `opponent_sample_games` equal to the team-game count.
  - A row whose opponent is unknown gets `opponent_data_missing` in both arms.
  - The Step 1 recorded-SQL test still passes, and `pytest` is green.
- [x] **Step 4 - Score it on 2025.** Run `python -m app.backtest.nfl_projections`
  once with the default arms.

  *Done when:*
  - The run completes for weeks 1-18.
  - Results holds: the paired table, the verdict per market, and a note that
    this is the second use of the 2025 holdout (after F-02).
  - If no market is `adopt`, Steps 5 and 6 are marked skipped with the reason,
    and the feature goes to `/complete` as "not adopted".
- [x] **Step 5 - Adopt in the slate (only if Step 4 adopts a market).**
  - `TEAM_GAME_DVP_MARKETS` in `app/core/nfl_projection.py`: exactly the markets
    Step 4 adopted, never `anytime_touchdown`.
  - `build_slate` loads the Step 1 totals once and, for those markets only,
    passes the team-game averages as `opponent_averages` and
    `league_position_averages`. The shared swap lives in one helper used by both
    the slate and the harness's `production` arm, so the harness keeps
    measuring what is served.
  - Bump `NFL_PROJECTION_MODEL_VERSION` (to `opponent-dvp-tg-usage-snap-v2`).

  *Done when:*
  - A slate test shows an adopted market reading the team-game ratio and a
    non-adopted market and anytime TD reading the old one.
  - Re-running the harness's `production` arm reproduces Step 4's
    `dvp_team_game` MAE for the adopted markets and production's for the rest.
  - `/nfl/slate` for 2026 week 3 returns 200 with the new version string.
- [x] **Step 6 - Evidence panel label (only if Step 5 ran).** In
  `NflEvidencePanel.tsx`, the Matchup line reads "{value} to {position}s per
  game · N games" for team-game markets, driven by the market, so the total is
  not read as one player's figure.

  *Done when:* `npm run build` and `npm run test` pass, and a screenshot of an
  adopted-market evidence panel shows the new label with a team-game count.

## Files / areas

- `api/app/repositories/nfl.py` - `get_team_game_position_totals`; attach in
  `get_replay_rows`.
- `api/app/core/nfl_team_game_dvp.py` (new) - window and league averages.
- `api/app/backtest/nfl_projections.py` - the `dvp_team_game` arm and default
  arms.
- If adopted: `api/app/core/nfl_projection.py`, `api/app/services/nfl/slate.py`,
  `web/src/components/NflEvidencePanel.tsx`.
- Tests:
  - `test_nfl_repository.py` (loader SQL)
  - `test_nfl_team_game_dvp.py` (new)
  - `test_nfl_projection_harness.py` (the arm)
  - if adopted, a slate test for the market split

## Data / contracts

No schema change.

```python
# app/core/nfl_team_game_dvp.py
DVP_TEAM_GAME_WINDOW = 17  # one regular season; fixed before scoring, not fitted

@dataclass(frozen=True)
class NflTeamGameTotals:
    game_id: int
    season: int
    week: int
    passing_yards: float
    passing_attempts: float
    passing_completions: float
    rushing_yards: float
    rushing_attempts: float
    receiving_yards: float
    receptions: float
    touchdowns: float
    fantasy_points: float | None
```

**Load-bearing:**
- The averages dicts keep the `_averages` shape, so `_slate_line` and
  `opponent_adjustment_pct` need no change and `opponent_sample_games` becomes a
  real game count wherever team-game DVP is used.
- Replay rows gain `team_game_opponent_averages` and `team_game_league_averages`.
  27d-27f arms stack on top of an adopted 27c, so they read these keys too.

**The rule is 27b's, unchanged:** at least 300 paired cases, MAE at least 1.0%
lower, and the paired difference below zero by more than two standard errors,
per market.

## Testing

- The test gate is on:
  - Step 1 ships a recorded-SQL test.
  - Step 2 ships unit tests.
  - Step 3 ships a harness test.
  - Step 5, if it runs, ships a slate test.
  - Step 6 rides on build, tests and a screenshot.
- Run with `cd api && .venv\Scripts\python.exe -m pytest`.

## Results

Run 2026-09-26 on 2025 REG weeks 1-18, `production` against `dvp_team_game`
(`python -m app.backtest.nfl_projections`, 2 min 59 s). **This is the second
use of the 2025 holdout,** after F-02 in 27b.

**Verdict: one market adopts, passing completions.** Every other market is
rejected.

| Market | Paired n | MAE change | Diff / SE | Verdict |
|---|---|---|---|---|
| passing completions | 568 | -1.65% | -0.100 / 0.044 (2.3 SE) | adopt |
| passing attempts | 568 | -1.45% | -0.131 / 0.068 (1.9 SE) | reject, misses the 2 SE bar |
| passing yards | 568 | -0.26% | -0.185 / 0.558 | reject |
| fantasy points | 5,371 | -0.12% | -0.005 / 0.008 | reject |
| rushing attempts | 1,395 | -0.17% | -0.006 / 0.013 | reject |
| receptions | 4,803 | -0.07% | -0.001 / 0.002 | reject |
| receiving yards | 4,803 | +0.06% | +0.011 / 0.027 | reject |
| rushing yards | 1,963 | +0.10% | +0.017 / 0.045 | reject |

**Reading it:**
- **The rebuild barely moves the high-volume markets.** Receiving, receptions,
  rushing and fantasy change by 0.2% or less either way. With real game counts
  the sample weight saturates, as expected, so the change is only the ratio and
  the window, and it is small.
- **Passing is where it helps.** All three passing markets improve (1.65%,
  1.45%, 0.26%), consistent with per-player QB averages being distorted by
  backup and garbage-time QB rows that team-game totals absorb.
- **Multiple comparisons.** Eight markets were judged, so one clearing 2 SE by
  chance is not rare. Completions clears at 2.3 SE, and attempts moves the same
  way at 1.9 SE, which makes a real passing effect more likely than a fluke.
  The rule is applied as pre-registered, and 27a's forward line grading
  confirms it.
- **The OVER lean is untouched.** `share_below` stays 53% to 64%, as expected:
  DVP scales the mean, not its skew (that is 27g).

Output (per-arm tables trimmed to the paired comparison):

```
Variant dvp_team_game against production, paired on player, game and market
  market                      n  prod MAE   var MAE   change     diff      SE  verdict
  fantasy_points           5371     4.625     4.619   -0.12%   -0.005   0.008  reject
  passing_attempts          568     9.021     8.890   -1.45%   -0.131   0.068  reject
  passing_completions       568     6.067     5.966   -1.65%   -0.100   0.044  adopt
  passing_yards             568    70.336    70.151   -0.26%   -0.185   0.558  reject
  receiving_yards          4803    16.384    16.394   +0.06%   +0.011   0.027  reject
  receptions               4803     1.270     1.269   -0.07%   -0.001   0.002  reject
  rushing_attempts         1395     3.499     3.493   -0.17%   -0.006   0.013  reject
  rushing_yards            1963    17.655    17.672   +0.10%   +0.017   0.045  reject
```

## Notes for the AI

- **The 17-game window and the unchanged constants are pre-registered here,
  2026-09-26, before any score.** Do not adjust them after seeing Step 4.
- **Loaded history is short.** Weekly stats cover 2024 onward, so 2025 week 1
  rests on 2024's 17 games and 2024 itself is never replayed. The window is
  therefore close to "all loaded games" early in 2025 and becomes truly recent
  later.
- **The sample weight will saturate.** With real counts, nearly every 2025
  defense has 12 or more team-games in its window, so the change is the ratio
  and the window, not the weighting. That is expected, not a bug.
- **Zero-fill:** a team-game with no row for a position is absent, not zero. For
  QB, RB, WR and TE every completed game has rows, so this only matters in
  principle; do not add a zero-fill.
- **Position** is `nfl_players.position` (current), as in the existing CTE.
- **Reuse:** `_averages` field names, `_slate_line`, `opponent_adjustment_pct`,
  the 27b metrics and verdict. Do not duplicate the as-of cutoff; use the same
  predicate text as `_BASELINES_CTE`.
- **Performance:** one extra query per week. If a harness week slows by more than
  a few seconds, report it.
- Standards: `X | None`, no `Any`, no em dashes, comment only the why,
  repositories own SQL, and `app/core` stays pure.
