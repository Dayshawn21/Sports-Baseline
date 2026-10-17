# 26d follow-ups: moneyline picks off, model page versions

**Type:** Fix

**Branch:** `fix/26d-follow-ups`

## The problem

Two loose ends from 26d (`blueprint/history/features/26d-market-anchored-ensemble.md`),
which started serving `ensemble-v3` on 2026-10-01.

1. **Moneyline best picks still fire, and the holdout says they lose.** The
   served blend is the close, slightly extremized. Betting its 3+ point gaps at
   the close lost 0.5% on 1,824 WTA picks and 2.2% on 7,504 Challenger picks;
   ATP never moves 3 points. `generate_ml_pick` still turns any positive-EV gap
   into a green moneyline play on the slate (`build_best_picks`) and on the
   match page (`match_detail.ml_pick`, which drives the green Moneyline EV tile).
2. **`/tennis/model`'s prediction sections are empty.** `DEFAULT_MODEL_VERSION`
   now follows `ENSEMBLE_VERSION`, so the page grades `ensemble-v3+lgbm-v6`
   only, and none has settled yet. The settled rows today are:

   | Version | Settled |
   |---|---|
   | `ensemble-v1+lgbm-v6` | 1,155 |
   | `ensemble-v1+lgbm-none` | 104 |
   | `ensemble-v1+lgbm-v5` | 94 |
   | `ensemble-v2+lgbm-none` | 68 |
   | `ensemble-v2+lgbm-v6` | 59 |

   The component table, calibration, CLV and the two prediction verdict cards
   all read "nothing yet" with no hint that older versions have a record or
   when v3 will fill in.

## The fix

**Step 1 - moneyline picks off.**
- A module constant in `app/services/tennis/best_picks.py`,
  `MONEYLINE_PICKS_ENABLED = False`, with a one-line why pointing at 26d.
- `build_best_picks` skips `generate_ml_pick` when it is off; derived,
  serve-edge and prop picks are unchanged.
- `match_detail` returns `ml_pick=None` when it is off, so the match page's
  Moneyline EV tile reads "—" and is never green (its existing no-pick path).
- `generate_ml_pick` itself stays pure and unchanged, so its tests and a later
  re-enable need no rewrite.

**Step 2 - model page grades any stored version.**
- `GET /tennis/model/predictions` takes an optional `model_version`, defaulting
  to `DEFAULT_MODEL_VERSION`. An unknown version is a 404 with a clear message.
- The response gains `versions`: each stored version with its settled count,
  served one first, then newest first. Built in the pure
  `build_prediction_grading` from rows already loaded, so no new query.
- The cache keys per version (`TimedSingleFlight.get(version, ...)`).
- The page shows a small version switch (Ant Design `Segmented` or `Select`)
  above the match-winner section, labeled with each version's settled count and
  marking the served one. The verdict cards and the three prediction sections
  follow the selection.
- When the served version has nothing graded, the empty states say so plainly:
  "`ensemble-v3+lgbm-v6` started serving 2026-10-01; no prediction has settled
  yet. Older versions are graded below the switch." No auto-switch: the default
  stays the served version, so the page never silently shows a retired model.

**Must not break:**
- The green rule: nothing new is colored; graded numbers keep
  `loss_signal` and `verdict_signal` exactly as today.
- The 26a CLI (`python -m app.backtest.tennis_predictions --model-version`)
  output, which shares `build_prediction_grading`.
- The 32b and 32a load-bearing contracts; `MatchDetailResponse.ml_pick` stays
  in the schema, just null.

**Out of scope:**
- The bankroll builder's own `_generate_ml_picks` (retired UI, open question 14).
- Derived picks that read `p1_win_prob` (2-0, three sets, win a set); they are
  unpriced and were not judged by 26d.
- `_overlay_live_moneyline`, which still fills displayed prices.
- Pooling versions together on the page.

## Build steps

- [x] **Step 1 - Turn off moneyline best picks.**
  - `MONEYLINE_PICKS_ENABLED = False` in `best_picks.py`; gate the call in
    `build_best_picks` and in `match_detail`.
  - Tests: `build_best_picks` on a priced prediction that `generate_ml_pick`
    would pick returns no `moneyline` pick; existing `generate_ml_pick` tests
    still pass; `test_match_detail` asserts `ml_pick is None` with a priced
    prediction.

  *Done when:* `pytest` passes, and `/tennis/predictions/best-picks` returns no
  `pickType: "moneyline"` entry while the slate still shows derived and prop
  picks; a match page with a price shows Moneyline EV "—", gray.

- [x] **Step 2 - Version switch on `/tennis/model`.**
  - API: `model_version` query parameter, `versions` list on
    `ModelPredictionsResponse`, per-version cache key, 404 on unknown.
  - Web: typed param in `src/api/tennis.ts`, `useModelPredictions(version)`
    with the version in its query key, a pure `versionOptions` helper in
    `src/utils/trackRecord.ts` (served first, counts in labels), the switch,
    and the served-version empty-state copy.
  - Tests: `build_prediction_grading` returns versions with counts in the
    stated order; the router-level default and 404 are covered by the service
    function test; `versionOptions` vitest.

  *Done when:* `pytest`, `npm run test` and `npm run build` pass; `/tennis/model`
  opens on `ensemble-v3+lgbm-v6` with the plain empty-state copy, and switching
  to `ensemble-v1+lgbm-v6` shows 1,155 settled rows, the component table,
  calibration, CLV and both prediction verdict cards, matching
  `python -m app.backtest.tennis_predictions --model-version ensemble-v1+lgbm-v6`.

## Verify

1. `cd api && .venv\Scripts\python.exe -m pytest`
2. `cd web && npm run test && npm run build`
3. Start the API and web, open `/` (no green moneyline best picks), a priced
   match page (Moneyline EV "—"), and `/tennis/model` (switch between v3 and
   v1, numbers match the CLI).

## Notes for the AI

- Standards: `X | None`, no `Any`, no em dashes, comment only the why, no UI
  text below 11px.
- Launch the API with the selector event loop on Windows (memory note).

## Results (2026-10-01)

- **Step 1:** on a fresh API, `/tennis/predictions/best-picks` returned 136
  derived and 90 prop picks across 73 matches and no moneyline pick (the old
  code returned 5). Match 83724, priced -175 / +141, returns `mlPick: null`.
- **Step 2:** `/tennis/model/predictions` defaults to `ensemble-v3+lgbm-v6`
  (0 graded); `?model_version=ensemble-v1+lgbm-v6` gives ATP+WTA n=308, market
  0.5255, ensemble 0.5316, identical to
  `python -m app.backtest.tennis_predictions --model-version ensemble-v1+lgbm-v6`;
  an unknown version is a 404. Screenshots showed the v3 note and the full v1
  record after switching, with no console errors.
- **Deviation from the spec:** the cache holds the loaded rows once, not one
  grading per version, so one database read serves every version and an
  arbitrary requested version cannot grow the cache.
- **Note:** the switch counts every settled row of a version (v1: 1,155); the
  tables grade fewer (1,121) after dropping retirements and walkovers.
- Checks: `pytest` 2,106 passed, `npm run test` 442 passed, `npm run build`
  passed.
