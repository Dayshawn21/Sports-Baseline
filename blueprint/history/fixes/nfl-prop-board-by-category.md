# NFL prop board: best picks by category

**Type:** Fix

## The problem

The NFL page is organized by game. To answer "what are the best passing-yards
plays this week?" you have to open each of 16 matchups in turn and hold the
comparison in your head. There is no way to read one market across the whole
slate.

This is not a build-plan item. Item 19 and item 24 are complete and NFL feature
work is closed ([project-overview.md](../../context/project-overview.md), open
question 12), so this is logged as an ad-hoc change rather than a new numbered
feature. It adopts no new signal and changes no projection: it is a second way
to read what `/nfl/slate` already computes.

## The fix

A new page at `/nfl/board`, beside `/nfl` in the nav. Pick a market and see
every player in it across every game, ranked best to worst.

Frontend only. `GET /nfl/slate` already returns the whole week, so the page
reuses the existing `useNflSlate` hook and its cache. No endpoint, repository,
schema, or model change.

Two ranking rules were set by what the live data did, and both must hold:

- **Edge is scored against the category's median rateable line, not the row's
  own line.** Dividing by a row's own line breaks in the bottom tail: a blocking
  tight end carries a real 0.5-yard receiving line, and a routine 12-yard
  projection on it reads as +2314%, taking the top of a board whose median line
  is 26.5. One shared denominator keeps rows comparable and immune to a tiny one.
- **Rows under 8 games of sample rank below full-sample rows and are marked
  thin.** The backend's 4-game floor in `edge_is_comparable` is right for the
  game-by-game slate but not for a ranked board, where a thin baseline produces
  the most extreme average and floats straight to the top. Before this rule the
  top passing-yards row was a backup quarterback projecting 62.7 yards against a
  185.5 line off four mop-up games. The 8-game cut is the confidence rule
  `/nfl/projections` already uses. Ruled-out and doubtful players are demoted the
  same way.

## What shipped

| File | Change |
|---|---|
| [web/src/utils/nflPropBoard.ts](../../../web/src/utils/nflPropBoard.ts) | New. Flattening, the category reference line, rateability, and the ranking comparator |
| [web/src/utils/nflPropBoard.test.ts](../../../web/src/utils/nflPropBoard.test.ts) | New. 27 tests |
| [web/src/utils/nflSignal.ts](../../../web/src/utils/nflSignal.ts) | New. `edgeLabel`, `edgePctLabel`, `trustLabel`, `signalSummary`, lifted out of the slate page |
| [web/src/utils/nflSignal.test.ts](../../../web/src/utils/nflSignal.test.ts) | New. 10 tests |
| [web/src/pages/NflPropBoardPage.tsx](../../../web/src/pages/NflPropBoardPage.tsx) | New. The page |
| [web/src/pages/nfl-prop-board.css](../../../web/src/pages/nfl-prop-board.css) | New. Scoped styles, reusing the `.nfl-slate` theme tokens |
| [web/src/utils/nflLabels.ts](../../../web/src/utils/nflLabels.ts) | Shared season and week select options |
| [web/src/pages/NflIntelligencePage.tsx](../../../web/src/pages/NflIntelligencePage.tsx) | Imports the extracted helpers; seeds its selection from a board link |
| [web/src/App.tsx](../../../web/src/App.tsx) | Route and nav entry |

## Build steps

- [x] **Build the board.** Ranking util and tests, the page and its CSS, the
  shared display helpers, the route and nav entry, and URL seeding on `/nfl`.
  **Done when:** `/nfl/board` ranks each of the 9 markets across the week, and a
  row links through to `/nfl` with its game and line preselected.

- [x] **Rebase onto the current master and resolve the overlap.** The branch was
  cut from `3b62495`; master moved to `4cae792`, which added the
  `nflBookOddsEvidence` and `snapShareLabel` imports plus the `BookOdds` and
  `SnapShare` components to `NflIntelligencePage.tsx`, in the same import block
  this branch rewrote. Both sides kept.
  **Done when:** build is clean, the full suite passes, the `/nfl` evidence panel
  still shows Sportsbooks and Snap share, and `/nfl/board` still ranks.

## Verification

Run on the rebased branch:

- `cd web && npm run build` - clean, `tsc -b` included.
- `cd web && npm run test` - 15 files, 132 tests passing.
- `/nfl/board`, 2026 week 2: 9 category tabs with rateable counts. Receiving
  yards leads with Rashee Rice (52.5 line, 85.4 model, +124.0%), Pickens, and
  Coleman, all starters on normal lines. Sample depth shows per row (8g, 17g,
  12g). The 0.5-yard blocking tight ends that led before the reference-line rule
  no longer place.
- Show all lines: 30 rateable to 84 total under the "Not rateable" divider.
- Position filter: receiving yards 178 to 49 with TE selected, all TE.
- Anytime TD renders as probabilities, not raw counts.
- Regression check on `/nfl`: Chuba Hubbard's anytime-TD line shows
  `Snap share = 55% · 31 g, season-weighted` and
  `Sportsbooks = 54.0% · 6 books · 30h ago`, matching the API payload
  (`snapShare` 0.554, `bookProbability` 0.5402, `bookCount` 6). A WR receiving
  yards line correctly renders neither block.
- Mobile at 390px: no horizontal page overflow, nav collapses to the drawer.
- Console clean on both routes.

## Notes

- Every row reads "Review" in 2026 week 2 because all baselines still come from
  2025 and carry `stale_baseline_season`. Accurate, and it resolves as 2026
  games accumulate.
- Anytime TD has only 5 rateable lines; most TD props arrive as goblin or demon
  odds types, which the model does not price against the market. They are
  visible behind "show all lines".
