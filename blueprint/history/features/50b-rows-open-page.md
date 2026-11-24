# Feature: Rows open the page (50b)

**From build-plan:** feature 50b (under 50, NFL props as player pages)
**Status:** complete (2026-11-02)
**Branch:** `feature/nfl-rows-open-page`

## Goal

A prop row on the NFL prop board, a prop row or digest box on the game page, and a
line row on the player page's lines card all navigate instead of opening a
drawer. The first two land on `/nfl/player/:id?market=<market>` (the section 50a
built for that market); the lines card scrolls to its own section on the same
page. The three NFL prop drawers, `useNflDrawerFocus`, `NflEvidencePanel` and their
CSS are then removed, so every prop for a player is visible on one page and no
evidence is hidden behind a click.

## Design reference

None. 50a built the target page; this step only changes how a reader gets there.
The 50a archive (`blueprint/history/features/50a-player-page-evidence.md`) records
the section ids, the `?market=` contract and the HashRouter scroll rule.

## In scope

- `NflPropTable` rows (board and game page) render the player name as a real
  `<Link>` to `nflPlayerMarketLink(playerId, market)`; a plain click anywhere on
  the row follows it. Ctrl, Cmd, Shift and middle click keep native link behavior.
- Game-page digest boxes link to the same URL instead of opening a drawer. The
  board and NFL intelligence digests keep linking to the game page (they are not
  drawers); see Open questions.
- Player-page lines card rows become links that set `?market=` with `replace` and
  scroll to their own section, the way the 50a jump list does.
- Selected-row state: the drawer's "selected" row (highlight and `aria-pressed`)
  goes away on the board and game page, since nothing is open. The player page's
  selected state (the section from `?market=`, and now the matching lines card
  row) stays.
- Back: returning to the board or game page restores the view (week, position,
  market, game filter, "include alternates") and puts scroll and focus back on the
  row or digest box that was opened. The view moves into the URL for this.
- A reader arriving on the player page from a row starts at the right place:
  the matching section for a market link, the top otherwise (see Contracts).
- Removed: the board, game page and lines card `Drawer`s, `useNflDrawerFocus`,
  `NflEvidencePanel`, the pieces only it used (`DetailHeader`, the
  `NflEvidenceContext` wrapper, `showPlayerLink` / `showGameLink` plumbing), and
  the `.nfl-game-drawer` / `.nfl-player-drawer` CSS in `nfl-matchup-context.css`,
  `nfl-game.css` and `nfl-player.css`.
- `nflPlayerMarketLink` drops its trailing `#game-log` (see Contracts).

## Out of scope

- NBA and tennis drawers (`nba-prop-drawer`, tennis `Drawer`s): a later item.
- Kept as is: the Ask drawer and the mobile nav menu drawer in `App.tsx`.
- Any change to projections, ranks, edges, P(over), versions, ordering, and
  signal colors. Gray stays gray; targets references keep their note and
  "reference" label. No new green or red.
- New API routes, columns or types beyond two display-free ids on the digest item.
- Scroll restoration for the rest of the app. Only the NFL board and game page get
  the restore behavior here.
- Deep links for line-only markets (`NflLineOnlyProps` links to
  `?market=<line-only market>`, which names no section on the player page today).
  Behavior unchanged apart from the dropped `#game-log`.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Link and digest contract** - in `web/src/utils/nflPlayer.ts` drop `#game-log` from `nflPlayerMarketLink`; in `web/src/utils/nflSlate.ts` add `playerId` and `marketKey` (the raw market, since `market` there is a display label with " reference" appended) to `NflSlateDigestItem`, filled by `slateDigest`. Update the two existing `nflPlayerMarketLink` assertions. *Done when:* `nflPlayer.test.ts` expects `/nfl/player/40440?market=kicking_points` and the encoded `a&b` case, `nflSlate.test.ts` shows the new fields for a normal row and a Rec Targets reference row (label unchanged, `marketKey` raw); `npm --prefix web run test` green and `tsc -b` still compiles (digest consumers untouched).
