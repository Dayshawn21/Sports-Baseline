# Feature: NBA rows open the page (53c)

**From build-plan:** feature 53c (third sub-item of 53, NBA, NHL and tennis player pages)
**Status:** complete (2026-11-03)
**Branch:** this worktree's branch (`claude/nba-player-page-e5edff`), merged with `origin/master` (53a, 53b, 53b2, 53d to 53f are on it)

## Goal

A prop row on the NBA prop board (`/nba/board`), a prop row on the game page's
Props and Other lines sections, and a gap box in the game page's digest each
navigate to that player's page (`/nba/player/:id`, built in 53b and 53b2)
instead of opening the evidence drawer. The link opens on the market the row
shows and on that game's date. The three NBA drawers and the evidence panel they
host are then removed, so every NBA prop for a player is read on one page with no
evidence hidden behind a click. Display only: no new projection, edge, rank or
pick; gray signal colors; rows keep their current order.

## Design reference

None captured. 50b did the same for NFL (`blueprint/history/features/50b-rows-open-the-page.md`)
and 53f for NHL; the target page already exists. The visual change is small
(the player name becomes a link, the selected-row highlight goes), so the check is
screenshots at 1440 and 390 px of the board and game page.

## What reading the code settled

| Question | Answer | Consequence |
|---|---|---|
| Drawer surfaces | Three, each with its own `Drawer` and focus-restore code: `NbaPropBoardMarket` (board), `NbaProps` (game page, modelled) and `NbaLineOnlyProps` (game page, double-double). All render `NbaPropEvidencePanel`. The game page's `NbaSlateDigest` also takes an `onOpen` that opens the modelled drawer from a box. | All four entry points become links; the three drawers, the panel and the `nba-prop-drawer` CSS go. |
| Row shape | `NbaPropTable.tsx` holds every row: `Player` renders the name as a `<button>`, and a row click opens it (`openFromRow`). Board rows carry their `game` and a key; game page rows carry neither. | Rows get an optional `pathFor(playerId, market)`: when given, the name is a `<Link>` and a plain click on the row follows it (as 50b did for NFL). Step 2 uses it on the board, Step 3 on the game page, then Step 3 deletes the button mode and the selected state. |
| Link target | `nbaPlayerPath(playerId, { date, market })` (53b) is the only place the page URL is built. The board knows its `date`; the game page knows `gameDate` (`NbaGameDetail`). `NbaGapGame` has no date. | Rows and digest boxes link through `nbaPlayerPath`. The board passes `board.data.date`. The game page passes `gameDate` as a prop on `NbaProps` and `NbaLineOnlyProps` (no change to `NbaGapGame`). `form` is never added (53b2's contract). |
| Digest | `NbaSlateDigestItem` has `gameId`, `playerId` and `marketKey` (the stored market). The slate and board pages already link boxes to the game page, not a drawer. | Only the game page's digest changes: its `onOpen` prop is replaced by a `playerPath` function. The slate and board digests keep linking to the game page. |
| Back | The board's view (`date`, `market`) is already in its URL. The player page's crumb goes to the game page, or to the board for a player with no game. 50b marks a board arrival with router state `FROM_BOARD` and `arrivedFromBoard(state)` (in `utils/nflPlayer.ts`, sport-neutral) and the NFL page then uses `navigate(-1)`. | Board links pass `state={FROM_BOARD}`. The NBA player page crumb reads `arrivedFromBoard` and goes back one step with the label "NBA props", restoring the market and date. From the game page the existing crumb to the game page stays (it opens on its Props tab). Imported as they are; no NFL file edited. |
| Evidence CSS | The player page's `NbaInjuryEvidence` and `NbaOpponentEvidence` use `.nba-prop-evidence__section` (and its `h4`, `p` rules), which live in `nba-prop-table.css` beside the drawer-only rules. 53b recorded that deleting the panel needs these moved first. | Step 1 moves exactly those shared rules into a new `components/nba/nba-evidence.css` imported by the two components, with no visual change, before anything is deleted. The panel keeps working during Steps 1 to 3. |
| Other consumers | `NbaPropEvidencePanel` is imported only by the three drawer hosts. `useIsMobile` (drawer width) is used elsewhere. | The panel file and its remaining `nba-prop-evidence__*` rules are safe to delete in Step 4. `useIsMobile` stays. |
| Scroll restore | NBA board rows are not a scroll-restored list today. | Browser Back restores the URL view; no new scroll restoration (out of scope). Focus return to the opened row, which the drawer code did by hand, goes with the drawer. |

## In scope

- Player name links and whole-row click on the board and the game page's two tables, to `nbaPlayerPath(playerId, { date, market })`; ctrl, cmd, shift and middle click keep native link behavior.
- The game page digest boxes link to the player page.
- Board arrivals mark `FROM_BOARD`; the player page crumb returns to the board view.
- Removing the three drawers, `NbaPropEvidencePanel`, the selected-row state (`selected`, `onOpen`, `selectedKey`, `data-row-key`, `aria-pressed`), the focus-restore refs and the drawer-only CSS; moving the shared evidence CSS (Step 1).

## Out of scope

- Any API field, endpoint or ingest, and any NFL, NHL or tennis file.
- The slate and board digests (they already link to the game page).
- Scroll restoration, a new back-navigation system, or changes to what the player page shows.
- Sorting, ranking or coloring by value; rows keep tip time then name (board) and market then name (game page).
- Tennis drawers (53h is separate).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.

## Build steps

- [x] **Step 1 - Move the shared evidence CSS** - create `components/nba/nba-evidence.css` holding the `.nba-prop-evidence__section` rules (section spacing, `h4` and `h4 small`, `p` colors) that `NbaInjuryEvidence` and `NbaOpponentEvidence` use, import it from both, remove those rules from `nba-prop-table.css`, and drop the `nba-prop-table.css` import from `NbaPlayerMarketSection`. *Done when:* the production build passes; on `#/nba/player/322853?date=2026-11-02&market=rebounds` the injury and opponent sections have the same computed margin, font size and color as before (compared with `getComputedStyle` on the section, its `h4` and its `p`); the game page drawer still shows the same sections (open a row and compare); `npm --prefix web run test` passes.
- [x] **Step 2 - Board rows are links** - `NbaPropTable` rows take an optional `pathFor`; with it the name is a `Link` (state `FROM_BOARD`) and a plain row click navigates; `NbaPropBoardMarket` passes `pathFor` built from `nbaPlayerPath(playerId, { date, market })` using the board's date, and its `Drawer`, selection and focus code go; the board page passes `date` and stops passing `modelVersion`. *Done when:* in the running app a click on a modelled row and on a double-double row on `#/nba/board?date=2026-11-02&market=points` opens `#/nba/player/<id>?date=2026-11-02&market=points` on that tab; the name is a focusable link and middle-click opens a new tab; the browser Back button returns to the board on the same date and market (the crumb change is Step 4); the row no longer shows a selected highlight; `rg "Drawer" web/src/components/nba/NbaPropBoardMarket.tsx` finds nothing; a screenshot at 1440 and 390 px shows no horizontal page scroll and no text under 11px; the production build passes.
- [x] **Step 3 - Game page rows and digest are links** - `NbaProps` and `NbaLineOnlyProps` take `gameDate`, pass `pathFor`, and lose their `Drawer`, selection and focus code; `NbaSlateDigest` replaces `onOpen` with `playerPath` and the game page's digest boxes become links; `NbaPropTable` loses the button mode, `selected`, `onOpen`, `openFromRow` and `data-row-key`. *Done when:* in the running app a row in the Props section, a row in Other lines and a digest box on `#/nba/game/<id>` each open the player page on the right market and the game's date, and the crumb returns to that game page; the slate and board digests still link to the game page; `rg "Drawer|NbaPropEvidencePanel" web/src/components/nba` finds only the panel file itself; screenshots at 1440 and 390 px show no horizontal page scroll; build and tests pass.
- [x] **Step 4 - Back from the board, and delete the panel** - the player page crumb returns to the board with "NBA props" when `arrivedFromBoard(location.state)` (otherwise unchanged); delete `NbaPropEvidencePanel.tsx` and the `nba-prop-drawer` and remaining `nba-prop-evidence__*` rules; remove any import left unused. *Done when:* arriving from the board shows the "NBA props" crumb and clicking it returns to the same date and market; arriving from the game page still shows the "AWAY @ HOME" crumb; a direct visit with no game shows "NBA props" linking to the board for that date as today; `rg "NbaPropEvidencePanel|nba-prop-drawer|nba-prop-evidence__(head|summary|rungs|recent|caveat|empty)" web/src` finds nothing; build and tests pass.
- [x] **Step 5 - Verify** - the Verify command and a last click-through. *Done when:* `npm --prefix web run verify && cd api && python -m pytest` passes (dummy `DATABASE_URL`); `git diff origin/master --stat` shows no NFL, NHL or tennis file changed; a click-through of a board row, a game page row, an Other lines row and a digest box lands on the right market on the right date and returns correctly; screenshots at 1440 and 390 px of the board, the game page and the player page are attached to the review.

## Files / areas

- `web/src/components/nba/NbaPropTable.tsx`, `NbaPropBoardMarket.tsx`, `NbaProps.tsx`, `NbaLineOnlyProps.tsx`, `NbaSlateDigest.tsx`
- New `web/src/components/nba/nba-evidence.css`; `nba-prop-table.css` (rules moved and removed), `NbaInjury.tsx` and `NbaOpponentEvidence.tsx` (one import each)
- `web/src/components/nba/NbaPlayerMarketSection.tsx` (drop one stylesheet import)
- `web/src/pages/NbaPropBoardPage.tsx`, `NbaGamePage.tsx` (pass `gameDate`), `NbaPlayerPage.tsx` (crumb)
- Deleted: `web/src/components/nba/NbaPropEvidencePanel.tsx`
- Read-only reuse: `nbaPlayerPath` in `utils/nbaPlayer.ts`, `FROM_BOARD` and `arrivedFromBoard` in `utils/nflPlayer.ts`

## Data / contracts

- No new API shape and no new URL shape: links are `nbaPlayerPath(playerId, { date, market })`, the contract 53b locked. `form` is never added to a row link.
- Router state `{ from: 'board' }` (`FROM_BOARD`) marks a board arrival; it is read only by the player page crumb.
- Row identity stays `playerId` plus market; `NbaBoardRow.key` stays for React keys.

## Testing

- No new pure logic: links go through `nbaPlayerPath` (53b, tested) and `arrivedFromBoard` (NFL's, tested). If Step 2 or 3 needs a small helper to pick the market or date for a row, it ships with a Vitest case in `nbaPlayer.test.ts`.
- UI is verified in the running app with screenshots and click-throughs; the local API needs the Windows selector-loop launcher (`C:\dev\SportAppV2\api\.venv`, `DATABASE_URL` from the main checkout's `api/app/.env`), on ports other than 8000 and 3001; this worktree's `web/node_modules` is a junction to the main checkout's.
- Existing NFL, NHL and NBA tests must pass unchanged, apart from tests that exercised removed drawer code (none found).
- Keep the machine light: stop the dev servers before running the full Verify, since a past run failed from process exhaustion.

## Notes for the AI

- Display only. Gray signal colors; no sorting or coloring by value; no UI text under 11px; no em dashes in code, comments or docs.
- Do not edit any NFL, NHL or tennis file. `utils/nflPlayer.ts` is imported, not changed.
- Import via the `~/*` alias, HashRouter links, `Link` from `react-router-dom`.
- Each step must leave the app working: until Step 3 deletes it, the game page keeps its drawer path (`pathFor` is optional).
- A row's "game" cell link on the board (to the game page) stays; only the player name and the row click change.
- Delete tracked files with `git rm`.
