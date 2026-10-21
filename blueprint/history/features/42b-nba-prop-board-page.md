# Feature: NBA prop board page

**From build-plan:** 42b (parent 42, NBA prop board)
**Status:** complete (approved 2026-10-21; verified locally, deployment pending)
**Depends on:** completed 42a, NBA prop board API
**Planned branch:** `feature/nba-prop-board-page`

## Goal

Make `/nba/board` NBA's Props view: one Eastern game date and one market,
with dense player rows across games and the NBA game page's evidence drawer.
Reuse the existing NBA grouping and display rules so a board row and its
game-page counterpart show identical lines, projections, gaps and probabilities.
Everything remains gray, unranked reference information.

## Design reference

Extend the existing Lineform interface, using these checked-in references:

- [NFL board, desktop](../reference/38f/final-nfl-props-1440.png) and
  [phone](../reference/38f/final-nfl-props-390.png): shared head, market pills,
  dense rows and responsive structure. Do not copy NFL ranking or signal colors.
- [NBA game, desktop](../reference/38f/final-nba-game-1440.png) and
  [phone](../reference/38f/final-nba-game-390.png): NBA row content and gray styling.
- [NBA evidence drawer, desktop](../reference/38f/final-nba-game-drawer-1440.png)
  and [phone](../reference/38f/final-nba-game-drawer-390.png).

The live source components are the implementation authority: `PageHead`,
`NbaPropTable`, `NbaLineOnlyTable` and `NbaPropEvidencePanel`. There is no
`prototypes/` directory. Keep the existing global theme, fonts and tokens.

## In scope

- A typed board fetch and TanStack Query hook for `GET /nba/props?date=`.
- NBA Props registration in `SPORTS` and `SPORT_PAGES`, including the existing
  shell's desktop tabs, phone navigation and document-title derivation.
- Shared page head with resolved date and previous/next game-date navigation.
- Market pills in existing NBA market order, with grouped row counts. Default
  to Points. Include the ten known markets, including empty ones; show an
  explicit empty state for the selected market. Unknown returned markets may
  follow the known ones, using the existing fallback labels.
- One row per game/player/market, retaining every alternate rung through the
  existing main-rung and alternate display. Modelled rows show player, game
  link, tip/status, line, projection, gap, P(over), last-5 mini bars and flags.
- Line-only rows use the same game/tip context and existing plain line-only
  content, without projection, gap or probability columns.
- Reuse the evidence panel for both row kinds in the existing responsive
  drawer. Add game context/link outside the panel if needed.
- Shared loading/error/retry states, no-games, games-with-no-lines and
  selected-market-empty states; keyboard access and responsive verification.

## Out of scope

- Injuries (42c) and opponent/team statistics (42d), including placeholder tags.
- Signal colors, picks, ranks, edge columns, or sorting/filtering by gap or
  probability. No Top plays strip, Show all threshold, or NFL rating logic.
- New search, position/team/game filters, command search expansion, or a new
  board design system. The existing shell remains available as it is.
- Backend, database, ingest, projections, fits, model versions, grading,
  probability eligibility, API pagination or report caching changes.
- Deployment, merge, push or historical holdout evaluation.

## Build loop

1. Explain one step and its checks before editing.
2. Implement only that step, with tests for its pure logic.
3. Show the diff and evidence, then wait for review before the next step.
4. Checkpoints are optional and require approval and passing checks.
   `/complete` handles the final feature commit and archive.

## Build steps

- [x] **Step 1 - Typed board data and pure row assembly.** Add the response
  interfaces, `fetchNbaPropBoard(date)` and `useNbaPropBoard(date)`. Add a pure
  `nbaPropBoard` utility that calls `nbaPropGroups` and `nbaLineOnlyGroups`
  separately for each game, attaches game context and combines rows by market.
  Order by tip time ascending, then player name, then game/player ids as
  deterministic ties; null or invalid tips go last. Memoize assembly at the
  page boundary when it is connected in step 3.
  *Done when:* unit tests prove the row payloads equal existing grouping
  helpers' output, alternates stay together, the same player in two games
  stays separate, ordering is independent of gap/probability, missing tips
  sort last, market counts count grouped rows, and empty arrays are safe.
  Typecheck/build passes with the new transport and hook.