- [x] **Step 2 - Player page lands correctly** - (a) `NflPlayerLines` rows become `<Link to="?market=..." replace>` keeping the `nfl-player-line` grid, calling the same section scroll as the jump list (share one helper, do not copy it), with `aria-current` on the row whose section is selected; the drawer in this component and its `useState`, `useIsMobile` and `NflEvidencePanel` imports go. (b) `NflPlayerGameLog` takes the page's prop markets and scrolls to the log only when `selectedPropMarket(params, propMarkets)` is null, so a kicker's `?market=field_goals_made` lands on its prop section (50a's log scroll would otherwise win and jump past it). (c) A `useLayoutEffect` on `playerId` in `NflPlayerPage` scrolls to the top when the URL has no section market (layout effects run before the section's scroll effect), so arriving with cached data at a deep scroll position does not open mid-page; add it only if the live check reproduces the mid-page landing. *Done when:* on a WR page, clicking each lines card row scrolls to that market's section and marks it selected, and re-clicking the selected row scrolls again; Tab reaches each row, Enter follows it; a kicker opened at `#/nfl/player/<id>?market=field_goals_made` lands on the field goals section; a kicker with `?market=punts` style log-only column still lands on the game log; `npm --prefix web run build` passes.
- [x] **Step 3 - Rows and digest link, drawers off the board and game page** - `NflPropTable`: the `prop-table__open` button becomes a `<Link>` to `nflPlayerMarketLink(row.playerId, row.market)`; the `tr` click calls `navigate` only for an unmodified left click whose target is not inside `a` or `button` (the mini bars are buttons on the game page); remove the `selectedLineId` and `onOpen` props, `aria-pressed` and the `is-selected` class from this table's rows. `NflSlateDigest`: replace `onOpen` with a `linkFor` option; the game page passes the player link and the boxes' `aria-label` reads "open player page"; the board and intelligence page keep the game link. Delete `Drawer`, `selectedLineId`, `alternates`, `useNflDrawerFocus` and `NflEvidencePanel` use from `NflPropBoardPage` and `NflGameProps`. *Done when:* on the board and a game page, clicking a name or any non-control part of a row opens `#/nfl/player/<id>?market=<that row's market>` on its section; ranks, `#` column, model, gap text and gray classes are byte-identical in the DOM before and after for the same slate (compare a captured row); nothing on either page opens a drawer; Rec Targets rows still show "reference" and no rank; `npm --prefix web run build` passes.
- [x] **Step 4 - View state in the URL (pure part)** - new `web/src/utils/nflViewParams.ts`: `parseBoardView(params)` and `boardViewSearch(view)` for `season`, `week`, `position`, `market`, `game`, `all` (board), and `parseGameView` / `gameViewSearch` for `position` and `all` (game page). Invalid, missing or out-of-range values fall back to the default; defaults are omitted from the string; `position` is validated against `NFL_POSITION_OPTIONS`. *Done when:* `nflViewParams.test.ts` covers a full round trip, each default omitted, a non-numeric week, an unknown position, `game=all` versus a numeric game, and an empty query; green.
- [x] **Step 5 - Board and game page read and write the view** - `NflPropBoardPage` and `NflGameProps` replace their local `useState` filters with `useSearchParams` through step 4's helpers, writing with `replace` so filter clicks do not stack history entries. The board's "reset market when position or week changes" effect moves into the handlers (a mount effect would clear a restored `market`). *Done when:* reloading `#/nfl/board?position=WR&market=receptions&all=1&week=9` shows that exact view; changing a filter does not add a Back entry; a bad value (`week=abc`, `position=zz`) loads the default view with no error; the market pill still falls back when the chosen market is empty for a new position.
- [x] **Step 6 - Back restores scroll and focus** - new `web/src/utils/nflOpenedRow.ts` (pure): `openedRowKey(source, lineId)` and a `sessionStorage` wrapper (try/catch, as `adminAuth.ts` does) that stores `{ path, key }` and returns it once for a matching `pathname+search`. New hook `useRestoreOpenedRow(ready)` replaces `useNflDrawerFocus`: on a `POP` navigation, once rows have rendered, it focuses the element whose `data-open-key` matches and scrolls it to the center; it never runs on a fresh visit or a missing target. Table links get `data-open-key="table:<lineId>"`, digest links `digest:<lineId>`, and clicking records the key. *Done when:* `nflOpenedRow.test.ts` covers store, take-once, mismatched path, malformed JSON and unavailable storage; in the app, board row 30 of Receptions then browser Back lands on that row, focused (visible ring), same market and filters; a game page digest box does the same and restores the box, not the matching table row; a fresh visit to the board does not move focus.
- [x] **Step 7 - Remove the dead code** - delete `components/NflEvidencePanel.tsx`, `hooks/useNflDrawerFocus.ts`, `DetailHeader` (and `.nfl-prop-detail__player-link` if only it used it), the `NflEvidenceContext` wrapper (keep `NflUsageContext` and `NflOpponentAllowed`), the `showPlayerLink`/`showGameLink` props, and the `.nfl-game-drawer` / `.nfl-player-drawer` rules in `nfl-matchup-context.css:27`, `nfl-game.css:129`, `nfl-player.css:87`, plus the now-orphan `.nfl-player-line` button resets if unused. Confirm `DetailGameMarket`'s `gameLink` is still used before removing it. *Done when:* `grep` over `web/src` for `NflEvidencePanel|useNflDrawerFocus|nfl-game-drawer|nfl-player-drawer|DetailHeader|NflEvidenceContext\b` returns nothing; `Drawer` remains only in `App.tsx` (Ask, mobile menu) and the NBA and tennis files; the player page sections look the same as before (the 50a screenshot comparison); `npm --prefix web run verify` passes.
- [x] **Step 8 - Responsive, keyboard and final gate** - check 1280px and 390px for the board, a game page and a WR, an RB and a kicker player page: no horizontal page scroll, the lines card rows readable as links, focus ring visible on name links and lines card rows, no keyboard trap (there is no drawer to dismiss), row hover and focus not color alone. Run the full gate. *Done when:* screenshots of those views show no overflow; `npm --prefix web run verify && cd api && python -m pytest` passes.
- [x] **Step 9 - Tabs under the context card, one prop at a time** - added at the user's request after seeing the page: the prop tabs move below the usage and game market card, and only the prop the tabs select is shown (the first when `?market=` is absent or unknown). This supersedes 50a's all-props-expanded layout. Tabs are links with `replace` and never scroll; a `?market=` deep link and a lines card click scroll to the tabs; the lines card marks the same prop as the tabs. `NflPlayerProps` is keyed by player so the deep-link scroll runs once per player. *Done when:* a QB page with seven props shows one section at a time under the tabs; a tab click changes the section without moving the page; `?market=rushing_attempts` opens on that tab with the tabs at the top of the viewport; `npm --prefix web run verify` passes.

