# Tennis model input integrity

**Type:** Fix

## The problem

The tennis review (2026-09-25) found three serving bugs that change live
predictions and pick confidence:

1. **Missing features are encoded differently at serving and training.**
   `build_features` starts from `FILL_DEFAULTS`
   (`api/app/services/tennis/feature_builder.py:74`), which puts 0.0 in
   `d_rank_log`, `d_age`, `d_elo` and `d_surface_elo`. The v6 training export
   stores those as None, which becomes NaN (`api/train_model.py:281-306`).
   - An unknown rank is therefore served as "equal rank".
   - `d_rank_log` is a top-3 v6 feature and is missing in about a quarter of
     rows.
2. **Men's Challenger matches get the WTA model.**
   - `ModelRegistry.predict_lgbm` and `get_lgbm_version` route every non-ATP
     tour to the WTA bundle (`api/app/ml/registry.py:159,173`).
   - v6 was trained on ATP and WTA only (`api/train_model.py:127`).
3. **Quality flags never lower pick confidence.**
   - `_DOWNGRADE_FLAGS` (`api/app/core/bettable_criteria.py:13`) lists
     `missing_market`, `no_ml_model`, `no_elo`, `low_feature_quality` and
     `market_stale`, and no code emits any of them.
   - The ensemble and feature builder actually emit `market_missing`,
     `ml_missing`, `elo_missing`, `p1_elo_missing` and `p2_elo_missing`.
   - Only `stale_odds` matches, so a moneyline pick with no ML model or
     one-sided ELO keeps its full LOCK/STRONG tier.

Two related problems:
- The ensemble cuts ML weight by 20% on `ml_features_partial`
  (`api/app/services/tennis/ensemble.py:62`). That flag means "TennisAbstract
  rolling stats missing", and v6 uses none of those features.
- `predict_today` drops any match that raises, without logging
  (`api/app/services/tennis/predictor.py:382`).

## The fix

- Stop seeding defaults for the model features that training leaves missing
  (`d_elo`, `d_surface_elo`, `d_rank_log`, `d_age`).
  - Name that set once in `api/app/ml/feature_contract.py`.
  - The registry's declared NaN fill then applies, matching training.
- Serve ML only for the tours a bundle was trained on (ATP, WTA).
  - Other tours get no ML probability and a new `ml_not_trained_for_tour` flag.
  - The ensemble then renormalizes over ELO and market.
- Align `_DOWNGRADE_FLAGS` with the flags actually emitted, and add
  `ml_not_trained_for_tour`.
  - Keep the prop flags already in the set (`small_sample`, `stale_stats`,
    `stale_odds`, `fallback_stats`).
  - Drop the names nothing emits.
- Remove the ML weight penalty for `ml_features_partial`.
  - Keep the flag itself: `/admin` and `web/src/pages/AdminPage.tsx` use it to
    mean "player lacks stats".
- Log, with the match id, any match `predict_today` skips.

**Must not break:**
- Flag names: `/admin`, the admin page and `qualityFlags.ts` read them.
- The persisted `feature_snapshot` shape: keys may now be absent, which the
  snapshot already allows.
- ATP and WTA predictions whose inputs are complete must not change.

**Out of scope, noted by the review:**
- The substring `is_grand_slam` and `tournament_tier` in `feature_contract.py`
  (training used the same code). Fixing them only at serving would create new
  skew. Fold them into the retrain (review item 8).

## Build steps

1. [x] **Serve the trained missing-value encoding and route ML by tour.**
   - Add the no-default feature set.
   - Make the registry return None for non-ATP/WTA tours; the predictor adds
     `ml_not_trained_for_tour`.
   - Log skipped matches in `predict_today`.
   - Tests:
     - `build_features` with a missing rank and a missing birth date leaves
       `d_rank_log` and `d_age` absent.
     - `predict_lgbm` returns None for CHALLENGER.
   - Done when these tests pass. A local `python -m app.ingest.predictions`
     run then stores no `d_rank_log` key for a match with an unranked player,
     and a Challenger match has a null ML probability and the new flag.
2. [x] **Make quality flags lower confidence, and drop the irrelevant ML penalty.**
   - Align `_DOWNGRADE_FLAGS`.
   - Remove the `ml_features_partial` weight multiplier in `ensemble.py`.
   - Tests:
     - `assess_bettable_pick` downgrades STRONG to LEAN for `ml_missing`,
       `elo_missing` and `ml_not_trained_for_tour`.
     - Every flag `blend` can emit that signals a missing input is in the
       downgrade set.
     - `blend` gives the same weights with and without `ml_features_partial`.
   - Done when these tests pass, and a best-picks moneyline pick on a match
     flagged `ml_missing` or `ml_not_trained_for_tour` shows a tier no higher
     than LEAN.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest`
- `cd web && npm run build`, since flag labels are read client-side.
- Start the API. On `GET /tennis/predictions/today`, a Challenger match shows:
  - `p1_ml_prob: null`
  - `ml_not_trained_for_tour` in its flags
  - ensemble weights over ELO and market only
- On `GET /tennis/predictions/best-picks`, no moneyline pick on such a match is
  rated STRONG or LOCK.
- On `/admin`, flagged players still list their ELO and stats flags as before.

## Completion evidence

- `cd api && .venv\Scripts\python.exe -m pytest` passed, 1163 tests.
- `cd web && npm run build` passed.
- `GET /tennis/predictions/today` for 2026-09-25 and 26: all 12 ATP and 7 WTA
  matches carry an ML probability; all 27 CHALLENGER matches (18 men's, 9
  WTA 125) have a null ML probability, `ml_not_trained_for_tour`, and ELO plus
  market weights only.
- In-process `predict_today` then `generate_ml_pick` (the best-picks endpoint
  was skipped because it spends Odds-API.io quota per request): all five
  moneyline picks on flagged matches graded LEAN. Two of them, Clarke +100
  (30.8% EV) and Angelo -139 (10.6% EV), would have graded STRONG without the
  downgrade.
- `GET /admin/players/flagged` still lists ELO and `ml_features_partial` flags.
- The stored-row check from step 1 (`python -m app.ingest.predictions`) was
  covered by unit tests instead of a live write.
