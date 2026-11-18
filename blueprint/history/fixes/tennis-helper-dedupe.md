# Fix: Dedupe the tennis pick helpers and split the long pick generators

**Type:** Fix

**Fixes:** F-72 (the `_normal_cdf` and `_f` part), F-73 (the best picks and bankroll generators)

**Branch:** `fix/tennis-helper-dedupe`

**Status:** complete 2026-11-17 (merged as PR #45, `79b68881`; archived 2026-11-17 because the merge left it unarchived)

## The problem

**F-72: two small helpers are copied.**

- `_normal_cdf(z)` exists twice, word for word:
  - `services/tennis/best_picks.py:83`
  - `core/prop_probs.py:54`
- `_f(v)` (a nullable `float()` coercion) exists three times:
  - `best_picks.py:61`
  - `prop_enrichment.py:91`
  - `core/prop_projection.py:85`

**F-73: four pick generators run 120 to 220 lines against the roughly 50-line guideline.**

| Function | Lines |
|---|---|
| `best_picks.generate_market_odds_picks` | 176 |
| `best_picks.generate_derived_picks` | 220 |
| `bankroll_builder._generate_set_picks` | 142 |
| `bankroll_builder._generate_total_picks` | 120 |

## The fix

### F-72

- **`core/prop_probs.py`:** `_normal_cdf` becomes the public `normal_cdf`. `best_picks` imports it and deletes its copy.
- **`core/prop_projection.py`:** `_f` becomes the public `opt_float`. `best_picks` and `prop_enrichment` import it and delete their copies. Every `_f(` call is renamed.

### F-73

Each split is code moved into named helpers with the same expressions, in the same order. No formula changes.

- **`generate_market_odds_picks`:** the per-prop loop stays and dispatches to `_total_games_picks(...)` and `_game_spread_picks(...)`.
- **`generate_derived_picks`:** the best-of-5 block, the best-of-3 set picks and the Serve Dominance pick each become a helper.
- **`_generate_set_picks`:**
  - the two price sources (set-handicap market, then moneyline-derived) move into one helper that returns the prices
  - the straight-sets pick and the underdog set pick each become a helper
- **`_generate_total_picks`:**
  - the expected-total projection becomes a helper
  - the OVER and UNDER blocks share one side helper, if they turn out to be symmetric when built; otherwise each becomes its own helper

### Out of scope

| Left alone | Why |
|---|---|
| `core/prop_projection.compute_stat_avg` | F-73 lists it, but it feeds props-v3 and the v4 shadow. Its unclamped expected-sets formula must not be swapped for `expected_sets_from_win_prob`. |
| `core/count_over_probability._normal_cdf(x, mean, sigma)` | A different signature |
| `ingest/elo._f` | Ingest is outside this lane |
| The rest of F-72: `_CamelModel`, the odds converters, the name folders, the web duplicates | Other files and other lanes |
| The ingest functions F-73 lists | Ingest is outside this lane |

### Must not break

- Every `BestPick` and `BankrollPick` these generators return: the same fields, the same order, the same floats.
- The props-v3 snapshots and the v4 shadow. `prop_enrichment` only renames its `_f` calls.

## Build steps

- [x] **1. Share the two helpers (F-72).**
  - Make `normal_cdf` and `opt_float` public, import them at each site, delete the copies.
  - Add tests that pin `normal_cdf` at a few `z` values and `opt_float` on `None`, `Decimal` and `int`.
  - Done when no `def _normal_cdf(z` or `def _f(` remains in `best_picks`, `prop_enrichment` or `prop_projection`, and the full API suite passes.
- [x] **2. Pin the four generators' output.**
  - Add golden tests on the unchanged generators that assert full dataclass equality. Cover:
    - total games and game spread props, including the skip guards
    - best-of-3 and best-of-5 derived picks, with and without Serve Dominance
    - set-handicap prices from the market and from the moneyline
    - total games OVER and UNDER
  - Done when the tests pass before any split.
- [x] **3. Split the two `best_picks` generators.**
  - Done when each function is at most about 60 lines and the step 2 tests pass unedited.
- [x] **4. Split the two `bankroll_builder` generators.**
  - Done when each function is at most about 60 lines, the step 2 tests pass unedited, and the full API suite passes.

## Verify

- `cd api && python -m pytest` passes.
- The step 2 golden tests pass without edits after steps 3 and 4.

## Completion evidence

- `tests/test_tennis_pick_generators_golden.py`: 53 golden cases plus 2 guard tests, written against the unsplit generators, compare full dataclass output to `tests/fixtures/tennis_pick_generators_golden.json`. A line trace confirmed every reachable statement is covered.
- The golden values pass unedited after steps 3 and 4. CI on Linux then differed from Windows in the last bits of the one unrounded float, `score` (`math.erf` differs between the C libraries), so `8b763e09` compares `score` alone at a 1e-12 relative tolerance; every rounded field still matches exactly.
- `tests/test_shared_prop_helpers.py`: 9 tests pinning `normal_cdf` and `opt_float`.
- Final function sizes: `generate_market_odds_picks` 37 lines, `generate_derived_picks` 44, `_generate_set_picks` 36, `_generate_total_picks` 39. Three `best_picks` helpers run 65 to 73 lines; accepted in review.
- Full API suite: 6553 passed; CI passed.