## Files / areas

- `web/src/utils/nflPlayer.ts`, `nflSlate.ts`, new `nflViewParams.ts`, new `nflOpenedRow.ts`, each with its test (steps 1, 4, 6)
- `web/src/components/nfl/NflPropTable.tsx`, `NflSlateDigest.tsx`, `NflGameProps.tsx`, `NflPlayerLines.tsx`, `NflPlayerGameLog.tsx`, `NflPlayerProps.tsx` (shared scroll helper) (steps 2, 3)
- `web/src/pages/NflPropBoardPage.tsx`, `NflPlayerPage.tsx` (steps 2, 3, 5)
- New `web/src/hooks/useRestoreOpenedRow.ts`; deleted `useNflDrawerFocus.ts`, `components/NflEvidencePanel.tsx` (steps 6, 7)
- `web/src/components/nfl/NflPropDetailSections.tsx`, `NflEvidenceContext.tsx` (step 7)
- CSS: `nfl-matchup-context.css`, `pages/nfl-game.css`, `pages/nfl-player.css`, `nfl-prop-table.css` if a link style is needed (steps 2, 3, 7)
- Untouched: `App.tsx` drawers, `shared/prop-table.css` (NBA and tennis still use its selected styles), all NBA and tennis code, the API.

## Data / contracts

