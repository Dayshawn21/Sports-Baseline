# Feature: Table-first NFL slate

**From build-plan:** feature 38b
**Branch:** `feature/38b-table-first-nfl-slate`
**Status:** complete (2026-10-17)

> **Follow-up fix (2026-10-17, after merge):** Notes got a fixed 220px so spare width spreads across every
> column (it had taken 544px at 1440), the two-line breakpoint moved from 1000px to 1100px so the eight fixed
> columns still fit, and a final's Game cell shows the records instead of a second "final".

## Goal

Replace the NFL slate's card grid with the shape the chosen sketch locks for
every sport: a plays digest of the week's largest prop gaps (gray, labeled
reference) above one dense table row per game, grouped by kickoff window, each
row opening the game page. The owner scans fourteen games in one screen instead
of scrolling cards; 38c then puts tennis and NBA on the same shape.

**Display only.** No probability, edge, rank, sort or pick changes, and no API
or schema change. Every number shown already reaches the page today.

## Design reference

- Chosen sketch: `.impeccable/mocks/decision/command.html` (the digest and the
  table below the page head; open it in a browser).
- Direction contract: `.impeccable/surfaces/web-src-pages-nflintelligencepage-tsx.md`
  (FIRST VIEWPORT: four-up digest, table columns, phone behavior).
- Theme tokens stay in `web/src/index.css`; the 11px floor and the
  `.nfl-slate` gray-signal scope (33a) are unchanged.

## In scope

- **Plays digest.** Up to four boxes under a label reading "Largest gaps this
  week · reference, not picks". Each box: player, market and matchup, the line,
  the model projection, and the signed edge share (`edgePctLabel`), all gray.
  Each box links to its game page.
  - **Which lines:** the week-wide prop board as of now
    (`buildNflPropBoard(games, 'all', now)`, which already drops started
    games), rateable lines only, ranked exactly as the slate card's top props
    are ranked today (`compareBoardTiers`, then |edge share|, then name and
    line id), one per player. This is the card ranking widened from one game
    to the week, not a new sort.
  - **Empty:** with no upcoming rateable line (a finished week, a week before
    lines post), the digest and its label are not rendered.
