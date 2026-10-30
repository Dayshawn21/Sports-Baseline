# Floor NFL v4 and Rec Targets history at 2024

**Type:** Fix
**Completed:** 2026-10-30
**Branch:** `fix/nfl-v4-history-floor`

## The problem

On 2026-10-29, 2018-2023 NFLverse weekly stats, rosters and snap counts were
backfilled into the shared Neon database for 49a (which had held only
2024-2026). The v4 projection (`opponent-dvp-tg-blend-usage-snap-v4`) and Rec
Targets (`nfl-targets-v1`) read every stored season before the slate week,
with no lower bound, so their output changed under unchanged version labels:

- `_BASELINES_CTE` in `api/app/repositories/nfl.py`: `opponent_position_baselines`
  (DVP) and `league_position_baselines` average every stored season, so every
  matchup adjustment moved; `baselines` and `position_baselines` offer
  2018-2023 seasons to `choose_baseline_season`, which falls back to any
  earlier season for a player who missed 2024.
- The 2025 v4 replay moved (QB passing yards 582 to 600 cases, bias +2.72 to +5.47).

## The fix

- One constant, `PROJECTION_FIRST_HISTORY_SEASON = 2024`, in
  `api/app/core/nfl_baseline.py`: v4 and Rec Targets were validated on history
  from 2024 on, and 2024 reproduces exactly what both read before the backfill.
- Every v4 and Rec Targets history read gets `season >= :first_history_season`.
- No version label, market or fitted constant changes. 49a's files are untouched.

## Build steps

- [x] **Step 1 - floor the v4 readers.** `_BASELINES_CTE` (four CTEs),
  `_attach_snap_history`, `_td_history`, `get_team_game_position_totals`,
  `get_slate_player_history`, `get_slate_opponent_position_history`. Recorded-SQL
  tests that each carries the floor and binds the param.
- [x] **Step 2 - floor Rec Targets history.** `_get_history_with_opponents` in
  `api/app/repositories/nfl_targets.py`, with a recorded-SQL test.

## Done when

- `python -m app.backtest.nfl_projections --season 2025 --arms production` is
  byte-identical to the pre-backfill baseline (`v4_2025_before.txt`).
- Verify passes.
- Every other NFL reader that serves or backtests v4 or Rec Targets is listed
  with whether it needed the floor.
- Production changes only after merge, push and the next snapshot rebuild.

## Readers checked

Floored: the four `_BASELINES_CTE` CTEs, `_attach_snap_history`, `_td_history`,
`get_team_game_position_totals`, `get_slate_player_history`,
`get_slate_opponent_position_history`, and Rec Targets
`_get_history_with_opponents`. Through them the projection backtest, the
over-probability fit, the targets backtest and the targets p-over fit are
floored too.

Not floored: the roster lookup (`_player_teams_cte`, a team as of the week, not
an aggregate; the replay matched without it), `previous_depth` (depth charts
were not backfilled), the QB game and chart reads (already `season - 1`),
matchup context (current season), the environment and wind fits (one explicit
season), line-only props, the game-line backtests, and the frozen-prediction
reports. Left for the owner: `get_historical_player_baselines` career averages
on `/projections`, and `get_weekly_td_rows` / `get_snap_rows` used by the
anytime-TD and prop-market backtests, which now read 2018-2023.

## Stored outputs written unbounded

Backfill window, 2026-10-29 UTC: stats 17:34-20:33, rosters and snaps 18:17-21:15.

- `report_snapshots`: `nfl_slate_week_7`, `_8`, `_9` for 2026, computed 23:54 UTC.
- `sport_prop_predictions`: 7,062 v4 and 112 `nfl-targets-v1` rows for 2026
  week 8, generated about 23:00 UTC. Insert is `ON CONFLICT DO NOTHING`, so a
  later run does not replace them. Rebuild or exclusion needs a separate yes.

## Evidence

- 2025 replay (`--arms production`) after the fix is byte-identical to the
  pre-backfill baseline (SHA-256 `78f37df8...`); QB passing yards back to 582
  cases, bias +2.72.
- Verify: web typecheck, tests and build, then 5,064 API tests passed.