- **Load-bearing, unchanged:** the deep link is `/nfl/player/:id?market=<market>` (50a), and a market selects the section whose line the lines card lists for it. This step points every NFL row at it.
- **HashRouter and the trailing fragment:** the app's URLs live in the fragment (`#/nfl/player/1`), so a second `#game-log` is parsed by the router as `location.hash`, matches no element, and scrolls nothing; the log scroll is done in code from `?market=`. The suffix is dead and misleading, so it is dropped (step 1). The line-only market link keeps working because it also relies on the param.
- **Repeated market:** the lines card and `NflPlayerProps` both derive ids from `propSectionIds` over the same `week.lines`, so row `i` scrolls to section `i`; `?market=` selects the first of a repeated market (50a's one-primary-line-per-market assumption).
- **New URL params:** board `season, week, position, market, game, all`; game page `position, all`. All optional, validated, defaults omitted. Not stored server-side; no API change.
- **Digest item:** gains `playerId: number` and `marketKey: string`; `market` stays the display label.
- **Session store:** one `sessionStorage` key holding `{ path, key }`; absent or blocked storage degrades to "no restore", never an error.

## Testing

- Test gate is on. Logic that ships with a Vitest file in the same step: `nflPlayerMarketLink` and the digest item (step 1), view-param parse and serialize (step 4), opened-row store (step 6). Components (table, board, game page, lines card, hook wiring) are verified in the running app plus build, per `coding-standards.md`.
- Manual path: start the API and web; open the NFL prop board; click a WR row, land on its section; Back, confirm the row is focused and the filters are unchanged; Tab through the table and press Enter on a name; open a game page, click a digest box and a table row; open a player, click each lines card row; open a kicker via a Field Goals row; reload each deep link; try Cmd/Ctrl-click to open a new tab; try a past week and a player with only one prop.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest` (API untouched).
- Employer interview guide: the file is absent on this machine; skip.

## Notes for the AI

- Reuse the 50a jump-list pattern (`Link replace` plus a direct scroll call, since re-clicking a selected row changes no URL). Do not add a second scroll mechanism.
- Do not touch rank, edge, gap, sample or color code in `NflPropTable` beyond the open control and selection; the PropRow card model stays as is.
- Keep `Link` styling from the existing `a.prop-table__open` rules; add CSS only where an anchor needs a reset.
- Only `replace` for filter and jump changes; `push` only for the row click (a real navigation).
- No `useEffect` fetch loops, no new queries. No em dashes in code, comments or copy. Comments only for non-obvious why (HashRouter, layout-effect ordering).
- Per `one-feature-per-checkout`, this worktree holds only this item's spec.

## Open questions

- Should the board and NFL intelligence digests also link to the player page? Assumed no: they link to the game page today, which is not a drawer, and the user's wording names rows. Say so to change it.
- Step 5 moves board filters into the URL so Back can restore them. If you prefer not to change URLs, the fallback is restoring from `sessionStorage` only; say so before step 4.
- Whole-row click: kept for mouse users to match today's behavior. The name link is the single keyboard and assistive-tech target.

## Outcome

Built and checked live on the worktree dev server (Sam Darnold, Matthew Golden, Trey Smack, the board and game 121) at 390px and desktop, with `npm --prefix web run verify` (1008 tests, build) and API `pytest` (5192 passed, run with the main checkout's venv and CI's dummy `DATABASE_URL`).

Deviations from the draft spec:

- Step 2(c), the scroll-to-top on arrival, was not added: the mid-page landing never reproduced.
- Step 9 was added at the user's request: the prop tabs sit under the usage and game market card and only the selected prop's section shows (the first by default). This supersedes 50a's all-props-expanded layout, so the 50a archive describes the older layout.
- After step 9 the player-page tabs were restyled to the board's underline tab bar, the lines card got a drawn chevron and narrower phone columns, and the now-unused section `selected` prop and `is-selected` styles were removed.
- Known, pre-existing and not fixed: a kicker's `?market=field_goals_made` (a line-only market) scrolls about 700px short of the game log, because the Other markets block loads above it after the scroll fires.
