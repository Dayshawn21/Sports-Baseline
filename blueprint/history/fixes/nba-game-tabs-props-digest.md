# Props gap strips and NBA game tabs

**Type:** Fix

**Completed:** 2026-10-23

**Branch:** `fix/nba-game-tabs-props-digest`

## The problem

The owner asked for three display changes:

- **NBA game tabs.** The NBA game page stacks market, movement, injuries, team
  stats and props on one long page. NFL already splits these into Matchup and
  Player Props tabs.
- **Top cards on Props pages.** The gray "Largest gaps" strip (38b/38c2) is
  shown only on the Slate. The owner wants it at the top of the Props board
  and of each game page's Player Props tab, for NFL and NBA.
- **Dead card links.** On the game-page tabs, each strip card links to the
  game page the viewer is already on, so clicking it does nothing useful.

**Rule change (owner-approved 2026-10-23):** 38c2 and 42b allowed NBA gap
ranking only in the Slate strip; the NBA board and game page were never
sorted by gap. This fix allows the same gray, "reference, not picks" strip on
the NBA board and NBA game Player Props tab. The prop rows below it stay
unranked and unsorted (tip time, then player), and no signal color is added.

## The fix

- **NBA tabs:** `NbaGamePage` uses the same antd `Tabs` (`nfl-game-tabs`,
  default `props`) as `NflGamePage`. Matchup holds market, line movement,
  injuries and team stats; Player Props holds modelled and line-only props.
- **NFL strips:**
  - Board: `slateDigest(buildNflPropBoard(week games, 'all', now))`, exactly
    the Slate's digest, ignoring the board's filters.
  - Game tab: the same call on that game alone, labelled "this game".
- **NBA strips:**
  - Board: reuses the Slate's `useNbaSlateGaps(date)` request, so the two
    strips always agree.
  - Game tab: new pure `nbaGameGaps(game, lines, now, limit = 4)` in
    `web/src/utils/nbaSlate.ts`. It mirrors `rank_slate_gaps` for one game:
    standard lines with a projection and line > 0, scheduled and not yet
    tipped, ranked by |gap| / line, one per player, with the server's
    tie-break order. It reads the props query the tab already loads.
- **`NflSlateDigest` / `NbaSlateDigest`** take an optional `scope` label
  (default unchanged, "this week" / "today").
- **Game-tab cards open the drawer:** the digest components take an optional
  `onOpen`. When set, a card is a button that opens that line's evidence
  drawer instead of a link. The game-tab strip moves inside `NflGameProps` /
  `NbaProps`, which own the drawer state. Board and Slate cards keep linking
  to the game page.

**Must not break:**
- Slate strips (order, label, links) unchanged.
- Board and game-page row order, ranks, edges, P(over) and colors unchanged.
- Board/game parity (33a, 42a) and the `.nfl-slate` gray-signal scope.
- No API, schema, model or version change; no new request on the NBA game page.
- 11px floor; phone layout.

## Build steps

- [x] **1. NBA game tabs.** Done when `/nba/game/:id` shows Matchup / Player
  Props tabs, opening on Player Props, with every existing block present.
- [x] **2. Strips on NFL and NBA Props boards and game tabs.** `scope` labels,
  `nbaGameGaps` with tests. Done when all four pages show the strip and Verify
  (web half) passes. Recorded: 57 test files, 817 tests, build passed.
- [x] **3. Game-tab cards open the evidence drawer.** Add `onOpen` to both
  digest components; move the game-tab strip into `NflGameProps` and
  `NbaProps` and open the matching line (NFL: `lineId`; NBA: market and
  `playerId`). Done when clicking a game-tab card opens that player's drawer
  for that market, focus returns to the card on close, and board/Slate cards
  still navigate.
- [x] **4. Browser check and docs.** Done when the four pages are checked at
  1440 and 390 px, the full Verify passes, and `SPORT_STATUS` /
  How it works text is checked for any statement that NBA never ranks gaps.

## Verify

- `/nfl/board` and `/nba/board`: strip above the market pills; cards match
  the Slate strip for the same week/date and open the game page.
- `/nfl/game/:id` and `/nba/game/:id` Player Props: "Largest gaps this game"
  shows up to 4 cards; clicking one opens that player's drawer; strip is
  absent once the game has tipped.
- `/nba/game/:id`: Matchup tab holds market, movement, injuries, team stats.
- Slates unchanged; no green or red added to any strip.
- Verify: `npm --prefix web run verify && cd api && python -m pytest`.

## Completion evidence

- **Verify:** `npm --prefix web run verify` (57 files, 817 tests, typecheck,
  build) and `api/.venv/Scripts/python.exe -m pytest` (3,945 passed).
- **Browser, 1440 px, local dev against the shared database:**
  - NBA NY @ BOS (21300): four button cards; Neemias Queta's card opened his
    Pts + reb + ast drawer; Escape returned focus to the card.
  - NBA CHI @ MIL (21299): already tipped, no strip.
  - NFL PIT @ NO (95) with the QB filter on: Rico Dowdle's card opened his
    Rushing yards drawer; focus returned. Tyler Shough's +10.3% matches his
    board row.
  - `/nfl/board` and `/nba/board`: four link cards to game pages.
- **Browser, 390 px:** four cards on all four pages, strip scrolls sideways,
  no horizontal page scroll.
- **Found in step 3:** the step-2 NFL game strip built its board from one game,
  so gap share used a one-game reference line. Fixed by ranking the week-wide
  board narrowed to the game.
- **Not verified:** hosted deployment.
