# Feature: NFL props as rows

**From build-plan:** feature 38d1 (38d split into 38d1 NFL, 38d2 tennis, 38d3 NBA on 2026-10-17)
**Status:** spec

## Goal

The NFL prop board (`/nfl/board`) and the game page's Props (`/nfl/game/:gameId`)
show one dense table row per prop line instead of a card, in the shape the
slates took in 38b and 38c. Each row opens the existing evidence panel in a
drawer. **Display only:** every rank, edge, sort, filter and color is what the
cards show today, because each row reads the same `nflPropCard` model.

## Design reference

- No props mockup exists. The direction contract
  `.impeccable/surfaces/web-src-pages-nflintelligencepage-tsx.md` and the chosen
  sketch `.impeccable/mocks/decision/command.html` set the shape: dense rows,
  fixed column widths, two-line rows on phones, no boxed cards.
- Match the shipped tables: `NflSlateTable` and `nfl-slate-table.css` (38b),
  `TennisSlateTable` (38c1) and `NbaSlateTable` (38c2).

## In scope

- **One table per market,** under the market's heading, as the cards are grouped
  today. The market is the heading, so it is not a column (the board already
  shows one market at a time).
- **Stat rows** (every market but anytime TD):

  | Column | Content | From `NflPropCardModel` |
  |---|---|---|
  | # | Board rank, `--` when not rateable | `rank` |
  | Player | Name, then position, matchup, kickoff (and segment off full game); injury tag and depth text inline | `playerName`, `meta`, `injury`, `depthText` |
  | Line | Line and unit | `lineText`, `unit` |
  | Model | Projection | `modelText` |
  | Gap | Pick label, edge share (with today's tooltip), raw edge below | `pickLabel`, `edgeShareText`, `edgeText` |
  | Last 5 | Mini bars with the line dashed | `recentBars(row)` |
  | Sample | Trust, then sample text with the flags tooltip | `trust`, `sampleText`, `flags`, `thin` |

- **Anytime TD rows:** #, Player, Model, Sportsbooks (`bookText`), Snap share
  (`snapText`), Sample. No line, gap or bars, as today (no pick until 25c).
- **The "why" line** (`signalSummary`) leaves the row; it is already in the
  evidence panel. The row's `title` attribute carries it.
- **Not rateable** lines keep their divider and note, as dimmed rows below the
  rateable ones, under the same "Show all lines" switch.
- **Drawer:** a row click (or Enter / Space) opens `NflEvidencePanel` in an
  Ant Design `Drawer` (460px, full width on phones), as the game page does today.
  - **Board:** the side panel and its auto-selection of the first line go away;
    nothing is open until a row is clicked. The drawer keeps the game link.
    This is the one deliberate behavior change: the table takes the panel's
    width, and the phone scroll-to-panel code (`STACKED_QUERY`) is removed.
  - **Game page:** unchanged drawer, now opened from rows.
  - The open row reads as selected (`aria-pressed` on the row button, plus the
    selected style) while the drawer is open.
- **Other lines** (item 35's line-only markets on the game page): plain rows per
  market with Player, Line, Also (other rungs), Last 5 (mini bars) and "over N
  of 5". No rank, model, gap, click or drawer (item 35's rule). The player name
  stays a link to the player page.
- **Phones (at 1100px and below):** two-line rows, as the slate tables do: line
  one is rank, player and gap (or model for anytime TD); line two the rest. No
  horizontal page scroll at 390px.
- **Shared pieces for 38d2 and 38d3:**
  - `components/shared/MiniBars.tsx`: the last-games bars, taking the existing
    `NflRecentBars` shape (`bars` with `heightPct`, `vsLine`, plus `linePct`)
    and a `title` per bar. Its above/below rules move over verbatim from
    `.nfl-prop-card__bars` (same variables), so the `.nfl-slate` gray scope
    still applies and no color changes.
  - `components/shared/prop-table.css`: the row grid, selected and dim states,
    the not-rateable divider, and the two-line phone layout.
- **Cleanup:** delete `NflPropCard.tsx` (`NflPropCard`, `NflPropCardGrid`) and
  the NFL-only rules in `nfl-prop-card.css`; the rules the NBA cards still read
  stay until 38d3. Drop the board's `nfl-prop-layout` panel CSS.

## Out of scope

- Tennis (38d2) and NBA (38d3) props.
- The NFL player page's "This week's lines": already rows (33c).
- The evidence panel's content (`NflEvidencePanel`, `NflPropDetailSections`).
- Any change to ranking, edge share, filters, the market pills, the period or
  position segments, the "Show all lines" rule, or board parity (33a).
- Column sorting, and the command field (38e).
- `SPORT_STATUS` on How it works: no pick changes.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Shared mini bars and row CSS (web)** - add
  `components/shared/MiniBars.tsx` and `components/shared/prop-table.css`.
  Point the existing NFL card's `RecentBars` at `MiniBars` so the new component
  ships in use and the cards look the same. *Done when:*
  - the NFL board's cards render their bars exactly as before (screenshot
    before and after at 1440px), still gray
  - `npm run build` passes
- [x] **Step 2 - `NflPropTable` on the prop board (web)** - a new
  `components/nfl/NflPropTable.tsx` (stat and anytime-TD rows, the not-rateable
  divider and dim rows, keyboard-openable row buttons) built on
  `nflPropCard(row, rank, referenceLine, now)` unchanged. On `/nfl/board`,
  replace `NflPropCardGrid` and the side panel with the table and a drawer.
  *Done when:*
  - on `/nfl/board` each line is one row; for receiving yards and anytime TD,
    the rank order and every rank, line, model and edge-share value match the
    cards on master (compared for the first 10 rows of each)
  - every gap, pick label and bar is gray
  - "Show all lines" adds the dimmed not-rateable rows below the divider
  - a row click opens the evidence panel in a drawer with the game link;
    Escape closes it; Enter on a focused row opens it
  - at 390px the rows are two lines with no horizontal scroll
  - `npm run build` passes
- [x] **Step 3 - Game page props as rows (web)** - `NflGameProps` renders
  `NflPropTable` per market with its existing drawer, toolbar, notes and empty
  states. *Done when:*
  - on a game page the rows' ranks and edge shares equal the board's for the
    same lines (board parity, 33a), for one upcoming game and one final game
  - the Period and Position segments and the switch filter rows as they did cards
  - the kickoff note and both empty states still show where they did
  - `npm run build` passes
- [x] **Step 4 - Other lines as rows, then cleanup (web)** - `NflLineOnlyProps`
  renders plain rows (no button, no drawer) using `MiniBars`. Delete
  `NflPropCard.tsx`, the NFL-only card CSS and the board's panel CSS. *Done when:*
  - "Other lines" on a game page shows one gray row per player per market, the
    name links to the player page, and the row does not open anything
  - `grep` finds no `NflPropCard` or `nfl-prop-layout` in `web/src`
  - the NBA game page's Props and Other lines cards still render as before
    (screenshot)
  - Verify passes

## Files / areas

- **Web, new:** `components/shared/MiniBars.tsx`,
  `components/shared/prop-table.css`, `components/nfl/NflPropTable.tsx`
- **Web, changed:** `pages/NflPropBoardPage.tsx`, `pages/nfl-prop-board.css`,
  `components/nfl/NflGameProps.tsx`, `components/nfl/NflLineOnlyProps.tsx`,
  `components/nfl/nfl-prop-card.css` (trimmed)
- **Web, deleted:** `components/nfl/NflPropCard.tsx`
- **No API change.** Client only.

## Data / contracts

- **No schema, API or type change.**
- **Load-bearing:**
  - **Rows read `nflPropCard` unchanged.** It stays the one NFL prop display
    model (pinned by `nflPropCards.test.ts`); a row never recomputes a rank,
    edge or label. Renaming it is out of scope.
  - **`MiniBars`** takes `NflRecentBars` (`utils/nflPropCards.ts`) and is what
    38d2's and 38d3's rows use; NBA's `lineOnlyBars` already returns that shape.
  - **`prop-table.css`** is the one prop row style 38d2 and 38d3 build on.
  - **Still holding:** the `.nfl-slate` gray scope wraps every NFL row (board
    and game page roots already carry it), and 33a's board parity.

## Testing

- No new pure logic is expected: the rows render fields `nflPropCard` and
  `recentBars` already compute, and both are tested. If a step adds a helper
  (for example a two-line label), it ships a test in `utils/` in the same diff.
- Components are verified in the running app: screenshots at 1440px and 390px,
  the rank and value comparison against master in Step 2, and the parity check
  in Step 3.
- Final gate: the Verify command from `AGENTS.md`.

## Completion evidence

- `npm --prefix web run verify && cd api && python -m pytest`, with `api/.venv`
  active: 45 web test files and 546 tests passed, the production build passed,
  and 2,608 API tests passed on 2026-10-17.
- Browser captures in `.playwright-mcp/` cover the NFL prop board and game page
  at desktop and 390px, the Step 4 Other lines table, the evidence drawer, and
  the unchanged NBA prop cards.
- Manual try path: open NFL Props, click a row to open and close the evidence
  drawer, turn on Show all lines, then open an NFL game and inspect Props and
  Other lines at desktop and phone widths.

## Notes for the AI

- Colors: never add a color rule to a row. Gap and bars read `--nfl-green` /
  `--nfl-red`, which `.nfl-slate` sets to the text color. If any NFL number
  turns green or red, the scope was lost.
- Use the `Date.now()` the card already takes once per render pass, not per row
  (the game page memoizes its clock on mount).
- Rows are `<button>` cells inside a list or table structure; keep them
  focusable with a visible focus ring, as the slate rows are.
- No UI text below 11px, including the second-line meta and bar tooltips' labels.
- The employer interview guide needs no update for a restyle step; mention at
  `/complete` if 38d as a whole changes how the app is described.
