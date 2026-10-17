# Unreliable and missing ELO handling in the tennis ensemble

**Type:** Fix

## The problem

The ensemble in `app/services/tennis/ensemble.py` treats ELO badly at both
extremes:

- **Missing ELO:** the ELO weight is renormalized onto LightGBM and the market.
  For WTA that makes LightGBM about 75% of the blend, and 26a found LightGBM is
  the weakest component.
- **Unreliable ELO:** a present but stale or thin-sample TennisAbstract ELO is
  trusted at full weight. Challenger has no ML, so ELO is two-thirds of the
  blend there. On the 2026-09-28 board, every model-vs-market gap of 10+ points
  had ELO present (Xinyu Wang: ELO 74%, market 23%, shown as +131.6% EV).

**Evidence** (settled predictions, `ensemble-v1+lgbm-v6`, graded 2026-09-28;
paired log loss vs market, positive = worse than market):

| Slice | n | ELO vs market | Ensemble vs market |
|---|---|---|---|
| ATP/WTA, ELO missing | 27 | - | +0.030 +/- 0.030 |
| Challenger, ELO missing | 171 | - | +0.022 +/- 0.017 |
| ELO present, either player < 10 prior matches | 103 | +0.062 +/- 0.029 | +0.025 +/- 0.017 |
| ELO present, both players 10+ prior matches | 599 | about +0.018 | about +0.003 |
| ELO present, abs(ELO - market) >= 0.15 | 97 | - | +0.030 +/- 0.023 |

When ELO disagreed with the market by 20+ points (n=40), ELO's side won 42.5%;
the market said 44.9% and ELO said 70.3%.

## The fix

1. **Missing ELO gives its weight to the market**, not across ML and market.
   Only when the market is also missing do the remaining weights renormalize as
   today.
2. **Unreliable ELO is treated as missing** (weight to the market) and flagged
   `elo_unreliable`. ELO is unreliable when either:
   - `abs(elo_prob - market_prob) >= 0.15`, or
   - either player has fewer than 10 prior completed matches (the `experience`
     value from `HistoryIndex.form`, the same count the evidence used).
   Thresholds are fixed here, from the evidence above, and not tuned further.
3. **`elo_unreliable` blocks a bettable pick.** `assess_bettable_pick` returns
   None when the flag is present, so the match never ranks as a moneyline pick.
   Total-games and game-spread picks derived from the match are not blocked:
   they read the v2 win probability, which already excludes the unreliable ELO,
   and there is no evidence yet that they grade worse (decided 2026-09-28).
   `elo_missing` stays a downgrade flag, as today.
4. **Model version bumps** from `ensemble-v1` to `ensemble-v2` in
   `app/ingest/predictions.py`, so 26a grading never pools the two blends. The
   `tennis_predictions` backtest default stays on v1 until v2 accrues;
   `--model-version` reads v2.

**Must not break:**
- `elo_prob` is still stored and returned for display even when flagged, so the
  detail panel shows what ELO said.
- `core/` purity: the reliability rule is a pure function.
- Tour base weights, market stale/overround multipliers, and ML handling are
  unchanged.
- Tennis prop projections (`props-v2`) read `p1_win_prob`; their version is not
  bumped because this is a moneyline blend change, but note it in the archive.

## Build steps

- [x] **Step 1 - blend.** In `ensemble.py`, add `elo_unreliable: bool` to
  `EnsembleInput`, and a pure `elo_is_unreliable(elo_prob, market_prob,
  min_prior_matches)` with the two thresholds as named constants. In `blend`,
  missing or unreliable ELO moves its base weight to the market when the market
  is present, and emits `elo_unreliable` when flagged.
  **Done when:** `tests/test_ensemble.py` covers missing ELO with market present
  (weights are ML plus market-plus-ELO base), missing ELO and market (renormalize
  as today), unreliable ELO (same weights as missing, flag emitted, `elo_prob`
  echoed), and both threshold edges of `elo_is_unreliable`; `pytest` passes.
- [x] **Step 2 - serving.** In `predictor.py`, both `predict_match` and
  `_build_prediction` compute the min prior-match count from the history index
  and pass `elo_unreliable` into the blend. Bump the ingest model version to
  `ensemble-v2`.
  **Done when:** a replay of the new blend over the settled graded rows
  (stored ELO, ML and market probabilities plus reconstructed prior-match
  counts) shows the ensemble-vs-market log-loss gap no worse than v1 overall and
  smaller in the missing and unreliable slices; `pytest` passes.
- [x] **Step 3 - bettable gate.** In `app/core/bettable_criteria.py`, a
  blocking flag set holding `elo_unreliable`; `assess_bettable_pick` returns
  None when any is present.
  **Done when:** `tests/test_bettable_criteria.py` covers the block and that
  `elo_missing` still only downgrades; `pytest` passes.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest`
- `cd web && npm run build` (no web change expected; confirms nothing broke)
- Re-run predictions for today and open `/#/tennis/board` with Market odds:
  the Xinyu Wang, Andre Ilagan, Hugo Grenier and Billy Harris cards are gone,
  and the detail panel for an affected match still shows its ELO probability.

## Result (2026-09-28)

- `pytest`: 1805 passed (20 new tests). `npm run build` passes.
- **Replay of the v2 blend over 900 settled v1 predictions** (paired log loss vs
  market, positive = worse; in-sample, because the thresholds were chosen from
  the same rows):

  | Slice | n | v1 | v2 |
  |---|---|---|---|
  | All | 900 | +0.0105 +/- 0.0054 | +0.0036 +/- 0.0042 |
  | ELO missing | 198 | +0.0234 | +0.0107 |
  | ELO unreliable | 183 | +0.0236 | +0.0029 |
  | ELO trusted | 519 | +0.0009 | +0.0012 |

- **Live read-only run for 2026-09-28/29:** 30 of 114 predictions flagged
  `elo_unreliable`. Xinyu Wang (ensemble 0.55 to 0.35), Andre Ilagan, Hugo
  Grenier and Billy Harris are all flagged and produce no moneyline pick. Five
  moneyline picks remain, the largest +15.3% EV (the board had shown +131.6%).
- **Not changed:** `props-v2` was not bumped, though tennis prop projections
  read `p1_win_prob`. The `tennis_predictions` backtest default stays on
  `ensemble-v1+lgbm-v6`; grade v2 forward with
  `--model-version ensemble-v2+lgbm-v6`.
- **Still open:** v2 does not beat the market; its 10+ point picks in the replay
  won 31.6% against a market 29.9% and a model 42.8%. Item 26d remains the real
  fix.
