## Bankroll Builder: cached predictions, bounded limits, one surface-stats rule

**Type:** Fix
**Fixes:** F-23, F-24

### The problem

- **F-23.** `build_bankroll_picks` (`api/app/services/tennis/bankroll_builder.py:566`)
  calls `predict_today` directly, so every `/tennis/bankroll/today` and
  `/tennis/parlays/suggested` request rebuilds features and runs inference
  (about 20 s locally). Best picks already share predictions through
  `prediction_cache.cached_predictions`. `max_singles` and `max_parlays`
  (`routers/tennis.py:508`) are unbounded ints, and the live-moneyline overlay
  failure is swallowed with `except Exception: pass`.
- **F-24.** Three copies of "surface stats, or all-surface when the sample is
  small" have drifted: `routers/props.py:641` (`_SMALL_SAMPLE_MATCHES = 10`),
  `services/tennis/best_picks.py:178` (hardcoded 10), and the inline
  `bankroll_builder.py:613`, which takes surface stats whenever any exist.

### The fix

- Builder takes `registry`, `match_date: date | None` and `today`, and gets
  predictions from `best_picks_response.slate_predictions` (the cached path).
  A failed build raises `PredictionsUnavailable`; the router turns it into the
  same 503 the other slate routes return. `cached_predictions` hands each caller
  a deep copy, so the in-place overlay stays safe.
- `max_singles: Query(15, ge=1, le=50)`, `max_parlays: Query(10, ge=1, le=20)`.
  The web sends neither, so defaults are unchanged.
- The overlay failure logs a warning with the traceback and the build continues
  (unchanged behavior, now visible).
- `/tennis/parlays/suggested` delegates to the bankroll route, so it gets the
  cache and the 503 with no separate change.
- New pure helper `app/core/rolling_stats.py`: `SMALL_SAMPLE_MATCHES = 10` and
  `pick_stats_for_player(player_id, surface, all_stats)`. Props (selection and
  its `small_sample` flag), best picks, prop sim and bankroll all use it; the
  local copies go.

**Behavior change (F-24):** Bankroll total-games picks now project from
all-surface stats when the surface sample has fewer than 10 matches, matching
the props board and best picks. Some Bankroll totals picks will change or drop.

Must not break: best picks output, the props board, prop sim, the response
shape of both bankroll routes.

### Build steps

- [x] **1. Shared stats helper (F-24).** Add `app/core/rolling_stats.py`; switch
  props, best picks, prop sim and bankroll to it; unit tests for the threshold
  (9 falls back, 10 takes surface, missing surface falls back, `None` player).
  Done when: no other `matches_count ... >= 10` selection copy remains and the
  tests pass.
- [x] **2. Cached predictions, limits, logging (F-23).** Route the builder
  through `slate_predictions`, bound the two limits, log the overlay failure;
  route tests: over-limit values return 422, a prediction failure returns 503,
  and the builder reads predictions through the cache.
  Done when: Verify passes and a second local `/tennis/bankroll/today` within
  5 minutes is served from the cache (before/after timing recorded).

### Verify

- `npm --prefix web run verify && cd api && python -m pytest`
- Local read-only timing: two `/tennis/bankroll/today` calls before and after.

## Findings

### bankroll-cached-predictions/F-23 [P2] closed - Bankroll Builder rebuilds every tennis prediction per request

**File:** api/app/services/tennis/bankroll_builder.py:566
**Found:** 2026-11-06 by /audit (scope: full; lens: performance)
**Why it matters:** it calls `predict_today` directly instead of `prediction_cache.cached_predictions`, which best picks uses, so each request repeats the feature build and inference on the 512 MB instance; `/tennis/parlays/suggested` does the same. `max_singles` and `max_parlays` are unbounded (`routers/tennis.py:508`), and an overlay failure is swallowed with `except Exception: pass` (`:576-579`). Latency on the host is unmeasured.
**Suggested fix:** route through `cached_predictions`, bound both limits with `Query(le=...)`, and log the overlay failure.
**Resolution:** closed by /audit (scope: current) on 2026-11-06. `build_bankroll_picks` reads `best_picks_response.slate_predictions` (the `cached_predictions` path; dates outside the cache window still compute directly, as best picks does), and a failed build is the shared 503. `max_singles` is `Query(ge=1, le=50)`, `max_parlays` `Query(ge=1, le=20)`; the web sends neither. The overlay failure logs a warning with the traceback. `/tennis/parlays/suggested` delegates, so it shares all of it. Tests: `tests/test_bankroll_builder_cache.py`. Local read-only timing, overlay stubbed: warm request 0.83 s before, 0.13 s from the cache (28 matches).

### bankroll-cached-predictions/F-24 [P2] closed - Bankroll totals use surface stats from any sample; the board and best picks need 10 matches

**File:** api/app/services/tennis/bankroll_builder.py:613; api/app/routers/props.py:649; api/app/services/tennis/best_picks.py:185
**Found:** 2026-11-06 by /audit (scope: full; lens: quality)
**Why it matters:** three copies of the stats selection have drifted. Props and best picks use surface stats only when `matches_count >= 10` (one named, one hardcoded), but bankroll takes surface stats whenever any exist, so its total-games picks can project from a one or two match surface sample the other views reject.
**Suggested fix:** one shared helper with one constant, used by all three.
**Resolution:** closed by /audit (scope: current) on 2026-11-06. `app/core/rolling_stats.py` holds `SMALL_SAMPLE_MATCHES = 10` and `pick_stats_for_player`, used by props (selection and the `small_sample` flag), best picks, prop sim, the Bankroll Builder and the player-stats route's fallback. Bankroll totals now need 10 surface matches, like the other views; today's slate had no total-games candidates under either rule, so no change was observed. Tests: `tests/test_rolling_stats.py`.
