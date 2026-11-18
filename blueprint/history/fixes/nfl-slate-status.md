# Fix: The NFL slate reads status through `gameState()`

**Type:** Fix
**Fixes:** F-76
**Branch:** `claude/fix-nfl-slate-status-a58bad`

**Completed:** 2026-11-18. PR against master, merge left to the user.

### The problem

`utils/nflSlate.ts` `rowState` checks `game.status === 'completed'`
case-sensitively and has no postponed or canceled branch, so a postponed or
canceled NFL game reads as upcoming, live or "Result pending". Every other
sport reads status through `gameState()` in `utils/gameState.ts` (F-59). The
page's `STATE_LABEL` map in `pages/NflIntelligencePage.tsx` pairs with it. The
slate summaries (`nbaSlate.ts`, `nflSlate.ts`, `nhlSlate.ts`) and
`homeSources.ts` also count finals with a case-sensitive `=== 'completed'`.

### The fix

1. `gameState.ts` exports `isFinalStatus(status)`, the lowercase check
   `gameState()` already makes, and `gameState()` uses it.
2. `rowState` returns `gameState(status, startUtc, now, 'Live')`, so the NFL
   row state is the shared `GamePhase` (`off` added) and the row carries the
   phase's label (`stateLabel`, null while upcoming). NFL keeps its labels:
   `Final`, `Result pending`, `Live`.
3. An `off` row shows its kickoff time with `Postponed` or `Canceled` beside
   it (in place of the time on a phone, as `Result pending` does), drops the
   pre-game tags, conditions and odds age, and blanks the market cells, as
   the NBA card does for an `off` game. It sorts after upcoming games, as on
   the other slates.
4. The search result's second line uses `row.stateLabel`, so `STATE_LABEL`
   goes.
5. The finals counts in the three slate summaries and the home page's
   schedule and moneyline filters use `isFinalStatus`.
   `homeSources.ts:188` is not touched (F-77).

### Visible changes

1. A postponed or canceled NFL game shows `Postponed` or `Canceled` in the
   kickoff cell and in its search result, with no market lines or pre-game
   tags, and sorts after the upcoming games, instead of reading as upcoming,
   live or `Result pending`.
2. A stored status in another case (`Completed`) reads as final on the NFL
   slate and counts as a final in every slate summary and on the home page.

Must not change: upcoming, live, pending and final NFL rows and labels.

Kept as is: an `off` row still shows the muted model column, and the "games
left" line does not count an `off` game as left, as on the NBA and NHL slates.

### Build steps

- [x] **Step 1.** `isFinalStatus`, `rowState` through `gameState()`, the
  `off` row and kickoff cell, the page label, and the case-insensitive
  counts, with tests beside each util. Done when: tests cover postponed,
  canceled, uppercase status and unchanged upcoming, live, pending and final
  rows, and Verify passes.

### Verify

- `npm --prefix web run verify` and the API tests.