- [x] **Step 2 - Reusable NBA rows with optional game context.** Extend the
  existing NBA tables with optional board context, or extract their row cells
  for reuse in a small board table. Avoid a second implementation of line,
  projection, flag or mini-bar formatting. Use game/player identity for row
  keys and selection when used on the board. Game links open
  `/nba/game/:gameId` without also opening the evidence drawer. Keep existing
  game-page callers compatible.
  *Done when:* modelled and line-only board tables can show game links and CT
  tip/status labels; player buttons remain keyboard operable; game-page tables
  retain their current columns and drawer selection. Confirm both existing
  game-page row kinds in the running app and capture desktop/phone evidence.
  Any new pure context/status formatting has fixed-time tests.

- [x] **Step 3 - Board page, date/market controls and navigation.** Build
  `NbaPropBoardPage`, register it in both sport registries, connect the board
  hook and row assembler, add the shared head and market pills, and reuse
  `NbaPropEvidencePanel` in a drawer. Store the requested date and selected
  market in `?date=&market=` for reload/back/forward behavior. Parse date with
  `parseSlateDate`; omit invalid dates from the API request. An absent or
  invalid market selects Points. Previous/next links retain the selected
  market and use API-provided adjacent dates; missing neighbors are disabled.
  Close/reset selection when date or market changes and resolve selected
  evidence from current query data so a refetch cannot leave stale values.
  *Done when:* `/nba/board` opens the API-resolved date; the head matches that
  response; tabs and phone nav include NBA Props; pills show one market at a
  time; every row opens the correct evidence panel with the response model
  version; date/market navigation, reload and browser history work. Loading,
  retryable error, empty-date, no-lines and empty-market states are distinct.
  Update registry/title tests and test any new URL-selection logic.

- [x] **Step 4 - Browser proof, parity and final verification.** Check the
  finished page at 1440, 1000 and 390 pixels, including both drawer kinds,
  keyboard selection/close/focus return, navigation and empty/error states.
  Compare a board row and every rung in its drawer to the same game's page
  for an eligible assists player, a non-probability market, an ineligible
  projection and a line-only market. Use controlled fixtures for cases the
  current date does not contain; label fixture evidence separately.
  Exercise the known large-date payload and record line count, grouped row
  count, fetch/assembly/render observations and pill/drawer responsiveness.
  *Done when:* all rows remain reachable, only the selected market's table
  mounts, controls and drawer respond without repeated full-data assembly,
  page width stays within the viewport (table-local overflow is acceptable),
  no new console errors appear, all parity cases pass, and full Verify passes.
  Record any actual performance failure before proposing a contract change.

## Files / areas

- `web/src/types/nba.ts`, `web/src/api/nba.ts`, `web/src/hooks/useNba.ts`:
  board contract, fetch and hook.
- `web/src/utils/nbaPropBoard.ts` and adjacent `.test.ts` (new): pure board
  assembly and selection helpers if needed.
- `web/src/pages/NbaPropBoardPage.tsx` (new), scoped board CSS as needed.
- `web/src/components/nba/NbaPropTable.tsx` and its CSS, with a small shared
  row extraction or board component only where needed.
- `web/src/components/nba/NbaPropEvidencePanel.tsx`: reuse its public props;
  change only if a minimal compatible extension is required.
- `web/src/utils/sportNav.ts`, `web/src/routes/sportPages.tsx` and relevant
  existing registry tests: NBA Props route, navigation and titles.
- `blueprint/reference/42b/`: browser evidence during implementation/check.
- Local ignored `docs/SportApp-Employer-Interview-Guide.md`, if present:
  update when the board is implemented and verified; describe deployment
  separately. Never stage this file.

## Data / contracts

