# Feature: NBA game page

**From build-plan:** feature 20e3 (last of 20e's three parts)
**Status:** complete (2026-10-06)

## Goal

Give each NBA game its own linkable page, `/nba/game/:gameId`, built from 20e1's
`GET /nba/games/{id}` and `GET /nba/games/{id}/line-only-props`: a hero with
teams, records, tip time and the final score, the market block (no model
strip), pre-tip spread and total movement, and gray line-only prop cards with
each player's last 5 results. Slate cards become links to it. Display only, no
signal color. Completing it closes item 20e.

## Design reference

No mockup: the target is the shipped NFL game page (33a, with item 35's
"Other lines" cards), `/nfl/game/:gameId`, built from `pages/NflGamePage.tsx`,
`components/nfl/NflGameHero.tsx`, `NflLineMovementChart.tsx`,
`NflLineOnlyProps.tsx`, `pages/nfl-game.css` and
`components/nfl/nfl-prop-card.css`. The NBA page reuses those stylesheets and
class names (as 20e2 reused the slate's) under the `.nfl-slate` root, so the
gray-signal variables apply. An NBA game page is the NFL one minus the model
row, conditions, the modelled prop cards, the position filter and the sidebar
(injuries, depth, form, team stats), so the main column runs full width.

## In scope

- Types, API functions and hooks for the two 20e1 game endpoints.
- `utils/nbaGame.ts` (pure): the market block's cells.
- `utils/nbaLineOnly.ts` (pure): NBA market labels and order, and cards
  grouped by market, reusing `lineOnlyBars` and `mainRung` from
  `utils/nflLineOnly.ts`.
- `NbaGamePage` at `/nba/game/:gameId`, registered in `SPORT_PAGES.nba.details`.
- Slate cards become links to the game page.
- Reuse of `NflLineMovementChart` for NBA by narrowing its prop to the fields
  it reads (type-only change, NFL output unchanged).

## Out of scope

- Any API change: 20e1's responses are used as they are.
- Any projection, edge, P(over), rank or signal color (20g).
- An NBA player page; player names are plain text.
- A position or market filter on the line-only cards (two players a game on
  today's board).
- Injuries, rest, team stats, recent form: no NBA ingest feeds them yet.
- Moving or renaming the shared `nfl-*` classes to a sport-neutral prefix.
- Fixing in-play odds rows, if 20d stores any (see Notes).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Game types, API, hooks and market cells** - in
  `types/nba.ts`, `NbaLineStep`, `NbaLineHistory`, `NbaGameDetail` (=
  `NbaSlateGame` plus `lineHistory`); `fetchNbaGame(id)` in `api/nba.ts`;
  `useNbaGame(id | null)` in `hooks/useNba.ts` (key `['nba', 'game', id]`,
  5-minute `staleTime`, disabled for a null id, `retry:
  retryUnlessNotFound`). In `utils/nbaGame.ts`:
  - `parseGameId` re-exported from `utils/nflGame.ts`.
  - `nbaGameMarket(game)`: three cells, each `{ value, detail }`:
    - **Spread**: favorite label (`spreadLabel`, `DET -2.5`; `PK` at 0),
      detail `-105 / -115 · draftkings` (favorite's side first).
    - **Win probability**: `DET 53.2%` from the stored de-vigged
      `homeWinProbability`, for whichever side is above 50% (home at exactly
      50%), detail `DET -125 / BOS +105 de-vigged · draftkings`.
    - **Total**: `221.5`, detail `o -110 / u -110 · draftkings`.
    - A missing market gives `--` with detail `Not stored`; all three missing
      gives null, so the page shows one "No book odds stored" line.

  *Done when:* `nbaGame.test.ts` passes for: home favorite, away favorite,
  pick'em spread, a 50/50 moneyline, each market missing alone, all missing
  (null), and the book named per cell when the three come from different
  books; `npm run build` and `npm run test` pass. No UI yet.

- [x] **Step 2 - Page shell, hero, market block and slate links** -
  `NbaGamePage` registered at `/nba/game/:gameId` in `SPORT_PAGES.nba.details`:
  - **Crumb:** `← NBA slate` to `/nba?date=<gameDate>`, so Back lands on the
    game's own day.
  - **Hero** (`.nfl-game-hero`): team badges and codes, full team name and
    record beneath (`No games yet` at 0-0); middle shows the tip time in
    Central, the game type for `PIN` / `PST` ("Play-in", "Playoffs"), and the
    state from `nbaSlateCard` ("Tipped off", "Final", "Postponed"); a final
    shows the score with the loser dimmed.
  - **Body by state** (reusing `nbaSlateCard(detail, now)` so page and card
    cannot disagree):
    - upcoming or started: the market block (`.nfl-game-card`, `.nfl-game-mm`
      with one Market row and no model row; caveat "Latest stored price"),
      plus "Scores load the morning after the game" when started;
    - final: a "Closing lines" block with the card's graded final cells, or
      "No closing lines stored";
    - postponed or canceled: "Postponed: no market shown" (or Canceled).
  - **Layout:** the main column alone (`.nfl-game-layout` gets an NBA
    modifier for one column; one new rule in a small `pages/nba-game.css`).
  - **States:** loading and error via the shared components; a non-numeric
    id or a 404 shows "Game not found. It may be a preseason game, or the
    link is wrong." with the crumb to `/nba`.
  - **Slate links:** `NbaSlateGameCard` renders as a `Link` to the game page,
    as `NflSlateGameCard` does.

  *Done when:* in the running app, clicking BOS at DET on `/nba` opens
  `/nba/game/21320` with NBA highlighted in the nav, the hero (BOS at DET,
  Boston Celtics / Detroit Pistons, "No games yet", `Tue, Oct 20, 2:00 PM CT`)
  and the market matching its slate card (on 20e1's run: DET -2.5, DET 53.2%
  de-vigged, 221.5, each naming `draftkings`; odds refresh twice a day, so
  the slate card is the reference, not these numbers); Back returns to `/nba?date=2026-10-20`; a 2026-04-12 final
  (ORL 108 at BOS 113) shows the score with ORL dimmed, records 45-36 and
  55-26, and "No closing lines stored"; `/nba/game/22521` (a `PRE` id),
  `/nba/game/1` (NFL) and `/nba/game/abc` show the not-found state; `/nfl`
  game pages are unchanged; `npm run build` and `npm run test` pass.

- [x] **Step 3 - Line movement** - narrow `NflLineMovementChart`'s `detail`
  prop to `{ homeTeam, awayTeam, startUtc, lineHistory }` (structural,
  `utils/nflLineMovement.ts` already reads only the history), and render it on
  the NBA page under the market block. Caveat text stays "Before kickoff" on
  NFL; the component takes an optional `caveat` so NBA reads "Before tip-off".

  *Done when:* `/nba/game/21320` shows Spread and Total panels from
  `draftkings` whose open and current lines match the slate card's movement
  detail ("no move" while one run is stored); the 2026-04-12 final shows "No
  spread or total prices stored for this game yet."; an NFL game page's
  movement panels read the same as a screenshot taken before the change;
  `npm run build` and `npm run test` pass.

- [x] **Step 4 - Line-only prop cards** - `types/nba.ts` gains
  `NbaLineOnlyRecent`, `NbaLineOnlyLine`, `NbaLineOnlyProps`;
  `fetchNbaLineOnlyProps(id)` and `useNbaLineOnlyProps(id | null)` (key
  `['nba', 'game', id, 'line-only-props']`). `utils/nbaLineOnly.ts`:
  - `NBA_LINE_ONLY_MARKETS` in `NbaLineOnlyMarket` order and
    `nbaMarketLabel` (Points, Rebounds, Assists, 3-pointers made, Blocks,
    Pts + reb + ast, Pts + reb, Pts + ast, Reb + ast, Double-double; an
    unknown market shows its raw key).
  - `nbaLineOnlyGroups(lines)`: one row per player per market with every rung
    (sorted by line), the player's team and position, `overCount` / `count`
    against the standard line (NFL's rule: values strictly above), markets in
    the order above, rows by player name.
  - `lineOnlyBars` and `mainRung` in `utils/nflLineOnly.ts` widen their input
    to `{ value, opponent }` recent games (type-only; NFL tests unchanged).
  - Double-double values are 1 / 0 (20c's settlement rule), so bars and
    "over N of 5" work against whatever line is stored; the footer shows
    `yes` / `no` instead of `1` / `0` for it.

  `NbaLineOnlyProps` renders an "Other lines · not modelled · recent results
  only" section of `.nfl-prop-card` cards (badge: team code; name plain text;
  small: position and market; main rung and "Also" rungs; gray bars with the
  standard line dashed; values oldest to newest; "over N of 5"). Hidden when
  the game has no linked lines; its own loading and error text, so a failure
  never blanks the page.

  *Done when:* `nbaLineOnly.test.ts` passes for grouping and ordering,
  rungs collapsed per player, a NULL value excluded from the count, a player
  with no earlier games (no bars, "No earlier games"), no standard line
  (no count), double-double labels, and an unknown market; on
  `/nba/game/21320` the section shows 61 lines as cards for Cunningham and
  Tatum across the stored markets, each with up to 5 recent results; the
  2026-04-12 final shows no section; a DOM audit finds no text under 11px and
  nothing computing to the theme's green or red on either page; `npm run
  build` and `npm run test` pass.

## Files / areas

- New: `web/src/pages/NbaGamePage.tsx`, `web/src/pages/nba-game.css`,
  `web/src/components/nba/NbaGameHero.tsx` (hero and market block),
  `web/src/components/nba/NbaLineOnlyProps.tsx`, `web/src/utils/nbaGame.ts`,
  `web/src/utils/nbaGame.test.ts`, `web/src/utils/nbaLineOnly.ts`,
  `web/src/utils/nbaLineOnly.test.ts`
- Changed: `web/src/types/nba.ts`, `web/src/api/nba.ts`,
  `web/src/hooks/useNba.ts`, `web/src/routes/sportPages.tsx`,
  `web/src/components/nba/NbaSlateGameCard.tsx` (becomes a link),
  `web/src/components/nfl/NflLineMovementChart.tsx` (prop type and optional
  caveat only), `web/src/utils/nflLineOnly.ts` (input types only)
- Reused, unchanged: `pages/nfl-slate.css`, `pages/nfl-game.css`,
  `components/nfl/nfl-prop-card.css`, `utils/nbaSlate.ts`,
  `utils/nflLineMovement.ts`, `LoadingState`, `ErrorState`, `isNotFound`,
  `retryUnlessNotFound`

## Data / contracts

- Reads 20e1's `GET /nba/games/{id}` (`NbaGameDetailResponse`) and
  `GET /nba/games/{id}/line-only-props` (`NbaLineOnlyPropsResponse`)
  unchanged; types in `types/nba.ts` mirror `app/schemas/nba.py`.
- **Load-bearing:**
  - **One NBA game page.** The route `/nba/game/:gameId`. Later game-level
    NBA display (injuries, 20g's modelled props, a model row) extends this
    page and 20e1's game response, or adds a sibling under
    `/nba/games/{id}/`, never another page (33a's rule).
  - **Page and card parity.** The hero and final block read `nbaSlateCard`,
    so a game page never disagrees with its slate card.
  - **`NflLineMovementChart` is shared** by both sports through its narrowed
    prop; `lineOnlyBars` and `mainRung` likewise.
- No schema change, no API change.

## Testing

- Test gate is on: `utils/nbaGame.test.ts` (Step 1) and
  `utils/nbaLineOnly.test.ts` (Step 4); the existing `nflLineOnly.test.ts`
  and `nflLineMovement.test.ts` must pass unchanged after the type widening.
  Components and the page ride on build plus screenshots.
- `cd web && npm run build` (typechecks) and `npm run test` after each step.
- Screenshots (desktop and 390px wide) via the Playwright MCP, or Playwright
  for Python from `api/.venv` if the MCP browser is held, against the web dev
  server (3001) and API (8000).

## Notes for the AI

- TanStack Query only; components call hooks, never axios. `~/` imports, no
  `any`, theme variables rather than hex.
- Times are Central (`America/Chicago`), as on the slate.
- Green is a signal color: nothing on this page is green or red. Keep the page
  under the `.nfl-slate` root, which sets the NFL signal variables to the
  text color.
- No UI text under 11px, micro-labels included.
- Don't change NFL behavior: the two NFL edits are type narrowing and one
  optional prop with NFL's current text as its default. Re-check an NFL game
  page after Steps 3 and 4.
- **Possible in-play odds rows.** `nba_odds` matches events within 6 hours of
  tip-off and does not visibly filter out games already started, so a
  started game's "latest stored price" may be in-play. Movement and closing
  lines are pre-tip only (20e1's rule), so the final block is safe. If Step 2
  finds post-tip rows stored, note it for a `/fix` rather than widening this
  feature.
- 20e1's line-only endpoint returns linked lines only; unlinked lines count
  on the slate but never appear as cards (20e1's scope).

## Results

Proved with the Playwright MCP browser against the owner's running web dev
server (3001) and API (8000) on 2026-10-06.

- **Slate link:** clicking BOS at DET on `/nba` opens `/nba/game/21320` with
  NBA highlighted in the nav; "← NBA slate" returns to `/nba?date=2026-10-20`.
- **Hero and market (21320):** Boston Celtics · No games yet, Detroit Pistons ·
  No games yet, `TUE, OCT 20, 2:00 PM CT`; DET -2.5 (`-105 / -115 ·
  draftkings`), DET 53.2% (`DET -125 / BOS +105 de-vigged · draftkings`),
  221.5 (`o -110 / u -110 · draftkings`), matching the slate card.
- **Final (17568):** ORL 108 at BOS 113 with 108 dimmed, records 45-36 and
  55-26, "No closing lines stored", "No spread or total prices stored for this
  game yet.", and no "Other lines" section.
- **Not found:** `22521` (`PRE`), `1` (NFL) and `abc` all show "Game not
  found. It may be a preseason game, or the link is wrong."
- **Line movement (21320):** Spread "DET -2.5, no move" and Total "221.5, no
  move", `draftkings · no moves` (one stored odds run), caveat "Before
  tip-off".
- **Line-only cards:** 21320 shows 16 cards covering all 61 lines (Cunningham,
  Tatum) across 8 markets, each with 5 recent results (Cunningham Points 24.5:
  `27 · 19 · 39 · 21 · 13`, over 2 of 5). 21318 shows all 10 markets,
  double-double reading yes / no (Wembanyama `yes · no · no · yes · yes`).
- **390px:** single column, no horizontal overflow.
- **Rules:** a DOM audit on 21320 and 17568 found no text under 11px and
  nothing computing to the theme's `#00c805` or `#ff5000`.
- **NFL unchanged:** `/nfl/game/65`'s line movement card screenshot has the
  same MD5 before and after Step 3; its "Other lines" still renders (21
  cards).
- **Checks:** `npm run build` passes; `npm run test` 493 passed (7 in
  `nbaGame.test.ts`, 9 in `nbaLineOnly.test.ts`; `nflLineOnly.test.ts` and
  `nflLineMovement.test.ts` unchanged and passing).

**Beyond the spec:**
- `overAgainstStandard` in `utils/nflLineOnly.ts` is now exported (with the
  widened recent-game type) so NBA reuses the over count instead of copying
  it; `LineOnlyRecentValue` names that type.
- Slate cards gained NFL's "Open game →" footer label.

**Not exercised live:**
- A tipped-off, postponed or play-in game page (no current game is in those
  states); the states come from `nbaSlateCard`, which 20e2's tests cover.
- In-play odds rows: no NBA game has tipped off since 20d began storing odds,
  so whether 20d stores post-tip rows is still unknown. If it does, a started
  game's "Latest stored price" may be in-play (closing lines stay pre-tip).
- Every double-double line on today's board is goblin or demon, so those
  cards show no "over N of 5" (NFL's rule counts against the standard line
  only).
