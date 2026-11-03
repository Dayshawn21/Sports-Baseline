# Feature: NHL rows open the player page (53f)

**From build-plan:** feature 53f (sixth sub-item of 53, NBA, NHL and tennis player pages)
**Status:** complete (2026-11-03)
**Branch:** `feature/nhl-rows-open-page`; `claude/nhl-player-page-dc0f41` is fully merged to master (53d, 53e) and level with it

## Goal

On the NHL game page's Player Props tab, each prop row becomes a link to that
player's page (`/nhl/player/:id`, built in 53e), opened on the market the row
shows and on the game's date. The game page's inline panel (`NhlLineOnlyProps`:
one table row per offering, with its own count header) is removed and replaced
by a leaner list, one row per player per market, whose name opens the page where
the lines, form chart and injury and goalie evidence now live. Display only: no
new projection, edge, rank or pick; gray signal colors; rows keep their current
order (market order, then player name).

## Design reference

None captured. The target is the NFL game page's other-markets list
(`web/src/components/nfl/NflLineOnlyProps.tsx`), where the player name is a link
to the player page, and the NHL panel it replaces (`NhlLineOnlyProps.tsx` and its
`nhl-prop-*` styles in `pages/nhl-game.css`). No `prototypes/` folder exists.
Because no reference image exists, Step 2 ends with screenshots at 1440 and 390 px
beside the current panel.

## What reading the code settled

| Question | Answer | Consequence |
|---|---|---|
| What is "the inline panel"? | `NhlLineOnlyProps` is the only NHL prop UI on the game page: a count header and, per market, a table with one row per offering (standard, goblin, demon). NHL has no expandable drawer like NBA's. | It is replaced, not just given links. A row per offering would repeat the same player and the same link up to three times, so rows collapse to one per player per market. |
| Where is the detail now? | The player page (53e) already shows every rung with its type, line and update time, plus the chart and evidence. | The game page list shows the player, team and position, the standard line, the alternate lines in one gray line, and the latest update. The rest is one click away. |
| Link shape | `nhlPlayerPath(playerId, { date, market })` from 53e is the one place a link to the page is built. `NhlGameDetail.gameDate` is the game's slate date. | Rows link with `date = game.gameDate` and `market = the row's market`, so the page opens on that market and that date, not on whatever "today" resolves to. |
| Data | `useNhlLineOnlyProps(gameId)` returns `NhlLineOnlyLine[]`, each with `playerId`, `playerName`, `team`, `position`, `market`, `oddsType`, `line`, `fetchedAt`. | No API change. The same hook feeds the new list. |
| Reused pure code | `nhlMarketLabel`, `nhlPropLineLabel` (minutes and signed plus/minus), `nhlOddsTypeCounts` and `NHL_LINE_ONLY_MARKETS` order in `utils/nhlLineOnly.ts`; the player page imports the first two. | Keep them. `nhlLineOnlyGroups` (one row per offering) is replaced by a per-player grouping; its tests are rewritten, not dropped. |
| Back path | The 53e page's crumb links to the game page when the player has a game, and the game page opens on its Player Props tab. | No new back-navigation code. A check in Step 2 confirms the round trip. |
| Loading and error | `NhlLineOnlyProps` owns the loading, error-with-retry and empty states. | The replacement keeps all three unchanged. |
| Other users | `NhlLineOnlyProps` is imported only by `NhlGamePage`. `fetchNhlLineOnlyProps`, `useNhlLineOnlyProps` and the types stay. | Safe to delete the component file. Nothing else is removed from the API layer. |

## In scope

- A pure per-player grouping helper in `utils/nhlLineOnly.ts` with Vitest tests.
- A new `NhlGameProps` list on the game page's Player Props tab, replacing `NhlLineOnlyProps`: market groups in the server enum order, one row per player per market, the player name a link to the player page, the standard line shown first and alternates after it, the latest update time.
- Deleting `NhlLineOnlyProps.tsx` and the `nhl-prop-*` and `nhl-props-*` styles that nothing uses afterward.
- The `NhlGamePage` change that passes `gameDate`.

## Out of scope

- Any API field, endpoint or ingest.
- The player page itself (53e is merged) and any NFL, NBA or tennis file.
- A slate-level NHL props board or links from the slate page (not planned).
- Sorting, ranking or coloring rows by line, gap or any value.
- Showing the form chart, evidence or per-rung update times on the game page; they stay on the player page.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.

## Build steps

- [x] **Step 1 - Per-player rows helper** - in `utils/nhlLineOnly.ts` replace `nhlLineOnlyGroups` with `nhlPropListGroups(lines)`: market groups in `NHL_LINE_ONLY_MARKETS` order, each holding one row per player (keyed by `playerId`, never by name) with the player's name, team and position, `rungs` sorted by line then standard, goblin, demon (each with its `nhlPropLineLabel` text and odds type label), `standard` (the standard rung's label or null), and `fetchedAt` as the latest of the player's rungs; rows are ordered by name then id. Move the old grouping's cases to the new helper. *Done when:* `npm --prefix web run test` passes `nhlLineOnly.test.ts` cases for: three offerings of one player collapsing to one row with rungs in line order; two players with the same name staying separate; market order following the server enum; a plus/minus rung reading `+0.5` and a time-on-ice rung `20.5 min`; no standard rung giving a null `standard` and the alternates still listed; the latest `fetchedAt` chosen across offerings; and the unchanged `nhlOddsTypeCounts`, `nhlMarketLabel` and `nhlPropLineLabel` cases still passing.
- [x] **Step 2 - Linked list replaces the panel** - add `NhlGameProps` (`components/nhl/NhlGameProps.tsx`) using `useNhlLineOnlyProps` and the new helper, with the player name a `Link` to `nhlPlayerPath(playerId, { date: gameDate, market })`; swap it into `NhlGamePage` (passing `gameId` and `gameDate`); delete `NhlLineOnlyProps.tsx`; remove the CSS in `nhl-game.css` that nothing references. *Done when:* in the running app the Player Props tab of a game with lines shows market groups with one row per player, the heading and count header unchanged, the rows linked and keyboard focusable, a click opening `#/nhl/player/<id>?date=<gameDate>&market=<market>` on that tab, and the player page's crumb returning to the game page's Player Props tab; a game with no lines shows the existing empty message; a screenshot at 1440 and 390 px shows no horizontal page scroll, no text under 11px and no signal color on any value; `npm.cmd run build` passes and `rg NhlLineOnlyProps web/src` finds only the API type and hook names.
- [x] **Step 3 - Verify** - the Verify command and a last click-through. *Done when:* `npm --prefix web run verify && cd api && python -m pytest` passes (dummy `DATABASE_URL`), and a recorded click-through of a skater row, a goalie row and a plus/minus row lands on the right market tab on the right date, with the existing NFL, NBA and 53e tests still passing.

