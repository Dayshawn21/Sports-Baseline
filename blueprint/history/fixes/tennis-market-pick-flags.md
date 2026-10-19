# Current Feature

## Apply prediction flags to tennis Total Games and Game Spread picks

**Type:** Fix
**Branch:** `fix/tennis-market-pick-flags`

### The problem

- `generate_market_odds_picks` in `api/app/services/tennis/best_picks.py`
  builds the two priced, book-odds picks, Total Games and Game Spread, from
  the match prediction (`pred.p1_win_prob`) and rolling stats.
- It calls `assess_bettable_pick(prob, ev, kelly, odds_source="posted")`
  (lines 343 and 410) without `data_quality_flags`, unlike the moneyline pick
  (`generate_ml_pick`, line 152), which passes `pred.quality_flags`.
- So the prediction's warnings never reach these picks:
  - `elo_unreliable` does not block them, although the rule says no tier is
    safe to show when ELO and the market disagree that much.
  - `stale_odds`, `market_missing`, `elo_missing`, `p1_elo_missing` and
    `p2_elo_missing` do not lower their tier.
  - The pick's `data_quality_flags` is empty, so the card shows no warning.
- These are live picks: Total Games and Game Spread appear in the prop bucket
  of `/tennis/predictions/best-picks` whenever a book line is stored.

### The fix

1. Pass `data_quality_flags=pred.quality_flags or []` into both
   `assess_bettable_pick` calls in `generate_market_odds_picks`, the same
   source `generate_ml_pick` uses. The picks already copy
   `assessment.data_quality_flags`, so the flags then show on the card.
2. Tests in `api/tests/test_best_picks_live_odds.py`, on the existing
   fixtures: a STRONG Total Games or Game Spread pick drops to LEAN with
   `stale_odds`, is dropped with `elo_unreliable`, keeps its tier with
   `ml_missing`, and carries the flags in `data_quality_flags`.

**Must not break:**
- No probability, EV, edge or score changes; only tiers, flags shown, and
  picks removed by `elo_unreliable`.
- `generate_prop_picks` (PrizePicks lines) keeps the board's own flags and
  tier, never recomputed.
- `SPORT_STATUS` on How it works is unchanged: these picks stay on.

**Out of scope:**
- Unpriced derived and serve-edge picks (set score, total sets, win a set,
  serve dominance, serve edge). Their tier is not validated (finding F-09,
  "do not retune"), so they stay as they are; decided 2026-10-18.
- Which flags belong in `_DOWNGRADE_FLAGS` (settled by fix
  `tennis-ml-tier-flags`).

### Build steps

- [x] **1. Pass the flags and test it.** Edit both calls and add the tests
  above.
  *Done when:* `grep -n "assess_bettable_pick(prob, ev, kelly, odds_source" api/app/services/tennis/best_picks.py`
  finds nothing, and the new tests pass.

### Verify

- Run the Verify command (`npm --prefix web run verify && cd api && python -m pytest`).
- On today's `/tennis/predictions/best-picks`, a Total Games or Game Spread
  pick on a match with `stale_odds` (or any downgrade flag) now reads one tier
  lower and lists the flag; a match flagged `elo_unreliable` shows none.
