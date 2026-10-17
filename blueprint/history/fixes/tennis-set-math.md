# Tennis set and total-games math

**Type:** Fix

## The problem

The tennis review (2026-09-25, item 5) flagged the set-count math. Measuring it
against real results changed both the diagnosis and the fix.

**Measurement:** 4,680 completed best-of-3 matches with a clean score (no
retirements or walkovers) and a pre-start moneyline, de-vigged, from
2026-03-12 to 2026-09-25.

| Favorite's win prob | 3 sets, actual | `2p(1-p)` (current) | Favorite 2-0, actual | `p²` (current) |
|---|---|---|---|---|
| 0.5 to 0.6 | 0.400 | 0.493 | 0.341 | 0.306 |
| 0.6 to 0.7 | 0.382 | 0.455 | 0.437 | 0.420 |
| 0.7 to 0.8 | 0.323 | 0.376 | 0.566 | 0.559 |
| 0.8 to 0.9 | 0.262 | 0.257 | 0.652 | 0.719 |
| 0.9 to 1.0 | 0.189 | 0.137 | 0.789 | 0.857 |

1. **The set-count formulas are miscalibrated.**
   - `2p(1-p)` overstates 3-setters in close matches and understates them in
     lopsided ones.
   - On the holdout it scores worse than a constant base rate.
   - The review's proposed alternative, per-set independence with
     `p = s²(3-2s)`, doubles the error, because sets are correlated.
   - The formulas are used in:
     - derived set picks (`api/app/services/tennis/best_picks.py:667,685`)
     - the total-games mixture weight (`best_picks.py:381`,
       `api/app/routers/props.py:82`,
       `api/app/services/tennis/bankroll_builder.py:375`)
     - imputed set-handicap odds (`bankroll_builder.py:240`)
   - `expected_sets_from_win_prob` (`api/app/core/tennis_props.py:24`) uses the
     same formula, but it stays. Every game-based prop projection is built on
     it, and those projections' coefficients (the 0.917 scaling in
     `expected_total_games_from_matchup` and `_DOWNSTREAM_GAMES_CALIBRATION`)
     were fitted to market lines on top of it. Changing it alone would shift
     every projection about 3% without refitting them. It belongs with the prop
     projection rework, measured against settled prop results (review item 6).
2. **Book total-games lines are graded against themselves.**
   - When a sportsbook total exists, `expected_total_games` returns that line as
     the projection (`api/app/core/prop_projection.py:125`).
   - `generate_market_odds_picks` then prices the same book's total-games line
     against it (`best_picks.py:363-383`).
   - Any "edge" there comes only from the mixture's asymmetry, not from a view
     of the match.
   - PrizePicks total-games props are different: grading a PrizePicks line
     against the sportsbook total is a real comparison, and stays.
3. **A prop's side and its probability can disagree.**
   - `recommendation` comes from mean versus line (`routers/props.py:286`), and
     `generate_prop_picks` picks its direction the same way (`best_picks.py:252`).
   - The confidence uses the higher-probability side (`routers/props.py:322`).
   - For a skewed count distribution near the line, these point opposite ways.
4. **Unpriced picks can push the priced moneyline pick out.**
   - `build_best_picks` ranks the moneyline pick, derived set picks and
     serve-edge picks in one top-3 bucket by score (`best_picks.py:786`).
   - Derived and serve-edge "edges" are measured against hardcoded baselines,
     so they are not comparable to a priced EV.

**Measured and left alone:** the game-spread spread (Skellam variance,
sd ≈ 4.7 games).
- On the holdout, the actual margins spread out about as much as the model
  assumes: a z-score standard deviation of 1.013 overall and 1.056 for close
  matches.
- An odds-fitted sd scored 0.978 and 0.951, no better.

## The fix

- Add a pure `app/core/` helper for best-of-3 set counts, fitted by least
  squares on the earliest 70% of matches (3,276, 2026-03-12 to 2026-05-18) and
  checked on the latest 30% (1,404, 2026-05-18 to 2026-09-25):
  - `P(3 sets) = 0.1168 + 0.5813 × 2p(1-p)`. Holdout log loss 0.638, against
    0.651 for the current formula and 0.645 for the base rate.
  - The favorite's share of 3-setters is `q = 0.0461 + 0.8580 × p`.
  - `P(favorite 2-0) = p - q × P(3 sets)` and
    `P(underdog 2-0) = (1-p) - (1-q) × P(3 sets)`, each floored at 0, so the
    three outcomes always sum to 1. Holdout log loss 0.664, against 0.666 for
    `p²`.
- Route the best-of-3 set-outcome call sites through it: derived set picks, and
  the bankroll builder's straight-sets probability and imputed set-handicap
  price. Best-of-5 keeps its current inputs, because no best-of-5 fit exists.
