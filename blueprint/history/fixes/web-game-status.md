# Fix: One game-status rule on the web

**Type:** Fix
**Fixes:** F-59
**Branch:** `fix/web-game-status` (cut from `fix/web-formatting`, so merge
F-71 and F-60/F-72 first)

**Completed:** 2026-11-16. Squash-merged to master at the user's request.

### The problem

`utils/gameState.ts` `gameState()` is the canonical status rule used by the
NFL, NBA and NHL game pages: it lowercases the stored status, accepts both
`canceled` and `cancelled`, and says "Result pending" for a game started over
five hours ago with no final stored. Four copies skip parts of it:

| Copy | Used by | Gaps |
|---|---|---|
| `nhlGame.ts` `nhlGameState` | NHL slate cards | case, `cancelled`; OT final reads `Final / OT` where the game page says `Final/OT` |
| `nbaSlate.ts` `cardState` | NBA slate cards | case, `cancelled` |
| `nbaPropBoard.ts` `nbaBoardGameLabels` | NBA props board | case, `cancelled`, no "Result pending" |
| `nhlPropBoard.ts` `nhlBoardGameStatus` | NHL props board | case, `cancelled`, no "Result pending" |

### Decisions (approved 2026-11-15)

Each sport keeps its started label (`Tipped off`, `Puck dropped`, `Started`)
and the NBA cards and boards keep no label for an upcoming game. These
visible changes are approved:

1. NHL slate card OT or shootout final: `Final / OT` becomes `Final/OT`.
2. NBA and NHL props boards: a game started over five hours ago with no final
   stored shows `Result pending` instead of `Tipped off` / `Started`.
3. A stored status in another case or spelled `cancelled` reads as
   Final / Postponed / Canceled everywhere.

### The fix

Give `gameState()` an optional started label (default `In progress`). Each
copy calls it (plus `withEndPeriod` for NHL) and maps the result to the
shape its callers already use: `live` stays `started` for the NBA and NHL
card types, and the boards and NBA cards turn the `upcoming` label into null.
The copies' start-time parsing goes with them where nothing else uses it.

Must not change: the game pages' labels, the slate sort order, any other
label text.

### Build steps

- [x] **Step 1 - slates.** `gameState()` takes the started label, with
  tests; `nhlGameState` and the NBA `cardState` route through it. Done when:
  tests cover the started label, `cancelled`, uppercase status and the
  NHL `Final/OT` label, and Verify passes.
- [x] **Step 2 - props boards.** `nbaBoardGameLabels` and
  `nhlBoardGameStatus` route through it. Done when: board tests cover
  `Result pending` and the upcoming null, Verify passes, and the NBA and NHL
  props boards and slates show the same labels as before for today's games.

### Verify

- `npm --prefix web run verify` after each step.
- In the running app: NBA and NHL slates and props boards, and the NHL game
  page for a final.