**Load-bearing: 42a's existing camelCase response, unchanged.**

```text
NbaPropBoardResponse
  date: string
  previousDate: string | null
  nextDate: string | null
  modelVersion: string
  games: NbaPropBoardGame[]

NbaPropBoardGame
  gameId: number
  awayTeam: string
  homeTeam: string
  startUtc: string | null
  status: string
  lines: NbaPropLine[]
  lineOnlyLines: NbaLineOnlyLine[]
```

- API date is an Eastern calendar date; tip labels explicitly use CT, matching
  the NBA slate. Do not derive the requested date by converting CT tip labels.
- Hook key: `['nba', 'prop-board', date]`; deliberate five-minute `staleTime`.
  Use shared axios client, one board request, no per-game prop requests or
  duplicate slate request. The API supplies all navigation/game context.
- Board row identity includes kind, game id, market and player id. Group
  within each game before flattening, never across games.
- `nbaPropGroups` and `nbaLineOnlyGroups` remain authoritative for main rung,
  alternates, recent bars, nulls, flags and formatting. Null means missing,
  never zero. Preserve actual zero stats/probabilities.
- P(over) is displayed only where the existing response serves it (currently
  eligible assists lines). Never fit or derive a new probability on the client.
- Retain started, completed, postponed and canceled games from the response;
  show their status. Label elapsed scheduled games as started, never live,
  following existing NBA semantics. Missing tip is explicitly unknown.
- Grouped row counts differ from raw line counts because alternates share a
  row. Label counts accordingly. No silent truncation of games, rows or rungs.
- 42c/42d may extend the response with nullable context later; no speculative
  fields or second board endpoint here.

## Testing

The test gate is on. Unit-test pure derivation, ordering, identity, URL
validation/fallback and any new status/time formatting. Use fixed times, include
zero/null values and alternate rungs. Update existing sport-navigation tests
that currently expect NBA to have Slate / Model only.

Observe components and route integration in the browser, per project standards;
do not add component-render or browser test infrastructure. Check accessible
pill names/pressed state, player buttons, game links, drawer focus/close, and
date navigation. Use local read-only API requests and clearly labeled fixtures
for missing states; no paid provider calls or database writes are needed.

Final gate from the repo root, with the API venv on PATH:
`npm --prefix web run verify && cd api && python -m pytest`.
In this shell the API half may use `api/.venv/Scripts/python.exe -m pytest`
from `api/` with the corresponding relative path `.venv/Scripts/python.exe`.

## Notes for the AI

- Step 4 approved; user chose Continue to completion (2026-10-21).
  Browser proof found and repaired board-drawer focus return: board rows
  expose their stable key, the market component captures the matching player
  button, and focus returns on close and after the drawer's own restoration.
  Both immediate and settled Escape closes pass; mouse-row opens and Close
  button also restore focus. No pure derivation changed in this step, so
  browser evidence covers the DOM behavior under the project's test policy.
  Four live board/game comparisons matched every shared row cell, alternate
  rung and full evidence body. Both drawer kinds and responsive rows passed
  at 1440, 1000 and 390 pixels. All ten markets retain every ordered row and
  reach their last row. Full Verify passed: 659 web tests, typecheck/build,
  3,470 API tests. Existing bundle-size and Starlette warnings remain.
  Evidence, measurements and limitations: `blueprint/reference/42b/step4-check.md`.
  Updated the ignored local interview guide with this locally verified board;
  final review and deployment remain pending. No commit or remote action.
  Ledger checked: no open/fixed P0/P1; unrelated F-09/F-12 remain unverified.
- Step 3 approved; user chose Continue without a checkpoint (2026-10-21). Added the board page,
  URL date/market controls, scoped current-data drawer selection, both sport
  registry entries, scoped CSS and URL/navigation tests. Web Verify passed:
  659 tests, typecheck and production build. API venv pytest: 3,470 passed.
  Browser checks passed for live default/date/market navigation, both drawer
  kinds, phone menu and reload/history, plus controlled loading/error/retry,
  all three empty states, invalid URL values, disabled adjacent date and
  fresh selected evidence after refetch. Evidence and fixture boundaries:
  `blueprint/reference/42b/step3-check.md`. No checkpoint commit.