- **The total-games mixture weight stays on `2p(1-p)` (decided during
  implementation, 2026-09-25).**
  - Plugging the fitted curve in shifts total-games picks toward UNDER, because
    the projection it anchors to was scaled to the market's median line, not its
    mean.
  - The only data to check that against, the stored book total lines, proved
    unreliable. Over 1,414 settled matches, the actual over rate at the stored
    line was 0.618 while the stored prices implied 0.492. The market's own
    de-vigged price scored worse than a coin flip there.
  - Cause: `_parse_draftkings` (`api/app/ingest/odds_api.py:302`) keeps the
    alternative total nearest 21.5 rather than the main line, and its
    `"total" in name` test can match other total markets too.
- In `generate_market_odds_picks`, skip a book total-games line when the
  projection is that same market line.
- Choose a prop's side by the higher of `p_over` and `p_under` in both places.
- Rank priced picks ahead of unpriced ones in the moneyline/derived bucket.

**Must not break:**
- Best-of-5 behavior.
- PrizePicks total-games grading against the sportsbook total.
- Demon and goblin props staying OVER-only.
- The existing `total_games_probs`, best-of-5 and bankroll set-pick tests,
  apart from assertions that encode the old formula (update those, with a
  note).

## Follow-ups found during this fix

- **Book total-games lines are stored wrong.** Fix `_parse_draftkings` to keep the
  main (balanced) total, and only the match-total market. This also feeds the
  PrizePicks total-games projection through `_fetch_market_total_games`.
- **Refit the total-games set weight after that fix.** Then decide whether the
  projection is a mean or a median before switching the mixture to the fitted
  curve.

## Build steps

1. [x] **Calibrated best-of-3 set counts.**
   - Add the helper, with the fit's provenance in a short comment.
   - Use it at every best-of-3 call site.
   - Tests:
     - The three outcomes sum to 1 and are never negative across p in 0.5 to
       0.99.
     - The helper is symmetric in which player is p1.
     - It reproduces the fitted values at a few points.
     - Best-of-5 inputs are unchanged.
   - Done when these pass, and a before-and-after replay of today's slate
     shows changed probabilities on derived set picks, with no best-of-5
     changes and total-games probabilities unchanged.
2. [x] **No self-graded book totals, and a consistent prop side.**
   - Skip the circular total-games pick.
   - Choose prop side by probability in `routers/props.py` and
     `best_picks.generate_prop_picks`.
   - Tests:
     - A book total-games line whose projection equals that line yields no
       pick.
     - A Poisson prop with mean just above the line whose `p_under` exceeds
       `p_over` recommends UNDER.
     - Demon and goblin stay OVER.
   - Done when these pass, and a replay shows no book Total Games picks whose
     projection equals the line.
3. [x] **Priced picks rank first.**
   - Sort the moneyline/derived bucket with priced picks before unpriced
     ones.
   - Tests: a priced moneyline pick is kept even when three derived picks
     score higher.
   - Done when this passes, and a replay shows every match with a moneyline
     pick still lists it.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest`
- On the Tennis page, set-score and "Match goes 3 sets" probabilities move
  toward the measured rates. For example, a 55% favorite shows about 40% for
  3 sets, not 49%.
- Moneyline picks are never hidden behind unpriced set picks.

## Completion evidence

- `cd api && .venv\Scripts\python.exe -m pytest` passed, 1303 tests. The web app
  was not touched.
- The fit's analysis scripts ran read-only against the live database.
  Measurement, fit, and time-split holdout are recorded above and in the
  `app/core/tennis_sets.py` docstring.
- Replay of the 2026-09-25/26 slate, before and after step 1, 89 to 91 derived
  set picks:
  - "Match goes 3 sets" averaged 0.478 before and 0.395 after; 4 picks fell
    under the 0.35 cutoff.
  - "Favorite 2-0" went from 0.531 to 0.498.
  - "Underdog wins a set" went from 0.656 to 0.633, and 2 picks were added.
  - There were no best-of-5 matches, and the total-games code path is
    unchanged.
- Step 2 left no mark on that day's data: none of 36 standard PrizePicks props
  changed side, and no book total-games lines were stored. It is covered by
  `tests/test_prop_side.py` (end to end through `_enrich`) and
  `test_a_book_total_is_not_graded_against_itself`.
- Step 3: `test_priced_moneyline_pick_is_never_pushed_out_by_unpriced_picks`
  fails with the step's change removed and passes with it. All 6 moneyline
  picks on the day's slate stayed listed.
- Decided with the user during implementation: set outcomes only. The
  total-games mixture weight and expected sets stay on `2p(1-p)`, for the
  reasons recorded above.
