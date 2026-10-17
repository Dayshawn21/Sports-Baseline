# NFL projection model

**Type:** Feature
**From build-plan:** 19e

**Status:** complete

## Goal

Replace NFL player-prop season averages with an explicit, testable projection
that weights recent performance, regresses thin samples toward a position-market
baseline, and adjusts its confidence using the de-vigged game moneyline from
19f. Surface the model result and market-input status on the existing NFL slate.

## In scope

- A pure per-player projection function with documented, deterministic inputs.
- Game moneyline lookup and a conservative market adjustment that never invents
  a probability when no fresh odds exist.
- Repository aggregation for recent player games and position-level fallback.
- Existing `/nfl/slate` response fields and UI labels for model projection,
  model version, and quality flags.

## Out of scope

- Training LightGBM/XGBoost, backtesting profitability, or changing PrizePicks
  ingest. Those need a labeled NFL results history and are separate work.
- Modeling spread or total markets, individual defensive matchups, injuries, or
  projections for non-full-game lines.
- Generalizing the model to NBA/WNBA or modifying the cross-sport foundation.

## Data contract

- `NflProjectionInput` is pure and contains recent games, position baseline,
  player sample size, and optional home moneyline probability.
- `market_missing` and `market_stale` are explicit flags. A missing or stale
  market never changes a player projection.
- `projectionModelVersion` is returned per slate line. The initial value is a
  named constant, not an implicit behavior change.

## Build steps

- [x] **Step 1 - Define and test the pure projection contract.** Add a pure
  weighted-recent projection with regression to a position baseline for small
  samples, plus an optional conservative home/away market adjustment.  
  *Done when:* table-driven tests cover adequate sample, small sample, missing
  market, stale market, home and away orientation, and deterministic rounding.

- [ ] **Step 2 - Supply model inputs through repositories.** Fetch recent
  regular-season player stats, position baselines, and the newest moneyline
  snapshot per slate game without N+1 queries.  
  *Done when:* a repository test or focused database fixture proves the latest
  moneyline is selected and absent odds remain nullable.

- [x] **Step 3 - Replace baseline use on the NFL slate.** Wire the model into
  `_slate_line`, retain the existing edge gate for unsupported or thin lines,
  and carry model version and market status through schema and UI types.  
  *Done when:* a supported full-game line shows the model projection and flags;
  a missing-market line still renders without a fabricated adjustment.

- [x] **Step 4 - Verify the slate end to end.** Run focused and full API tests,
  web tests/build, and inspect the running NFL slate against one current game
  with odds and one without.  
  *Done when:* model version, projection, and honest market flags are visible
  and no existing unmatched or unsupported states regress.

## Files / areas

| Path | Change |
|---|---|
| `api/app/core/nfl_projection.py` | Pure model and flags. |
| `api/app/repositories/nfl.py` | Batched recent-stat and latest-moneyline inputs. |
| `api/app/routers/nfl.py`, `api/app/schemas/nfl.py` | Slate model output contract. |
| `web/src/pages/NflIntelligencePage.tsx`, `web/src/types/nfl.ts` | Model status display. |
| `api/tests/test_nfl_projection.py` | Pure model and input behavior. |

## Testing

- Add focused `pytest` coverage for all projection math and flags.
- Mock database/provider boundaries; no live provider request is required.
- Run API tests, web tests, and web build before review.

## Notes for the AI

- Keep model math in `core/`; repositories own SQL.
- The market probability is a calibration input, not a substitute for a player
  prop probability. Keep its effect bounded and observable.
- Preserve current baseline fields until the model output is proven in the slate.