## Files / areas

- `web/src/utils/nhlLineOnly.ts` and `nhlLineOnly.test.ts`
- New `web/src/components/nhl/NhlGameProps.tsx`; deleted `NhlLineOnlyProps.tsx`
- `web/src/pages/NhlGamePage.tsx` (one component swap) and `web/src/pages/nhl-game.css` (unused rules removed, a few added)
- Read-only reuse: `nhlPlayerPath` in `utils/nhlPlayer.ts`, `useNhlLineOnlyProps`, `LoadingState`, `ErrorState`

## Data / contracts

- No new API shape. The list reads `NhlLineOnlyProps` (`NhlLineOnlyLine[]`) as today.
- Link contract: rows link only through `nhlPlayerPath` (53e), always with the game's `gameDate` and the row's market key.
- Row identity is `playerId`, not the name.

## Testing

- Vitest for the grouping helper (Step 1), per the project gate: logic gets a test, React components do not.
- UI is verified in the running app with screenshots and a click-through. The local API needs the Windows selector-loop launcher; the dev server proxies `/api`.
- Existing NFL, NBA and NHL tests must still pass.

## Notes for the AI

- Display only. Gray signal colors; no sorting or coloring by value; no UI text under 11px; no em dashes in code, comments or docs.
- Do not edit any NFL, NBA or tennis file, the NHL player page files from 53e, or `NhlGameContext.tsx`.
- Import via the `~/*` alias, TanStack Query only through the hook, HashRouter links, `LoadingState` and `ErrorState` for states.
- Keep the page-head rule: no new eyebrow or filler subtitle on the game page.
- Open decision for the reviewer: the cheaper alternative is to keep `NhlLineOnlyProps` and only turn each player name into a link (one row per offering, three rows for a three-rung player). This spec chooses the leaner one-row-per-player list because the build plan says the inline panel is removed and because the full per-rung detail now lives on the player page.
- The local API: the main checkout's `api/.venv`, `DATABASE_URL` from the main checkout's `api/app/.env` (copy it in temporarily and remove it after), the selector-loop launcher, `npm.cmd` on Windows; this worktree's `web/node_modules` is a junction to the main checkout's.