- Step 2 approved; user chose Continue without a checkpoint (2026-10-21). Shared NBA row
  rendering accepts optional game context; `NbaBoardTable` reuses it with
  game/player keys and game/tip columns. CT/status tests bring focused board
  tests to 11. Web Verify passed (655 tests, typecheck, production build);
  API venv pytest passed (3,470). Browser checks passed for both existing
  game-page drawer kinds and controlled board-table harness at 1440, 1000
  and 390 pixels. See `blueprint/reference/42b/step2-check.md` for evidence
  and fixture boundaries. No checkpoint commit.
- Step 1 approved; user chose Continue without a checkpoint (2026-10-21).
  Implemented on `feature/nba-prop-board-page`. Eight new pure-helper tests pass. Full web Verify passed:
  652 tests, typecheck and production build. API tests passed: 3,470.
  The combined command selected system Python without pytest, so the API
  half was rerun successfully from `api/` using
  `.venv/Scripts/python.exe -m pytest`. Existing bundle-size and Starlette
  deprecation warnings remain. No checkpoint commit or page UI yet.
- Spec critique tightened multi-game player identity, raw-line versus grouped
  counts, stale drawer selection, Eastern-date versus CT-tip semantics,
  status retention and large-payload verification. No additional feature split
  is needed: four small steps form one frontend delivery.
- 42a's archive records 7,986 modelled and 111 line-only lines on 2026-10-21,
  a 4,877,159-byte local response in 1.91 seconds. This is evidence for a
  realistic browser check, not proof of Render memory or hosted performance.
  Keep one selected table mounted and memoize grouping; do not introduce
  speculative pagination, virtualization or backend caching.
- The generated overview still describes 42a as not started. The checked
  build plan, completed 42a archive and current code establish the dependency
  is complete. Do not hand-edit the overview as part of this spec.
- Stay frontend-only. Preserve gray reference rules, game-page formatting,
  versions, API filters and all validation/holdout boundaries.
- This skill writes the spec only. Implementation begins after spec review.

## Completion review

- All four steps approved and verified on `feature/nba-prop-board-page`.
- Final safety pass: changed files belong to 42b; no workflow adapters or
  backend code changed. Invariants review is clean for gray display, versions,
  validation boundaries, secrets and request-path behavior.
- Verify passed in this session using the documented Windows halves:
  `npm.cmd --prefix web run verify` (659 tests, typecheck, production build)
  and, from `api/`, `.venv/Scripts/python.exe -m pytest` (3,470 tests).
  Existing bundle-size and Starlette deprecation warnings remain.
- Behavioral proof is recorded in `blueprint/reference/42b/step2-check.md`,
  `step3-check.md` and `step4-check.md`, with screenshots. Four live parity
  cases, all ten market row sets, three widths, drawer focus, history and
  controlled error/empty/refetch cases pass.
- Manual try: `http://127.0.0.1:3001/#/nba/board?date=2026-10-21&market=assists`;
  open AJ Green, inspect alternates, Escape back to the player, switch to
  Double-double and navigate dates.
- Local large-date payload: 4,877,159 bytes, 8,097 raw lines and 1,383 grouped
  rows. Pure assembly measured 3.3-4.3 ms; full-data assembly did not repeat
  during market/drawer interactions. Hosted latency and Render memory remain
  unverified; no production claim follows from these development measurements.
- No open/fixed P0/P1 findings. Unrelated unverified F-09 (P3) and F-12 (P2)
  remain in the ledger. No findings were resolved by this feature.
- Local ignored employer interview guide updated, with implementation/local
  verification separated from deployment. Never stage that file.
- 42c and 42d remain pending, so parent 42 stays unchecked. Merge and push
  require separate approval; neither is included in this completion commit.
