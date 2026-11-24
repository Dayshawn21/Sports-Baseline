# Fix: Shared NHL prop helpers, projection history and board sorting

**Type:** Fix
**Fixes:** F-69
**Branch:** `fix/web-shared-props` (cut from `fix/web-hooks`, so merge the
five earlier web branches first)

**Completed:** 2026-11-16. Squash-merged to master at the user's request.

### The problem

Three sets of near copies:

- **NHL prop tables.** `NhlGameProps.tsx` and `NhlPropBoardMarket.tsx` each
  define `alternates()` (the non-standard rungs as `Goblin 2.5 (+0.4)`
  labels) and each build the same P(over) caption from
  `NHL_PROBABILITY_CAPTION`, `NHL_WHOLE_LINE_NOTE` and
  `nhlProbabilityNote`.
- **Projection history.** `nhl/NhlPlayerProjectionHistory.tsx` and
  `tennis/player/PlayerProjectionHistory.tsx` share the heading, the loading,
  error and empty states, the toolbar and chart layout, and a `footnote()`
  that differs only in "game" versus "match".
- **Board sorting.** `nbaPropBoard.ts` and `nhlPropBoard.ts` each define a
  start-time parser (`tipTime`, `dropTime`), the same row comparator (start
  time, player name, game id, player id; NBA adds the row kind) and the same
  board path builder.

### The fix

User decisions (2026-11-16):

- **Default market:** each sport keeps its own rule. NBA falls back to
  Points; NHL falls back to the first market with rows, else Shots on Goal.
  Only the sort and path are shared.
- **NHL tables:** share the helpers only. Both tables keep their own markup
  and classes.

Changes:

- `utils/nhlProjection.ts` gains `nhlAlternateLabels(rungs): string[]` and
  `nhlProbabilityCaption(market, rows): string | null`. Both NHL tables use
  them. The game page joins the labels with ` / ` as it does now.
- `utils/projectionHistory.ts` gains a `historyFootnote` shared by both
  sports, with the unit word passed in. A new
  `components/shared/ProjectionHistorySection.tsx` holds the heading, states
  and layout. The NHL and tennis components become adapters that supply the
  query, the filters toolbar, the chart points and their own empty text and
  classes.
- New `utils/propBoardRows.ts` with `boardStartTime`, `compareBoardRows` (NBA
  adds its row-kind tiebreak after it) and
  `propBoardPath(sport, date, market)`. Both boards use them, and the
  exported `nbaBoardPath` and `nhlBoardPath` keep their signatures.

No visible change. Stays inside `web/`.

### Build steps

- [x] **Step 1 - NHL table helpers.** Add `nhlAlternateLabels` and
  `nhlProbabilityCaption` with tests, and use them in both tables. Done
  when: neither component defines `alternates`, Verify passes, and the NHL
  game page props and the NHL board show the same captions and other lines
  as before.
- [x] **Step 2 - board sort and path.** Add `propBoardRows.ts` with tests,
  and use it in `nbaPropBoard.ts` and `nhlPropBoard.ts`. Done when: neither
  board file defines its own time parser, comparator or path builder, the
  existing board tests pass unchanged, and Verify passes.
- [x] **Step 3 - projection history.** Add `historyFootnote` with tests and
  `ProjectionHistorySection`, then make the NHL and tennis components
  adapters. Done when: the footnote text and the empty, loading and error
  states read as before on an NHL and a tennis player page, and Verify
  passes.

### Verify

- `npm --prefix web run verify` after each step.
- In the running app: the NHL game page props, the NBA and NHL boards
  (default tab, row order, links) and the NHL and tennis projection history
  sections look the same as before.
