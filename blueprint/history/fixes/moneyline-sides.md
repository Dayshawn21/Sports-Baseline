# Fix: Share one moneyline side calculation between best picks and the bankroll builder

**Type:** Fix

**Fixes:** F-61

**Branch:** `fix/moneyline-sides`

**Status:** complete 2026-11-17 (merged as PR #44, `d00d2489`; archived 2026-11-17 because the merge left it unarchived)

## The problem

Two functions derive the same moneyline numbers independently:

- `best_picks.py` `generate_ml_pick` (lines 101-176)
- `bankroll_builder.py` `_generate_ml_picks` (lines 138-193)

Both check the same inputs, de-vig the two prices, and compute EV, Kelly and the
bettable assessment for each side.

Around that shared core:

- `bankroll_builder.py:34` imports two privates from `best_picks`:
  - `_compute_stat_avg`, which is just an alias of `core.prop_projection.compute_stat_avg`
  - `_CONF_MULT`
- Both read `getattr(pred, "quality_flags", [])`, even though
  `PredictionOutput.quality_flags` is a declared field.
- American odds are formatted twice: inline at `best_picks.py:143`, and in
  `bankroll_builder.py:114` as `_odds_str`.

## The fix

### `app/services/tennis/moneyline.py` (new, pure, no I/O)

- **`MoneylineSide`**, a frozen dataclass with:
  - `side`: `"p1"` or `"p2"`
  - `name`, `our_prob`, `market_prob` (de-vigged), `odds`, `ev`, `kelly`
- **`moneyline_sides(pred) -> tuple[MoneylineSide, MoneylineSide] | None`**
  - Returns `None` on the same guard both callers use today: no `p1_win_prob`
    or a missing price.
- **`odds_str(odds: int | None) -> str`**
  - Gives `"+120"` or `"-130"`, and `"N/A"` for `None`.
  - Replaces both copies.

### `best_picks.py`

- `generate_ml_pick` gets its side numbers from `moneyline_sides`.
- `_CONF_MULT` becomes the public `CONF_MULT`.

### `bankroll_builder.py`

- `_generate_ml_picks` gets its side numbers from `moneyline_sides`.
- It imports `compute_stat_avg` from `core.prop_projection` and `CONF_MULT` from `best_picks`.
- Every `_odds_str` call (ML, sets and totals) uses the shared `odds_str`.

### Both callers

- Read `pred.quality_flags or []` directly.

### Kept exactly as is (the two callers differ on purpose)

| | Best picks | Bankroll builder |
|---|---|---|
| Sides returned | One: the higher-EV side, with ties going to p2 | Both sides that pass the assessment |
| Edge | `(our - mkt) / mkt` | `(our - (mkt or our)) / max(mkt or our, 0.01)` |
| p2 market prob | `1 - market_p1` | `market_p2` from `devig_two_way` |

- Best picks keeps its `1 - market_p1` line, so its output does not move by a
  float ulp.
- Changing either edge formula needs an explicit choice from the user. It is not
  part of this fix.

### Must not break

- Every field of `BestPick` and `BankrollPick` that these two functions produce.
- The tennis props-v3 snapshots and the v4 shadow. Neither reads this code.

## Build steps

- [x] **1. Pin today's output.**
  - Add golden tests on the unchanged code for both functions:
    - p1 has more EV
    - p2 has more EV
    - an EV tie
    - both sides pass (bankroll)
    - neither side passes
    - a blocking quality flag
    - a missing price
  - The tests assert full dataclass equality.
  - Done when they pass on the unchanged code.
- [x] **2. Extract and switch.**
  - Add `moneyline.py` with tests for `moneyline_sides` and `odds_str`.
  - Point both callers at it.
  - Make `CONF_MULT` public, fix the `compute_stat_avg` import, and drop the
    `getattr` calls.
  - Done when the step 1 golden tests pass unchanged, no module imports a
    `best_picks` private, and the full API suite passes.

## Verify

- `cd api && python -m pytest` passes.
- The golden tests from step 1 pass without edits after step 2.

## Completion evidence

- `tests/test_moneyline_golden.py` (9 cases, full dataclass equality for both callers) was written and passing on the old code, and passes unedited after the move.
- `tests/test_moneyline.py` covers the new `services/tennis/moneyline.py` (10 tests).
- Full API suite: 6488 passed; CI passed.
- The tennis props-v3 snapshots and the v4 shadow do not read this code.
