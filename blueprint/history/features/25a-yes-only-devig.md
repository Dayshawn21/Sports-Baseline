# Feature: 25a - Yes-only de-vig

**Build-plan item:** 25a, under 25. Market-relative prop rating.

## Goal

Turn the Yes-only sportsbook prop consensus that item 19i stores into a
normalized market probability with the book's margin removed, as pure testable
functions, and show it on the slate beside the raw price.

This is the measurement step. It does not change any projection, edge, or rank:
that is 25c, and only if 25b's forward holdout passes a pre-registered backtest.

## Design reference

None needed. The one new display lands in the existing `.nfl-evidence-block`
Sportsbooks block in
[web/src/pages/NflIntelligencePage.tsx](../../web/src/pages/NflIntelligencePage.tsx),
restored by the `nfl-evidence-blocks` fix.

## The problem, measured

Books price anytime TD one-way, so [nfl_prop_odds.py:45](../../api/app/core/nfl_prop_odds.py#L45)
keeps the raw implied probability and sets `includes_margin = True`. Every one
of the 398 book-priced lines in 2026 week 2 carries that flag; none is de-vigged.

Per-game consensus probabilities, deduplicated per player, sum to:

| Game | Players | Sum | Game | Players | Sum |
|---|---|---|---|---|---|
| LV @ LAC | 13 | 3.58 | CLE @ TB | 23 | 4.80 |
| PHI @ TEN | 20 | 3.99 | MIN @ CHI | 19 | 4.96 |
| PIT @ NE | 18 | 4.14 | GB @ NYJ | 24 | 5.00 |
| CAR @ ATL | 21 | 4.42 | IND @ KC | 25 | 5.09 |
| NO @ BAL | 19 | 4.63 | JAX @ DEN | 24 | 5.16 |
| MIA @ SF | 22 | 4.70 | WAS @ DAL | 24 | 5.47 |
| CIN @ HOU | 21 | 4.72 | NYG @ LA | 24 | 5.85 |
| SEA @ ARI | 18 | 4.16 | | | |

Against roughly 4.0 to 4.3 expected distinct scorers, that is a margin of about
10 to 15%, and it biases the model-versus-book comparison: across 315 players the
model sits a median 1.0 points and a mean 1.9 points below book, with 178 below
against 137 above.

## In scope

- A pure power-normalization function for a set of one-way prices given a target sum.
- A pure function deriving that target (expected distinct scorers) from the game's
  book total, with every constant named and documented.
- A nullable normalized probability on `/nfl/slate`, alongside the raw one.
- The normalized figure shown in the evidence panel beside the raw price.

## Out of scope

- **Any use of the normalized number in a projection, edge, rank, or board.**
  That is 25c and is gated on 25b. The prop board's rateability rule is untouched
  and Anytime TD stays at its handful of standard lines.
- Settling stored prices against results, or any accrual job. That is 25b.
- Markets other than `anytime_touchdown`. `PROP_MARKETS` is unchanged.
- Any schema change. `nfl_player_prop_odds` is read as-is and nothing is stored;
  the normalized value is computed per request, like the 24d model strip.
- Tennis. The shared de-vig belongs to item 17, not here.

## Build loop

Per [ai-interaction.md](ai-interaction.md): one small step at a time, diff shown
and approved before the next, tests with any step that adds logic.

## Build steps

- [x] **Step 1 - power normalization in `app/core/nfl_prop_odds.py`**

  Add `normalize_one_way(probabilities: Sequence[float], target: float) -> list[float]`,
  solving for the exponent `k` where `sum(p ** k) == target` by bisection, then
  returning `p ** k`. Power normalization rather than proportional scaling
  because scaling can push a favourite above 1.0 and distorts the tail; the
  odds-ratio form is the standard overround removal for a multi-outcome book.
  Pure: no DB, no I/O, per the `core/` purity rule.

  Handle: empty input returns empty; a target at or above the raw sum returns
  the input unchanged (never inflate); any probability outside `(0, 1)` is
  excluded from the solve and passed through.

  **Done when:** `pytest api/tests/test_nfl_prop_odds.py` passes with cases for
  a known sum reducing to the target within 1e-6, order preservation, the
  no-inflation guard, an empty list, and a single price.

- [x] **Step 2 - expected distinct scorers from the game total**

  Add `expected_distinct_scorers(total_line: float | None) -> float | None`
  in the same module: total points to expected touchdowns to expected distinct
  scorers, with each constant a named module-level value carrying a one-line
  comment on where it comes from. Returns `None` without a total, so a game with
  no book total simply gets no normalization.

  **Done when:** tests pin the output for a low, typical, and high total
  (for example 38.5, 45.5, and 52.5), assert monotonicity in the total, and
  assert `None` for a missing total.

- [x] **Step 3 - expose the normalized probability on `/nfl/slate`**

  Set a new nullable `book_probability_devigged` on each line. Null whenever the
  game has no book total, the market is not full-game anytime TD, or
  `includes_margin` is false (already de-vigged, so leave it alone).

  Three constraints this step has to respect, all of them easy to get wrong:

  1. **It cannot happen in the existing per-row loop.** `slate_book_odds` is
     called per line at [api/app/routers/nfl.py:304](../../api/app/routers/nfl.py#L304),
     but normalization needs every player in a game at once. Add a second pass
     over `lines_by_game` after that loop, next to the existing sort pass, the
     same way 24d's `_game_model` runs after assembly.
  2. **Deduplicate by player before summing.** A player carries several lines in
     one game (0.5 standard, 1.5 demon, 2.5 demon) and each one repeats the same
     consensus. Summing lines rather than players inflates a game's total by
     roughly 1.6x. Every line for a player then receives that player's single
     normalized value.
  3. **Use the book total, not the model total.** The router already has
     `totals` from `replay_scoring(..., NFL_SCORING_V1)`, and it is the wrong
     input: that scoring rating was rejected by 24b. Take the total from
     `matchup_context[game_id]["odds"]`, the same market figure the matchup bar
     shows.

  The computation itself stays a pure `core/` call; the router only feeds it
  rows, matching how `slate_book_odds` is already wired. No SQL outside
  `app/repositories/`, per [coding-standards.md](coding-standards.md).

  **Done when:** `curl "http://127.0.0.1:8000/nfl/slate?season=2026&week=2"`
  shows `bookProbabilityDevigged` non-null on anytime-TD lines in all 15
  book-priced games, the per-game sum of the deduplicated normalized values
  equals that game's target within 1e-6, every normalized value is strictly less
  than its raw value, and both lines of a player who has several rows carry the
  same normalized figure. DET @ BUF, which played on Thursday and has no book
  prices, stays null throughout.

- [x] **Step 4 - show it in the evidence panel**

  Extend `nflBookOddsEvidence` in
  [web/src/utils/nflBookOdds.ts](../../web/src/utils/nflBookOdds.ts) so the
  Sportsbooks block reads the de-vigged figure as the headline with the raw one
  named beside it, and compares the model against the de-vigged number. Falls
  back to today's exact wording when `bookProbabilityDevigged` is null, so no
  line loses information.

  **Done when:** on `/nfl` 2026 week 2, a CAR @ ATL anytime-TD line's
  Sportsbooks block shows both figures and the model comparison uses the
  de-vigged one; a line without a de-vigged value renders exactly as it does
  today; `npm run test` and `npm run build` pass.

## Files / areas

| Path | Change |
|---|---|
| `api/app/core/nfl_prop_odds.py` | Steps 1 and 2, pure functions |
| `api/tests/test_nfl_prop_odds.py` | Steps 1 and 2 tests |
| `api/app/routers/nfl.py` | Step 3, second pass over `lines_by_game`. There is no `app/services/nfl/`; NFL slate assembly lives in the router, and this step follows that existing shape rather than introducing a service |
| `api/app/schemas/nfl.py` | Step 3, new nullable field |
| `web/src/types/nfl.ts` | Step 3, matching type |
| `web/src/utils/nflBookOdds.ts` + its test | Step 4 |
| `web/src/pages/NflIntelligencePage.tsx` | Step 4, if wording changes |

## Data / contracts

**Load-bearing.** `book_probability_devigged` (`bookProbabilityDevigged` on the
wire) is the field 25c would rate against and the shape any later de-vigged prop
market reuses. Define it in Step 3 and do not rename it afterwards.

- Type `float | None`, in `(0, 1)`.
- Null means not normalized, never "no margin". A raw price with
  `includes_margin = false` also yields null, because it needs no correction.
- It never replaces `book_probability`; both travel together so the correction
  stays auditable.

No migration. Nothing is persisted.

## Testing

The gate is on. Steps 1 and 2 are pure logic and ship `pytest` tests in the same
diff. Step 3 is service assembly: it ships a focused test of the per-game
grouping and null rules, and is proven live with the documented curl. Step 4 is
UI and rides on the existing `nflBookOdds.test.ts` plus build and screenshot
evidence, per the Testing section of [coding-standards.md](coding-standards.md).

## Notes for the AI

- **The target is the weak link, and the spec should not hide it.** The
  constants in Step 2 are reasoned, not fitted, exactly like
  `USAGE_EFFICIENCY_REGRESSION` in finding F-02. Comment them as provisional and
  name 25b as what would validate them. A wrong target shifts every normalized
  probability in a game by the same factor, so it cannot be caught by eye: the
  numbers will look plausible whether or not the constants are right.
- **Data availability, checked 2026-09-19:** 15 of 16 week 2 games carry book
  prop prices, and all 15 also carry a book total, so the null-total path is
  real but will not fire this week. Do not treat "it was non-null everywhere I
  looked" as evidence the null path works; test it directly.
- **Do not let this creep into 25c.** If a step starts changing `isRateable`,
  `edge`, or the board, it is out of scope; stop and say so.
- The `core/` purity rule is load-bearing. Steps 1 and 2 take plain numbers, not
  rows or sessions.
- No em dashes in new content, per the Writing section of the standards.
