# Feature: Tennis slate

**From build-plan:** feature 31b (parent: 31. Web redesign)
**Status:** complete (2026-09-28)
**Branch:** `feature/tennis-slate-redesign`

## Goal

Rebuild the Tennis page (`/`) layout after `prototypes/tennis-slate.html`: a
summary strip, a row of best-pick cards, and a match table grouped by
tournament, with the selected match's detail in a side panel. The page shows
exactly the numbers it shows today, rearranged so the day's plays are visible
without clicking through the slate one match at a time.

## Design reference

- `prototypes/tennis-slate.html` - the summary strip, best-pick cards, and the
  grouped match table (layout, spacing, type sizes).
- `prototypes/nfl-prop-board.html` and today's NFL prop board - the pattern for
  the side panel (list left, sticky detail right).
- `web/src/index.css` `:root` - the tokens ported in 31a. `theme.css` is already
  in the app; this sub-feature builds against the tokens and does not port them
  again.
- **Where the mockup and this spec differ, the spec wins** (item 31 is restyle
  only):
  - The mockup's summary cards (plays, avg edge, suggested stake, 30-day P&L)
    are replaced by today's four counts: Matches, Props, Locks, Strong+. Avg
    edge and P&L would be new numbers; the quarter-Kelly stake is the retired
    bankroll builder (overview open question 29).
  - The mockup's price sparklines on pick cards are dropped: no odds history
    reaches this page.
  - The mockup's player ranks and per-book "best price" names are dropped: the
    predictions API returns neither. The table shows each player's moneyline.
  - The table has a detail side panel the mockup does not (user decision,
    2026-09-28).

## In scope

- A pure `web/src/utils/tennisSlate.ts` that turns `UnifiedTennisMatch[]` into
  table rows, tournament groups, and the featured picks, with unit tests.
- Summary strip: the four existing counts as large-number cards.
- Best-pick cards: the primary best bet of the first four matches that have one,
  in the page's current sort order.
- Match table: replaces the left-hand match list. Tour tabs (All, ATP, WTA,
  Challenger, WTA 125) stay. Rows grouped under tournament headers; selecting a
  row drives the side panel. The default selection stays as today (first match
  with a pick, else the first match).
- Side panel: today's selected-match workspace (matchup, best opportunity,
  match intelligence, decision board), restyled to fit a narrower column,
  sticky below the nav. "Open match analysis" still opens the comparison modal.
- Toolbar filters (Upcoming only, tour, date, sort, prop source, Show Leans)
  restyled in place, same behavior.
- Loading, empty, empty-tab, source-error, and props-health states restyled in
  place.
- 31a follow-ups on this page: side-tab stripes on the notices, the 9-10px
  labels in the workspace, and the tour tag that renders ATP blue.
- Mobile (390px): table rows collapse to two lines; the panel stacks under the
  table.

## Out of scope

- Any new number: average edge, P&L, stakes, sparklines, ranks, book names.
- Any change to which picks count as best bets, to confidence tiers, to EV, or to
  the sort orders (`utils/unifiedTennis.ts` logic is read, not changed).
- `PlayerComparisonModal` layout, including its Grass green; it keeps working as
  today.
- `UnifiedMatchCard.tsx` and its `.unified-match-card` CSS: no page renders it.
  Deleting dead code is a separate `/fix`.
- Tennis prop board (`/tennis/board`) - that is 31c.
- Any API or backend change.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Baseline and slate row model** - first record the current page:
  1440px and 390px screenshots of `/`, the four counts, and for the first five
  matches their pick, EV, and tier (saved under `.playwright-mcp/`, gitignored).
  Then add `web/src/utils/tennisSlate.ts` with `slateRows(matches)`,
  `groupByTournament(rows)` and `featuredPicks(matches, limit)`, plus
  `tennisSlate.test.ts`. No UI change. *Done when:* the baseline is recorded;
  tests cover a predicted match, a prop-only match (no prediction), a match with
  no best bet, missing probabilities, group order following each tournament's
  first row, a null tournament grouping under "Other", and `featuredPicks`
  skipping matches without a priced best bet; `npm run test` passes.
- [x] **Step 2 - Summary strip and toolbar** - restyle the page head: title,
  subtitle, and the four counts as summary cards (large mono numbers, Locks and
  Strong+ green as today). Restyle the filter toolbar as segmented pills and
  selects on the tokens, same controls and behavior. *Done when:* a 1440px
  screenshot shows the strip and toolbar, the four counts match the step 1
  baseline, every filter still changes the slate, and the build passes.
