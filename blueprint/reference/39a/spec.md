# Feature: Rec Targets baseline on 2024

**From build-plan:** feature 39a (parent 39, NFL Rec Targets projection)
**Status:** parked 2026-10-18 for the F-10 fix; restore to `blueprint/context/current-feature.md` before `/implement`
**Branch:** `feature/39a-rec-targets-baseline`

## Goal

Give PrizePicks Rec Targets lines their first projection: a pure function,
replayed on the 2024 season only, with the arm chosen under 27b's
pre-registered adoption rule and the result named `nfl-targets-v1`. This is
backtest-only. Nothing served changes, so 39b (P(over)), 39c (serve and freeze)
and 39d (forward check) build on a projection that was chosen before any line
was graded against it.

## In scope

- `app/core/nfl_targets_projection.py` (pure): the input shape, the three arms,
  the fixed arm order, the stacking rule, and the served composition once
  chosen.
- One repository read that turns 2024 WR, TE and RB player-games into replay
  rows with pre-week inputs, the closing moneyline and the actual targets.
- A CLI, `python -m app.backtest.nfl_targets_projection --season 2024`, that
  prints per-arm metrics, each candidate's paired verdict and the chosen
  composition. It refuses any season other than 2024.
- One recorded run on 2024. The chosen composition is fixed as constants under
  `NFL_TARGETS_MODEL_VERSION = "nfl-targets-v1"`.

## Out of scope

- **Any read of 2025.** The CLI cannot run on it. 39b makes the one 2025 read,
  for P(over) display only.
- **Anything served.** Rec Targets stays in `NflLineOnlyMarket`, and
  `NflPropMarket`, `MODELLED_MARKET_FILTER`, `_slate_line`, `build_slate`, frozen
  rows, 27a and 27j are untouched (39c and 39d).
- **P(over)** (39b).
- **The 27d season blend.** No 2023 stats are loaded, so a blend cannot be
  judged on 2024. It is recorded as untested, not rejected.
- **Matchup (DVP) for targets.** The opponent baselines hold no targets column;
  a later item can add one.
- Rush+Rec Yds and the other line-only markets.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [ ] **Step 1 - Pure projection and the pre-registered arm order** - create
  `app/core/nfl_targets_projection.py`:
  - `TargetsInput` (frozen dataclass): `season_average` and `season_games`
    (targets per game and usage games in the season `choose_baseline_season`
    picked), `position_average` (the position's targets per game in that
    season), `recent_values` (up to the last `RECENT_GAMES = 6` prior regular
    season targets, newest first, across seasons), `home_market_prob`,
    `player_is_home`, `market_is_stale`.
  - `TargetsArm` (frozen dataclass): `base` (`"season"` or `"recent"`) and
    `moneyline` (bool).
  - `project_targets(input, arm) -> float | None`: the base average regressed
    toward `position_average` by `min(1, games / MIN_BASELINE_GAMES)`, where
    `games` is `season_games` (season base) or `len(recent_values)` (recent
    base). With `arm.moneyline`, apply the v4 receiving factor unchanged
    (`1 + clamp(team_probability - 0.5, +/- MARKET_ADJUSTMENT_MAX)`, skipped
    when the probability is missing or stale). Rounded to 2 places. None when
    `season_games < MIN_BASELINE_GAMES`.
  - `REFERENCE_ARM = TargetsArm("season", False)` and
    `CANDIDATE_ORDER = ("moneyline", "recent")`, fixed now, before any 2024
    case is scored.
  - `next_arm(chosen, step) -> TargetsArm`: `moneyline` turns the factor on
    over the chosen base; `recent` swaps the base and keeps the chosen factor.
  - `choose_arm(verdicts) -> TargetsArm`: starts at `REFERENCE_ARM`, walks
    `CANDIDATE_ORDER`, and moves to the candidate only on an `adopt`.

  Add `tests/test_nfl_targets_projection.py`. *Done when:* tests pass for:
  - regression at 0, 2 and 4+ games
  - None below 4 season games
  - the moneyline factor's sign for home and away, the clamp, and stale or
    missing skipped
  - recent base with fewer than 6 values
  - `next_arm` stacking
  - `choose_arm` for adopt/adopt, adopt/reject, reject/adopt and all
    insufficient
  - a constants test pinning `REFERENCE_ARM`, `CANDIDATE_ORDER`,
    `RECENT_GAMES` and the reused `MIN_BASELINE_GAMES` and
    `MARKET_ADJUSTMENT_MAX`, so changing the order later fails loudly
