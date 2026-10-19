# Current Feature

## Stop ML flags from lowering tennis pick tiers

**Type:** Fix
**Branch:** `fix/tennis-ml-tier-flags`

### The problem

- `_DOWNGRADE_FLAGS` in `api/app/core/bettable_criteria.py` drops a pick one
  tier (LOCK to STRONG, STRONG to LEAN) when any listed flag is present.
- Two listed flags name an input the served model no longer uses:
  - `ml_missing` and `ml_not_trained_for_tour`. `ensemble-v3` gives v6
    LightGBM no weight on any tour (26d), so a missing ML probability changes
    nothing about the served probability. Every Challenger and WTA 125 match
    carries both (they are stored as `CHALLENGER`, which v6 does not serve).
  - When there is no market price, the frozen `ensemble-v2` path does use ML,
    but that row also carries `market_missing`, which still downgrades. A pick
    drops at most one tier, so removing the ML flags changes nothing there.
- Two listed names are raised by no tennis code, so they silently do nothing
  (the file's own comment warns about this):
  - `market_stale` is NFL's name; tennis raises `stale_odds`, which stays.
  - `fallback_stats` is emitted nowhere.
- **Live impact today is nil.** Only the moneyline best pick (off,
  `MONEYLINE_PICKS_ENABLED = False`) and the bankroll builder's moneyline
  singles (API only, hidden from nav) pass a prediction's flags into
  `assess_bettable_pick`. Derived picks pass none. This fix makes the rule
  correct before moneyline picks are ever re-enabled.

### The fix

1. Remove `ml_missing`, `ml_not_trained_for_tour`, `market_stale` and
   `fallback_stats` from `_DOWNGRADE_FLAGS`. Keep the flags on predictions:
   the match page reads `ml_not_trained_for_tour`, and the admin queue and
   stored `quality_flags` keep them.
2. Update `api/tests/test_bettable_criteria.py`:
   - `test_missing_model_inputs_downgrade_strong_to_lean`: drop the two ML
     flags from its parameters.
   - `test_every_missing_input_the_blend_reports_is_a_downgrade_flag`: expect
     `ml_missing` to be the one missing input that does not downgrade, with a
     one-line reason (v3 gives ML no weight).
   - New: `ml_missing` and `ml_not_trained_for_tour` leave a STRONG pick
     STRONG, like the existing `ml_features_partial` test.
   - New: every name in `_DOWNGRADE_FLAGS` and `_BLOCKING_FLAGS` appears as a
     string literal in a tennis flag source (`app/services/tennis/`,
     `app/routers/props.py`, `app/core/bettable_criteria.py` for
     `imputed_odds`), so an orphan name fails the suite.

**Must not break:**
- No probability, EV or pick list changes. Tier changes are possible only on
  the bankroll builder's moneyline singles for Challenger and WTA 125 matches.
- `elo_unreliable` still blocks; `elo_missing`, `p1_elo_missing`,
  `p2_elo_missing`, `market_missing`, `stale_odds`, `small_sample`,
  `stale_stats` still downgrade.
- `SPORT_STATUS` on How it works is unchanged: no sport's picks change.

**Out of scope:**
- WTA 125 blend coefficients (today the Challenger fit). Changing them is a
  model change that needs a pre-registered backtest, so it would be its own
  build-plan item.
- Derived picks ignoring prediction flags entirely (`stale_odds`,
  `elo_missing` never downgrade them). Noted for a separate decision.

### Build steps

- [x] **1. Downgrade list and tests.** Edit `_DOWNGRADE_FLAGS` and
  `test_bettable_criteria.py` as above.
  *Done when:* `grep -n "ml_missing\|ml_not_trained_for_tour\|market_stale\|fallback_stats" api/app/core/bettable_criteria.py`
  finds nothing, and the orphan-name test fails if `"fallback_stats"` is put
  back (checked by hand, then reverted).

### Verify

- Run the Verify command (`npm --prefix web run verify && cd api && python -m pytest`).
- `/tennis/predictions/best-picks` returns the same picks and tiers as before
  for today's slate (derived picks pass no prediction flags).