- [x] **Step 3 - Best-pick cards** - add `TennisPickCards` rendering
  `featuredPicks(matches, 4)`: pick, match and start time, EV large and green,
  model vs market %, odds, confidence tier. Clicking a card selects its match.
  Hidden when no match has a best bet. *Done when:* each card's pick, EV, and
  tier match the baseline for that match; clicking one moves the workspace to
  that match; with no best bets the row is absent, not an empty box.
- [x] **Step 4 - Match table** - add `TennisSlateTable` (tour tabs, tournament
  group headers, columns: time, players, ELO, ML, Market, Model, best pick, EV,
  odds, flags) and render it where `MatchNavigator` is today, deleting
  `MatchNavigator`. Prop-only rows show the players and prop count with dashes
  for probabilities. *Done when:* every match in the baseline appears as a row,
  selecting a row updates the workspace, tabs filter as before, an empty tab
  shows "No matches in this group.", a row with no best bet shows its best prop ("Player · stat") with the
  prop's EV in neutral gray, as the old list named it (amended in step 4: a
  dash dropped information the page showed), only best-bet EVs are green,
  and the build passes.
- [x] **Step 5 - Side panel layout** - swap the column proportions: table wide
  on the left, the workspace as a narrower panel on the right, sticky at
  `calc(var(--nav-height) + 16px)`, scrolling inside itself when taller than
  the viewport. Decided while building: the filter toolbar stops being
  sticky on this page (a pinned toolbar that wraps to two rows would hide the
  panel's top); ELO, ML and Odds columns show at 1680px and wider, and below
  that live in the panel (model breakdown, matchup odds), since the table gets
  875px beside the panel at 1440px; the time cell stacks day over time and flags
  show the first plus "+N" with all of them on hover. *Done when:* at 1440px the table and panel sit side by side,
  scrolling the table keeps the panel pinned below the nav, and the build
  passes.
- [x] **Step 6 - Panel restyle** - restyle the workspace for the narrow panel on
  the tokens: matchup, best opportunity, match intelligence, and decision-board
  rows stacked to fit (label and pick on one line, odds, model, market, EV and
  tier on the next); no side-tab or top accent stripes; labels at least 11px;
  the tour tag uses the tour token (Challenger teal, WTA 125 pink from
  `tourLabel`). Restyle the page notices (source error, props health) without
  the left stripe. *Done when:* a screenshot shows the panel with no stripes and
  no clipped decision-board text, the CHALLENGER tag renders teal, "Open match
  analysis" opens the modal, and the impeccable detector reports no `side-tab`,
  `border-accent-on-rounded` or `tiny-text` finding on `/`.
- [x] **Step 7 - Mobile** - at 768px and below, table rows collapse to two lines
  (time and players; best pick and EV), group headers stay, and the panel
  stacks under the table; selecting a row scrolls the panel into view. *Done
  when:* 390px screenshots show a readable table with no horizontal page
  scroll, and tapping a row shows its detail.
- [x] **Step 8 - Visual pass** - screenshot `/` at 1440px and 390px in the
  loaded, loading, empty (a date with no matches), and props-source-error states
  (error forced by blocking the props request in the browser), and run the
  impeccable detector on `/`. *Done when:* each state has a screenshot, the
  four counts and first five matches' picks match the original page read at
  the same moment (stash the page edits and `reload()`, never a same-URL
  `goto`, which keeps filter state; the live slate drifts as matches start,
  69/33/64/34 at baseline vs 69/32/62/33 fifteen minutes later, so the step 1
  snapshot is only indicative; found in step 2), no
  low-contrast finding beyond the known wordmark artifact, and `npm run build`
  and `npm run test` pass.

## Files / areas

- `web/src/utils/tennisSlate.ts`, `tennisSlate.test.ts` - new (step 1)
- `web/src/pages/TennisIntelligencePage.tsx` - head, toolbar, layout (steps 2, 3, 5)
- `web/src/components/tennis/TennisPickCards.tsx` - new (step 3)
- `web/src/components/tennis/TennisSlateTable.tsx` - new (step 4)
- `web/src/components/tennis/TennisCommandCenter.tsx` - `MatchNavigator` removed;
  the workspace becomes the panel (steps 4-6)
- `web/src/components/tennis/tennis-slate.css` - new page styles;
  `tennis-command-center.css` trimmed to the panel (steps 2-7)
- `web/src/index.css` - `.unified-source-notice` and toolbar rules (steps 2, 6)
- No API, schema, or backend change.

## Data / contracts

Internal to this page (no later feature depends on them yet):

```ts
interface SlateRow {
  key: string                      // UnifiedTennisMatch.key
  match: UnifiedTennisMatch        // the panel reads this
  startUtc: string | null
  tournament: string | null        // group header; null groups under "Other"
  tour: string | null
  tourLabel: string | null         // WTA 125 arrives as tour CHALLENGER
  players: [string, string | null] // prop-only rows may have one name
  // p1 then p2, 0-1; null when the prediction lacks it
  elo: [number, number] | null
  ml: [number, number] | null
  market: [number, number] | null
  model: [number, number] | null   // p1WinProb / p2WinProb
  odds: [number | null, number | null]
  primaryPick: BestPick | null     // bestBetPicks(match)[0] ?? anglePicks(match)[0]
  primaryIsBestBet: boolean        // true only when it came from bestBetPicks
  primaryProp: PropLine | null     // highest-EV prop; shown (EV neutral) when no pick (added in step 4)
  propCount: number
  flags: string[]                  // getDisplayFlags(prediction.qualityFlags)
}
```

- `groupByTournament(rows)` returns `{ tournament, rows }[]`; groups appear in
  the order of their first row, and rows keep their input (sort) order.
- **Grouping only in time order** (user decision in step 8): `isGroupedSort(sort)`
  is true for the two start-time sorts only, and `tableGroups(rows, grouped)`
  returns one header-less group otherwise, each row naming its tournament.
  Grouping under a ranking sort put the day's #3 opportunity at row 16.
- `featuredPicks(matches, limit)` returns `{ match, pick }[]` from
  `bestBetPicks(match)[0]`, in input order, skipping matches without one.
- Green: in the new table, EV is green only for a best bet (`primaryIsBestBet`);
  angles and prop fallbacks stay neutral. The panel keeps today's coloring,
  which is green on every EV (picks, angles and props). Corrected in step 6:
  this line first claimed the workspace colored only best bets.

## Testing

- **Step 1 ships unit tests** (`tennisSlate.test.ts`): pure logic with real
  branches (missing prediction, missing probabilities, grouping order, best bet
  vs angle).
- Steps 2-8 are layout and styling: build, screenshots at 1440px and 390px, the
  impeccable detector, and a comparison against the step 1 baseline (the four
  counts and the first five matches' pick, EV, and tier).
- `npm run build` and `npm run test` after every step.
- Block the props request in the browser to capture the source-error state.
  This page makes no Odds-API.io request, but keep Live Odds out of the checks.

## Notes for the AI

- **Restyle only.** Read `utils/unifiedTennis.ts`; do not change its logic or
  the order it produces. If a layout needs a number the row model does not
  carry, stop and ask rather than deriving a new one.
- Reuse existing formatters: `fmtPct`, `fmtAmerican` (`utils/odds`),
  `fmtStartCT`, `fmtTournament`, `fmtSurface` (`utils/format`),
  `getDisplayFlags` (`components/tennis/qualityFlags`).
- Tint token colors with `withAlpha()` (`utils/color.ts`); never append hex
  alpha to a color (31a completion notes).
- Keep functions under about 50 lines; the current `TennisCommandCenter` packs
  long one-line JSX, so split it as you touch it.
- Data fetching stays in the page's existing hooks; the new components take
  props only.
- Dark mode only; tokens from `index.css`, no new hex outside `:root`.

## Completion notes

- **Evidence:** `npm run build` and `npm run test` (229 tests, 20 files) passed.
  A same-moment comparison against the original page (tracked `web/src`
  changes stashed, clean `reload()`) matched the four counts (69 / 33 / 32 /
  62) and the first five matches' order, pick, EV and tier exactly. Loaded,
  loading, empty and PrizePicks-error states screenshotted at 1440px and 390px
  (empty and error forced with stubbed responses). The impeccable detector on
  `/` reports no side-tab, tiny-text, undersized-text or contrast finding
  beyond the known wordmark artifact.
- **Decisions made while building** (recorded in the steps above): grouping by
  tournament only under the start-time sorts (user decision); the toolbar is
  not sticky on this page; ELO, ML and Odds columns only at 1680px and wider;
  the prop fallback in the table; the panel keeps green on every EV.
- **Follow-ups (not changed here):**
  - `UnifiedMatchCard.tsx` and `.unified-match-card` are dead code (no page
    renders them); its top stripe is flagged by the detector.
  - The Admin page's props-audit banner still has a left side-tab stripe.
  - The comparison modal's Grass surface color is still a signal-like green.
  - Soft detector findings remain: intended ellipsis, uppercase eyebrows, "—"
    placeholders.