- [ ] **Step 2 - Replay rows** - add
  `get_targets_replay_rows(db, season, week)` to `app/repositories/nfl.py`. It
  reuses `_slate_line_rows` with `_REPLAY_LINES_CTE`, positions WR, TE and RB,
  and the market `NflLineOnlyMarket.RECEIVING_TARGETS`, so baselines, the
  season chooser, the as-of team and the cutoff are the slate's own. It adds:
  - the actual `targets` from the week's stat row (skipped when NULL)
  - the last 6 prior targets per player through `get_recent_stat_rows(...,
    limit=RECENT_GAMES)`
  - the NFLverse closing moneyline as `home_market_prob`, as 27b does

  It returns `ReplayRow`s. Also add the pure builder
  `targets_input(row, recent_values, home_market_prob, market_is_stale)` to
  the core module. It reads `usage` and `position_usage` from a
  `_slate_line_rows` dict, and `player_is_home` from `player_team_id ==
  home_team_id`, so 39c builds the same input from a live slate row. The
  replay passes `market_is_stale=False`, because a closing line is never
  stale. *Done when:*
  - recorded-SQL tests in `test_nfl_repository.py` show `sport = 'nfl'` on
    every `sport_*` alias, `game_type = 'REG'`, the
    `season < :season OR (season = :season AND week < :week)` cutoff on the
    recent rows, and the market and position parameters
  - a test shows a row with NULL targets is skipped
  - builder tests cover missing `usage` (no input), missing `position_usage`
    (no input), home and away, and an as-of team on neither side (no
    input, matching the slate's `team_not_in_game` case)
- [ ] **Step 3 - Report CLI** - create `app/backtest/nfl_targets_projection.py`:
  - pure `replay_cases(rows, arm, week)` turning rows into `ReplayCase`s
    through `project_targets`, dropping None projections
  - pure `report(season, cases_by_arm, verdicts, chosen)` printing:
    - per arm: n, MAE, RMSE, bias and share below (`market_metrics`)
    - per candidate step: the paired diff against the arm it stacks on
      (`paired`) and its `adoption_verdict`
    - the chosen arm, and that the 27d blend is untested
  - `_main` loops weeks 1-18 of the season and walks `CANDIDATE_ORDER`,
    scoring each candidate against the arm chosen so far

  `--season` defaults to 2024, and any other value exits non-zero with "Rec
  Targets arms are chosen on 2024 only (39a); 2025 is the holdout." *Done
  when:*
  - report tests pass on fixed cases, including an empty-candidate
    `insufficient` path
  - a test shows `--season 2025` exits without opening a database session
- [ ] **Step 4 - The 2024 run and the served composition** - run the CLI once
  on 2024 and paste its output into this spec's Results section. Then set
  `NFL_TARGETS_MODEL_VERSION = "nfl-targets-v1"` and `SERVED_ARM` (the chosen
  `TargetsArm`) in the core module, plus `project_served(input)` returning
  `project_targets(input, SERVED_ARM)`. *Done when:*
  - Results holds the full report
  - a test pins `SERVED_ARM` to what `choose_arm` returns for the recorded
    verdicts, and pins the version string
  - nothing outside `app/backtest/` and the tests imports the module
    (checked with `rg`)
  - the Verify command passes

## Files / areas

- `api/app/core/nfl_targets_projection.py` (new, pure)
- `api/app/repositories/nfl.py` (one new read; no existing query changes)
- `api/app/backtest/nfl_targets_projection.py` (new CLI)
- `api/tests/test_nfl_targets_projection.py` (new),
  `api/tests/test_nfl_targets_projection_report.py` (new),
  `api/tests/test_nfl_repository.py` (additions)

## Data / contracts

- **No schema change.** The read uses `nfl_player_weekly_stats.targets`,
  complete for 2024 WR, TE and RB (read-only count, 2026-10-18: 5,200
  player-games, every row non-null). No 2023 is loaded.
- **Load-bearing for 39b to 39d:**
  - `NFL_TARGETS_MODEL_VERSION = "nfl-targets-v1"`, the model version on every
    Rec Targets frozen row; 39b's fit gates on it.
  - `TargetsInput` and `project_served`, the one projection function 39c
    serves and freezes.
  - The market string stays `"receiving_targets"`, never renamed (34a).
- **Pre-registered here (Step 1, before any case is scored):**
  - the arm order: reference (season average), then moneyline, then recent
    6 games
  - the stacking rule
  - 27b's adoption constants, unchanged: 300 paired cases, MAE at least 1.0%
    lower, and the paired difference below zero by more than 2 SE
  - eligibility: WR, TE and RB player-games with a non-null result and 4+
    prior usage games

## Testing

- The test gate is on. Steps 1 to 3 ship tests with their logic (core arms,
  selection, report, recorded SQL, the season guard). Step 4 adds the
  constant pins.
- Verify: `npm --prefix web run verify && cd api && python -m pytest` (API
  venv active).
- `/check` evidence: the Results report from one 2024 run, the season guard
  refusing 2025, and `rg` showing no production import.

## Notes for the AI

- **Holdout discipline.** Never run the CLI, a query or a test against 2025
  data. The guard exits before any database work. 2024 is development data;
  its earlier uses for fits (27e, 27k, 19m) do not make it a holdout.
- **One run.** Step 4 runs the CLI once and records it. If the run fails
  midway, rerunning is fine; changing an arm, constant or eligibility after
  seeing results is not. That would be a new version with a new rule.
- Keep `app/core/` pure. Reuse `MIN_BASELINE_GAMES` (`app/core/nfl_baseline.py`)
  and `MARKET_ADJUSTMENT_MAX` (`app/core/nfl_projection.py`) rather than copying
  numbers. Reuse `ReplayCase`, `market_metrics`, `paired` and
  `adoption_verdict` from `app/core/nfl_projection_backtest.py`.
- `_slate_line` casts to `NflPropMarket`, so it must never see these rows;
  build `TargetsInput` from the `_slate_line_rows` dict directly (`usage` and
  `position_usage` hold the season's targets average and games).
- **Known difference from serving:** 2024 uses NFLverse closing moneylines,
  while 39c will serve the latest stored US moneyline (Tuesday). This is the
  same compromise 27b made; record it in Results.
- F-10 (27j finished-week guard) is a separate `/fix` and not part of this
  feature. 39d depends on it.

## Results

> Filled in by Step 4.
