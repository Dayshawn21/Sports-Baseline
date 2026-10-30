# Floor the remaining NFL history readers at 2024

**Type:** Fix
**Completed:** 2026-10-30
**Branch:** `fix/nfl-history-floor-remaining`

## The problem

`fix/nfl-v4-history-floor` floored every v4 and Rec Targets history read at
`PROJECTION_FIRST_HISTORY_SEASON` (2024) after the 2026-10-29 backfill of
2018-2023 NFL history. Three readers were left unbounded for an owner decision:

- `get_historical_player_baselines` (`/nfl/projections`): its career averages
  now include 2018-2023, while its TD and snap parts are already floored, so
  one response mixes floored and unfloored numbers. No web or Ask Lineform caller.
- `get_weekly_td_rows` and `get_snap_rows`: the anytime-TD backtest and the
  25c prop-market forward holdout. The report's model arm is meant to be the
  served anytime-TD model, which is now floored. Read-only comparison on
  2026-10-30: model log loss 0.44259 unbounded, 0.44263 floored; coverage and
  the common subset (1,764) unchanged. The 25c judgment is about one week away.

## The fix

- The same floor on all three reads, bound as `:first_history_season`.
- No version label, market or fitted constant changes. The anytime-TD backtest
  is not rerun: that would score the 2025 holdout again.

## Build steps

- [x] **Step 1 - floor the three reads.** Recorded-SQL tests that each carries
  the floor and binds the param.

## Done when

- `python -m app.backtest.nfl_prop_market` prints the floored report from the
  2026-10-30 comparison (model log loss 0.44263, common subset 1,764).
- Verify passes.

## Evidence

- `python -m app.backtest.nfl_prop_market` after the change: model log loss
  0.44263, common subset 1,764, book arms unchanged.
- Verify: web 66 test files and 988 tests passed and the build succeeded, then
  5,082 API tests passed. A later docstring-only edit reran
  `tests/test_nfl_repository.py` (94 passed).
- Not run: the anytime-TD backtest, which would score the 2025 holdout again.
