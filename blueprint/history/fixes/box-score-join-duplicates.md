# Fix: Box scores lost to duplicate rows and name suffixes

**Type:** Fix
**Status:** complete (2026-09-29)
**Branch:** `fix/box-score-join-duplicates`

## The problem

Aces, double faults and break points come from TennisAbstract box scores
(`player_match_stats`), attached to a match by `join_box_score` in
`app/core/box_score_join.py`. It joins only when exactly one candidate
survives the window, result, opponent and score checks. Over completed matches
in the last 30 days (measured 2026-09-29) it failed for:

| Tour | Player-matches | Joined | no_candidate | ambiguous | no_opponent_match | score_mismatch |
|---|---|---|---|---|---|---|
| ATP | 664 | 74% | 9% | 12% | 5% | 1% |
| WTA | 666 | 73% | 12% | 12% | 3% | 0% |
| Challenger | 3,188 | 65% | 20% | 7% | 8% | 0% |

Two of those causes are our bugs:

1. **Duplicate rows make the join ambiguous.** The row's unique key is a hash of
   the raw TennisAbstract row, so when TennisAbstract edits a row after the
   match, the refetch stores a second copy instead of updating it. Rublev v
   Hijikata (ATP Hangzhou R16) is stored twice with identical stats (6-3 6-3,
   12 aces, 0 DF), fetched 09-25 and 09-29; the join sees two candidates and
   gives up. An earlier fetch can also leave an **empty placeholder** for a
   match not yet played (no score, result or stats), which survives the score
   check (it has no score) beside the real row. 556 (player, date, opponent,
   round) groups are duplicated.
2. **Name suffixes break the opponent match.** `names_player` requires the
   stored name's last word to appear in the other name. For "Martin Damm Jr"
   that word is "jr", so TennisAbstract's "Martin Damm" never matches (Hurkacz v
   Damm Jr, ATP Chengdu R16). Any Jr, Sr, II, III or IV player hits this.

The third cause, `no_candidate`, is mostly real: 275 of 1,328 players active in
the last 30 days have no TennisAbstract rows at all (for example Alafia
Ayeni). Out of scope; the dashes there are correct.

## The fix

**In `join_box_score` (pure, `app/core/`)**, after the score check:

- Drop **empty** candidates (no score, and no aces, double faults, break
  points converted or break chances created) when any non-empty candidate
  remains.
- If every remaining candidate carries the **same facts** (date, result, score,
  aces, double faults, break points converted, break chances created), they are
  copies of one box score: join one of them, the lowest `stats_id`. Different
  facts stay `ambiguous`: never guess between two real box scores.

**In `names_player` (`app/core/tennis_odds_events.py`)**, ignore a trailing
generational suffix (`jr`, `sr`, `ii`, `iii`, `iv`) on either name before the
surname check.

Must not break:

- **Still one box score or none.** A genuinely different second candidate
  (another round, other stats) still returns `ambiguous`. The module's rule,
  "a wrong box score would quietly corrupt a hit rate, which is worse than a
  smaller sample", stands.
- **Odds-event matching.** `names_player` also matches Odds-API.io events to
  players; stripping a suffix only widens a match whose last word was the
  suffix. Its existing tests must pass unchanged.
- **No schema change, no ingest change.** Stopping the duplicates at ingest
  (a stable key, then a migration to merge existing copies) is a separate,
  larger fix; this makes the join tolerate them.

**Knock-on, intended:** everything that joins box scores gains rows: the match
page and prop evidence panel, `prop_settlement`, and the 26b and 26f grading
reports (`app/backtest/tennis_prizepicks_lines.py`,
`tennis_prop_snapshots.py`). Their settled samples grow; no pre-registered
tennis verdict depends on them yet.

## Build steps

- [x] **Step 1 - Name suffixes** - strip a trailing `jr`, `sr`, `ii`, `iii`
  or `iv` token in `names_player` (not when it is the only token). *Done
  when:* tests cover "Martin Damm Jr" v "Martin Damm" both ways, "Jr." with a
  dot, "Juan Martin del Potro" unaffected, a suffix-only name, and "Li" still
  not matching "Lin"; existing `names_player` and odds-event tests pass.
- [x] **Step 2 - Collapse copies and drop placeholders** - in
  `join_box_score`, drop empty candidates when a non-empty one remains, then
  join when all remaining candidates share the same facts (lowest
  `stats_id`). *Done when:* tests cover two identical copies (joined, lowest
  id), a placeholder plus a real row (joined to the real row), two placeholders
  only (still ambiguous, nothing to join), and two real rows with different
  stats (still `ambiguous`); the full pytest suite passes; and re-running the
  30-day measurement shows `ambiguous` and `no_opponent_match` down and
  `joined` up per tour, with Rublev v Hijikata and Hurkacz v Damm Jr now
  joined.

## Result

Measured again on 2026-09-29 over the same 30 days, after both steps:

| Tour | Joined | ambiguous | no_opponent_match |
|---|---|---|---|
| ATP | 74% to 87% | 12% to 0% | 5% to 4% |
| WTA | 73% to 86% | 12% to 0% | 3% to 3% |
| Challenger | 65% to 73% | 7% to 0% | 8% to 7% |

Left open: the remaining `no_opponent_match` rows are other name differences,
and ingest still stores duplicate rows (the join now tolerates them).

## Verify

1. `#/tennis/match/82863` (Hurkacz v Davidovich Fokina): Hurkacz's recent form
   now shows aces, DF and BP won for v Damm Jr and v Shevchenko.
2. `#/tennis/match/82864` (Medvedev v Rublev): Rublev v Hijikata now shows
   12 aces, 0 DF.
3. A low-ranked Challenger player with no TennisAbstract data (Alafia Ayeni,
   `#/tennis/match/82419`) still shows dashes.

## Notes for the AI

- Both changes are pure `app/core/` functions: test them directly in
  `tests/test_box_score_join.py` and the existing name-matching tests.
- "Same facts" compares the stored values, not the opponent name's spelling.
- No em dashes in comments.
