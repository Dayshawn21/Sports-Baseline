# Fix: Shared player-page helpers, and the NHL board crumb

**Type:** Fix
**Fixes:** F-62 (web part), F-67
**Branch:** `fix/web-player-pages` (cut from `fix/web-game-status`, so merge
the three earlier web branches first)

**Completed:** 2026-11-16. Squash-merged to master at the user's request.

### The problem

- **F-62.** Sport-neutral player-page helpers live in `utils/nflPlayer.ts`, so
  NBA, NHL and tennis code imports from an NFL module: `FROM_BOARD`,
  `arrivedFromBoard`, `playerSearch`, `propSectionIds`. And
  `nbaPlayerTabs`/`nhlPlayerTabs` and `nbaSelectedMarket`/`nhlSelectedMarket`
  are identical copies typed as `string`, which forces the
  `as NhlLineOnlyMarket[]` and `as NhlLineOnlyMarket` casts in
  `components/nhl/NhlPlayerPropTabs.tsx:12,15`.
- **F-67.** The NBA board marks its player links as a board arrival
  (`FROM_BOARD` state) and `NbaPlayerPage` then shows a `← NBA props` crumb
  that goes back to the board on its own date and market. The NHL board link
  (`components/nhl/NhlPropBoardMarket.tsx`) passes no state and
  `NhlPlayerPage`'s crumb always points at the game (or the slate).

### The fix

- `utils/playerPage.ts` (already home to the shared tag and footer helpers) takes `FROM_BOARD`, `arrivedFromBoard`,
  `playerSearch`, `propSectionIds`, plus one generic
  `playerTabs<M extends string>(markets: { market: M }[]): M[]` and
  `selectedMarket<M extends string>(params, markets: readonly M[]): M | null`.
  Their tests move with them. Every importer switches; the NBA/NHL copies and
  the NHL casts go.
- The NHL board player link passes `FROM_BOARD`, and `NhlPlayerPage`'s crumb
  copies the NBA one.

**Visible change (F-67, approved 2026-11-15):** opening an NHL player from the NHL
props board shows `← NHL props` (going back to the board on its date and
market) instead of `← AWAY @ HOME`. Opening the player from anywhere else is
unchanged.

Stays inside `web/`.

### Build steps

- [x] **Step 1 - `playerPage.ts`.** Move the four helpers and add the two
  generic ones, with their tests (the file already existed with
  `injuryTone`, `latestTime` and `payoutTierNote`; they stay); switch every importer; delete the NBA/NHL
  copies and casts. Done when: no non-NFL file imports from
  `utils/nflPlayer`, the casts are gone, and Verify passes.
- [x] **Step 2 - NHL board crumb.** Board link state plus the NBA-style crumb.
  Done when: Verify passes and, in the app, an NHL player opened from the
  props board shows `← NHL props` that returns to the board, while one opened
  from a game page still shows the game crumb.

### Verify

- `npm --prefix web run verify` after each step.
- In the running app: NBA and NHL player pages switch market tabs as before;
  the NBA board crumb still works; the NHL one is new.