- **Game table.** One `<table>` per kickoff window (existing `kickoffWindows`),
  under the existing window heading. Columns, matching the sketch:

  | Column | Upcoming / live | Final |
  |---|---|---|
  | Kickoff | Central weekday and clock (`Sun 7:15 PM`), `Live` tag once started | `Final` |
  | Game | `AWAY @ HOME`, records below (`3-2 · 1-4`) | `AWAY 14 · HOME 17`, loser dimmed |
  | Spread | market spread, "opened ..." below when it moved | close spread, "HOME covered" below |
  | Total | market total, "opened ..." below | close total, "over by 3.5" below |
  | Moneyline | favorite's price, the other side below | `--` |
  | Model | muted `nfl-elo-v1` spread · total, "Not a pick" column header note | muted, unchanged |
  | Props | stored prop lines for the game (`groupNflPropRows`, the summary strip's count) | same |
  | Notes | Out / D / Q counts, QB change, short week, conditions (`conditionsLabel`) | injury counts dropped |

  Missing values read `--`; a game with no odds shows `--` in the three
  market columns; an absent model reads "Unavailable", muted. A game with no
  kickoff time reads `--` in Kickoff (its window heading already says "Kickoff
  time not set"). A final whose score is not loaded yet shows `AWAY @ HOME`
  with a `Final` tag and `--` for the close lines, as the card's "Final score
  not loaded yet" did.
- **Row opens the game page.** The Game cell holds the `Link` (keyboard and
  screen reader path, `aria-label` "AWAY at HOME, open game page"); a click
  anywhere else on the row navigates too, ignoring clicks that land on the link
  itself (no double navigation) and modified clicks (Ctrl or middle click open
  the link in a new tab as normal). Hover raises the row to `--bg-card`.
- **Phone (768px or narrower), and two-line rows up to 1000px.** The fixed
  column widths need about 1000px, so rows switch to two lines at 1000px and
  below (found in step 5); the digest scrolls sideways at 768px and below (boxes about 70%
  of the viewport, scroll snap); each table row becomes two lines: line 1
  kickoff, game, props; line 2 spread, total, moneyline, model. The header row
  is hidden on phones; the total, moneyline and model carry short labels (`o/u`,
  `ML`, `model`) and the spread reads unaided. To fit line 2 at 390px (decided in
  step 4): the opened-move second lines hide, the model shows its spread only,
  and conditions hide (all three stay on desktop and the game page). Injury, QB
  and short-week tags, when a game has any, sit on a short third line. A final
  keeps its graded result ("DEN covered", "under by 9.5") in place of the
  moneyline and model.
- **Legend** stays, reworded: the gaps line says the digest and edges are
  reference until the ranking check (27j) adopts a slice.
- **Removed:** `NflSlateGameCard`, `nflSlateCard` and its card types,
  `topGameProps`, `slateBoards`, and their tests. Their content either moves to
  the row, the digest, or already lives on the game page (win bar, best spread,
  per-game top three props).

## Out of scope

- Previous / next week in the page head (the season and week selects stay);
  38f's shape pass decides that.
- Tennis and NBA slates (38c). **`nfl-slate-card.css` stays**: the NBA card
  imports it until 38c replaces that card.
- Props as rows on the game page and prop board (38d); the command field and
  live filtering (38e).
- Any API, schema, ranking, edge, color or `build_slate` change.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Row and digest view models** - in `web/src/utils/nflSlate.ts`,
  add `nflSlateRow(game, notes, now): NflSlateRowModel` and
  `slateDigest(categories, limit = 4): NflSlateDigestItem[]` (board lines already carry their teams, so no games argument), reusing the
  card's helpers (`marketCells`, `finalCells`, `injuryCounts`, `modelCells`,
  `cardTeam`). Extract the card's ranking loop into one shared function so
  `topGameProps` and `slateDigest` rank identically (the existing
  `topGameProps` tests stay green, proving the extraction changed nothing).
  Page unchanged.
  *Done when:* new Vitest cases pass for: an upcoming row (market with opened
  moves, favorite moneyline, muted model, prop count equal to
  `groupNflPropRows(game.lines).length`, tags); a live row; a final row (score,
  loser, covered and over/under results, no injury tags); a final without a
  stored score; an unscheduled kickoff (`--`); a row without odds,
  model or notes (`--`, "Unavailable", no tags); the digest ranking across games
  (out player sunk, one per player, limit 4, anytime TD and non-rateable lines
  excluded, started games absent); and an empty digest. `npm run test` green.
- [x] **Step 2 - Game table on desktop** - `NflSlateTable` (one window's
  rows) in `web/src/components/nfl/`, its CSS, and the page switching from the
  card grid to tables under each window heading. *Done when:* `/nfl` at 1440px
  shows every game of the current week as one row with the eight columns above,
  grouped by window; clicking a row or tabbing to its Game link and pressing
  Enter opens `/nfl/game/:id`; a final week (e.g. 2026 week 5) shows scores and
  results; no text below 11px; no green or red besides the existing Out tag
  color; no console errors.
- [x] **Step 3 - Plays digest** - `NflSlateDigest` above the first window.
  *Done when:* an upcoming week shows up to four gray boxes in `slateDigest`'s
  order (the step 1 test pins the order; in the browser, each box's player is
  the first rateable row of its market on `/nfl/board` or ranks ahead of it on
  edge share); each box opens its game page; a finished week renders no digest
  and no label.
- [x] **Step 4 - Phone layout** - two-line rows and a sideways digest at 768px
  and below. *Done when:* at 390px wide there is no horizontal page scroll,
  each game is two lines as specified, the digest scrolls sideways inside its
  strip, and every row still opens its game page.
- [x] **Step 5 - Remove the card path** - delete `NflSlateGameCard.tsx`,
  `nflSlateCard`, the card-only types, `topGameProps`, `slateBoards` and their
  tests, keeping the shared ranking function the digest uses; reword the
  legend. *Done when:*
  `rg "NflSlateGameCard|nflSlateCard|slateBoards" web/src` finds nothing, the
  NBA slate still renders its cards unchanged, and Verify passes.

## Files / areas

- `web/src/utils/nflSlate.ts`, `web/src/utils/nflSlate.test.ts` - view models.
- `web/src/components/nfl/NflSlateTable.tsx`, `NflSlateDigest.tsx`,
  `nfl-slate-table.css` - new.
- `web/src/pages/NflIntelligencePage.tsx`, `web/src/pages/nfl-slate.css` - the
  page wiring and legend.
- `web/src/components/nfl/NflSlateGameCard.tsx` - deleted (step 5).
- Not touched: `nfl-slate-card.css` (NBA imports it), the API.

## Data / contracts

- No API or schema change. Inputs are `/nfl/slate` and `/nfl/game-notes` as
  today.
- `NflSlateRowModel` and `NflSlateDigestItem` are display strings only, never an
  input to an edge or rank. **Load-bearing for 38c and 38e:** the digest item
  shape (`gameId`, `playerName`, `market`, `matchup`, `line`, `model`, `gap`) is
  the strip tennis and NBA reuse in 38c, and the row model is what 38e's
  command field filters, so both stay pure and keyed by `gameId`.
- **The digest order is the existing board-tier-then-edge-share order.** Any
  later change to it is a ranking change, not a display one.

## Testing

- Test gate is on. Step 1 ships the logic tests (`nflSlateRow`,
  `slateDigest`, the shared ranking). Steps 2 to 4 are components and CSS:
  verified in the browser at 1440px and 390px with screenshots, plus the build.
- Step 5 removes tests with the code they covered; the remaining suite must
  still exceed zero and pass.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`.
- Browser check needs the local API (see memory: the Windows selector-loop
  launcher) or the hosted API through `VITE_API_BASE_URL`.

## Notes for the AI

- Gray signal: the table sits inside the `.nfl-slate` root, so `--nfl-green` and
  `--nfl-red` resolve to text color; never style a gap or edge with
  `--signal-positive` / `--signal-negative` directly.
- The muted model is never sorted by or colored (24d); keep "Not a pick" visible
  in the Model column header.
- Times are CT: the Kickoff column shows weekday and clock without "CT" (the
  window heading names it); the weekday stays because Prime time spans Sunday and
  Monday (found in step 2).
- `buildNflPropBoard` already drops started games; do not re-implement that
  filter in `slateDigest`, and do not read the board as of kickoff for the
  digest (that was the card's per-game rule).
- Keep `kickoffWindows` and `nflSlateSummary` unchanged; their tests stay.
- No em dashes in new copy or comments.
