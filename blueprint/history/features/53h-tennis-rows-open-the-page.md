# Feature: Tennis rows open the page (53h)

**From build-plan:** feature 53h (listed as `53g` in this worktree's build-plan copy until the NHL renumber lands; 53g, tennis props on the player page, is commit `29f246c5` and is not yet on master)
**Status:** complete (2026-11-02)
**Depends on:** 53g, merged to master as `50a00003`.

## Goal

A tennis prop row on the prop board and on the match page's props tab navigates to the player's page, landing on the right market tab, match and line. The evidence drawer is removed from both places, along with the drawer-only code and styles. The evidence now lives only on `/tennis/player/:id`. Display only: no new projection, edge, rank, pick or color.

## Design reference

None. Row behavior follows the slate table (`TennisSlateTable.tsx`: native link, modified-click kept, row click navigates). The landing page is the shipped 53g page.

## What reading the code settled

| Question | Answer | Consequence |
|---|---|---|
| Where is the drawer? | Two mounts: `TennisPropBoardPage` (selection in state) and `MatchPropsPanel` (selection in the URL as `?prop=<id>`). Both render `TennisPropEvidencePanel` in an antd `Drawer`. | Both go. The panel's default export, its private `FormStats`, `FormHistory`, `linePlayer` and `exactPropResult`, and `.tennis-prop-drawer` CSS are dead after this. `TennisPropEvidenceBody` and `TennisRecentBars` (53g) stay. |
| Where do rows go today? | Board: the player name is already a link to the match page props tab (`propMatchPath`, with `prop=<id>`), the row and a "View evidence" button open the drawer. Match page: the row and button open the drawer. | The name link and the row go to the player page. The match page stays reachable from the player page's "Open match picks & props" link (already in the evidence body). |
| Who is the player? | `PropLine.playerId` is null for moneyline and Win a Set rows (built from predictions) and can be null for unlinked feed lines; `MatchPrediction.p1Id/p2Id` are optional. The match page has `detail.p1.playerId` and `detail.p2.playerId`. | A pure `propPlayerPath(line, matches)` resolves the id by `line.playerId`, else the match's p1/p2 by normalized name. If it cannot, the row is not navigable: plain name, no link or button (see Open decisions). |
| Landing params | The 53g page reads `?market=`, `?match=`, `?form=`. `market` is the board category key, the same normalization `propMatchPath` already uses. | Rows link to `/tennis/player/:id?market=<statType>&match=<matchId>` plus `prop=<line id>` (below). Defaults are omitted as the page already does. |
| Which line? | A market tab can hold several lines (Cirstea's Total games has four). The 53g page lists them all; the clicked one would be lost in the stack. | Add `?prop=<line id>` to the player page: the matching section is scrolled into view and outlined with an existing border token, no color. Ignored if the id is not on the tab. |
| `?prop=` on the match page | `MatchView.prop` and `readMatchView`/`updateMatchView` exist only to select a row for the drawer; `propMatchPath` (also used by the slate) writes it. | Remove `prop` from `MatchView`, its tests and `propMatchPath`. Old bookmarked `?prop=` links keep working (the parameter is ignored). The slate's primary-prop link still goes to the match props tab. |
| Back link | The player page's crumb always says "Tennis slate" and goes to `/`. Arriving from the board that is the wrong place. | Row links pass `state: { from: <path> }`; the crumb uses it when it is the board or a match props tab, else the slate as today. Small pure guard with a test. |
| Load time | The player page needs four feeds. From the board all four are cached (shared query keys, 10 minute stale time); from the match page only PrizePicks is. | Accepted: the page already shows a loading state. Noted, not fixed here. |

## In scope

- Pure `propPlayerPath` (and its id resolver) and the `from` state guard in `utils/tennisPlayerProps.ts`, with tests.
- Player page: honor `?prop=` (scroll and outline the line) and the `from` crumb.
- `TennisPropTable`: row click and the player name navigate through links; "View evidence" becomes "Open player"; drawer props (`selectedId`, `onOpen`, `aria-haspopup`, `aria-pressed`) removed; the lines-for-review note reworded.
- `TennisPropBoardPage` and `MatchPropsPanel`: drawer, selection state, `isMobile`, the `prop` selection and the "selected line is no longer available" notice removed; the evidence hint line reworded.
- Remove `prop` from `MatchView` and `propMatchPath`, with tests.
- Delete drawer-only code and CSS; rename `TennisPropEvidencePanel.tsx` to `TennisPropEvidenceBody.tsx` (its remaining exports).

## Out of scope

- The slate table's primary-prop link beyond losing `prop=` from its URL.
- NFL, NBA and NHL files, the match page's analysis tab, `MatchRecentForm`, `useMatchRecentForm`.
- Ranking, EV, tiers, trust, filters, markets or sources on the board, and the 53g page's content.
- A cold-load speed fix for the player page; board filters as URL state.
- New colors: EV green and red and the gray pick tones stay exactly as the rows have them.

## Open decisions (defaults assumed)

- **Unresolvable rows** (no player id and no name match in the match's predictions): plain, non-clickable rows. The alternative is to send them to the match props tab. Default: plain rows, since a match page link is one click from every resolvable row.
- **Slate primary-prop link**: stays on the match props tab. Sending it to the player page too would be a separate item.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Link helpers and tests (web)** - `propPlayerPath(line, matches)` and `propPlayerId` in `utils/tennisPlayerProps.ts` returning `/tennis/player/:id?market=&match=&prop=` or null, `playerPageOrigin(state)` for the crumb (state is `{ from: <path> }`, the label is derived from the path), and a `marketKey` export from `tennisPropBoard.ts`. Removing `prop` from `MatchView` and `propMatchPath` moves to step 4, where the match panel stops reading it, so the app compiles and the drawer still works at every step. *Done when:* Vitest covers an id on the line, an id resolved from the match by name for a moneyline row, a name matching neither side, a side without an id, an unknown or null match giving null, market normalization (`1st Set Total Games` gives `1st_set_total_games`), a synthetic negative line id leaving `prop` out, and `from` accepted only for the board and a match-props path and otherwise ignored; `npm.cmd run test` and `npm.cmd run build` pass.
- [x] **Step 2 - Player page landing (web)** - `?prop=` scrolls the matching evidence section into view and outlines it with an existing border token; the crumb reads `from`. *Done when:* in the running app `#/tennis/player/<id>?market=total_games&prop=<id of the third line>` scrolls to and outlines that line and no other; an unknown `prop` changes nothing; a valid `from` shows its label and returns there, no `from` shows "Tennis slate" as today; no text under 11px.
- [x] **Step 3 - Board rows open the page (web)** - `TennisPropTable` navigates; `TennisPropBoardPage` loses the drawer, selection state and hint text. *Done when:* in the running app a board row click, Enter on the name link and the "Open player" link each land on the right player page at the right market, match and line; ctrl-click opens a new tab; a moneyline row resolves a player; an unresolvable row shows no link; rows, order, EV colors and filters are unchanged against master for one market; the crumb returns to the board.
- [x] **Step 4 - Match page rows open the page (web)** - `MatchPropsPanel` rows navigate with `from` set to that match's props tab; the drawer, `prop` selection and "no longer available" notice are removed, and `prop` is dropped from `MatchView`, `readMatchView`, `updateMatchView` and `propMatchPath` with their tests updated. *Done when:* in the running app a row on `#/tennis/match/<id>?tab=props` lands on the right player page, the crumb returns to that match tab, the match tab's player and market filters still work, and a stale `?prop=` in the URL is ignored without an error.
- [x] **Step 5 - Remove the dead drawer and Verify** - delete the panel's default export and private helpers, the `.tennis-prop-drawer`, `.tennis-prop-evidence-hint` and now-unused history/stats form CSS, and rename the file to `TennisPropEvidenceBody.tsx`. *Done when:* `rg` finds no `TennisPropEvidencePanel`, `tennis-prop-drawer` or `aria-haspopup="dialog"` on tennis rows, and `useMatchRecentForm` is no longer imported by any prop row or evidence code (the match page's own recent-form blocks still use it); `npm --prefix web run verify && cd api && python -m pytest` passes (dummy `DATABASE_URL`); a 375px capture of the board and a landed player page shows no horizontal scroll.

## Files / areas

- Changed: `web/src/utils/tennisPlayerProps.ts` (+ test), `tennisMatchView.ts` (+ test), `TennisPropTable.tsx`, `TennisPropBoardPage.tsx`, `match/MatchPropsPanel.tsx`, `TennisPlayerPage.tsx`, `player/PlayerPropTabs.tsx`, `tennis-prop-table.css`, `tennis-prop-board.css`
- Renamed: `TennisPropEvidencePanel.tsx` to `TennisPropEvidenceBody.tsx`
- Untouched: all API files, NFL/NBA/NHL files, `TennisSlateTable.tsx` (it only loses `prop=` through `propMatchPath`)

## Data / contracts

- No API change.
- Load-bearing: `/tennis/player/:id?market=<category key>&match=<matchId>&prop=<line id>&form=` and `location.state.from = <router path string>` (label derived); NBA and NHL player pages may adopt the same shape.
- `MatchView` loses `prop`; any other reader of it is found by the type error in step 1.

## Testing

- Vitest for step 1; components verified in the running app, desktop and 375px, per the testing gate.
- Manual: board row, name link, Open player and ctrl-click; a moneyline row; a Win a Set row; an unlinked feed row; a match page row and its crumb; a stale `?prop=` link; keyboard navigation through the table.

## Notes for the AI

- Display only; no signal color added or changed. The selected-line outline uses existing border tokens.
- Rows keep native link behavior; no `window.location`. HashRouter: link targets are router paths.
- Do not edit NFL, NBA or NHL files. No text under 11px. No em dashes. `npm.cmd` on Windows; this worktree's dev server uses port 3011 (3001 belongs to another session); a local API already runs on 8000.
- `docs/SportApp-Employer-Interview-Guide.md` does not exist on this machine, so skip it.
