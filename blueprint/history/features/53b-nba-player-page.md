# Feature: NBA player page (53b)

**From build-plan:** feature 53b (second sub-item of 53, NBA, NHL and tennis player pages)
**Status:** complete (2026-11-02)
**Branch:** this worktree's branch (`claude/nba-player-page-e5edff`), which already holds 53a on `master`

## Goal

A new page, `/nba/player/:playerId`, that shows one player's props for a slate
date as tabs, built the way item 50 and 52b made the NFL page: one tab per
market the player has (modelled markets first, double-double last), each tab
with its stored line and alternates, the reference projection, gap and P(over)
where the market is modelled, and the injury and opponent evidence. The
full-width recent form chart with the Last 5 / Last 10 / vs Opponent switch and
game dates moves to 53b2 (split approved 2026-11-02), because the shared chart
helper it needs is not built yet. It reads the 53a endpoint through `useNbaPlayerProps`. Display only:
no new projection, edge, rank or pick; gray signal colors.

## Design reference

None captured. The target is the existing NFL player page, which shares its
layout and form chart: `web/src/pages/NflPlayerPage.tsx`,
`NflPlayerProps.tsx` (tab strip), `NflPlayerOtherMarketSection.tsx` (a market
card with the switch and chart). No `prototypes/` folder exists. Because no
reference image exists, Step 3 ended with a screenshot review at 1440 and 390 px.

## What reading the code settled

| Question | Answer | Consequence |
|---|---|---|
| Data | `useNbaPlayerProps(playerId, date)` and its types exist (53a), 5 min `staleTime`, 404 not retried. | No new API work. `date` comes from `?date=`; absent means the API default (the board's). |
| Route | NBA's `details` in `routes/sportPages.tsx` holds only `/nba/game/:gameId`. NFL's player route is the pattern. | Add `/nba/player/:playerId`. HashRouter, so links are `/nba/player/:id`. |
| Reusable evidence | `NbaInjuryEvidence` and `NbaOpponentEvidence` take plain props (injury, report, startUtc, team stats, team, market). | Reuse them unchanged. Both rely on the `nba-prop-evidence__section` classes that live in `components/nba/nba-prop-table.css`, which 53c may delete with the drawer. 53b imports that stylesheet as it is; **53c must first move those classes out** (recorded in Notes). |
| Not reusable | `NbaPropEvidencePanel` builds from board `NbaPropCard` rows and will be deleted in 53c. | 53b builds its own market section from `NbaPlayerMarket` and imports nothing from the panel. |
| Tab and URL helpers | `playerSearch`, `propSectionIds`, `selectedPropMarket` in `utils/nflPlayer.ts` are sport-neutral pure functions. | Import them as they are (no NFL file is edited). If you would rather have a neutral copy, say so; copying three small functions is the alternative. |
| Form chart | `FormSwitch`, `GameLogBars` and the window helpers are NFL-specific. The NHL session (53e) will extract a sport-neutral helper but has not started; the user chose (2026-11-02) to ship 53b without the chart. | The chart, switch, dates and the pure helpers for them move to 53b2. `nbaFormSample`, `nbaNotLoadedCount` and `nbaStandardLine` are built here (Step 1) and stay unused until 53b2. |
| Chart reference line | NFL uses the standard rung, else none. | NBA does the same: the `oddsType === 'standard'` rung, else no line, never a guess among alternates. |
| Season for dates | NBA runs Oct to June; stored data starts 2023. | Passed to the shared date and empty-text helpers as NBA's season start and floor year (2023). |
| Data limits | `recent` can be under 10 (a rookie had 6); `opponentGames` can be empty; `value` can be null. | Short Last 10 says "6 of 10 games"; empty opponent history says so; null stats are left out of the chart and counted as "not loaded", never drawn as zero. |
| Entry points | Nothing links to the page until 53c. | Reach it by URL for now (`#/nba/player/322853`). 53c adds the board and game-page links and removes the drawer. |
| Page head | The project rule: compact title plus a period status line, no eyebrow or filler subtitle. | Title is the player; the status line is `POS · TEAM · vs OPP · date`. |

## In scope

- Route `/nba/player/:playerId` and `NbaPlayerPage`.
- Page states: loading, error with retry, player not found (404), invalid id, and a player with no props on the date (links back to the NBA props board for that date).
- Head: name, position, team, opponent and date; the player's injury tag when one exists.
- Tab strip: one tab per market in API order, selected by `?market=` (invalid or absent selects the first); a market section per tab.
- Market section: line and alternates (rungs table); for modelled markets the projection, gap, P(over), P(under), flags and the sample line (games, minutes, model version), all gray with the caveat "Reference projection only. No pick, rank, or signal."; for double-double "Recent results only. This market is not modelled."; the opponent and injury evidence.
- Pure helpers with Vitest tests in `web/src/utils/nbaPlayer.ts`.

## Out of scope

- Rows opening the page, the drawer and panel removal, and moving the shared evidence CSS (53c).
- Any new API field, endpoint or ingest (53a is done). If the page needs a field the endpoint lacks, stop and amend 53a's contract.
- A season summary, usage or full game-log card (the NFL page's other cards).
- The form chart, window switch, game dates and `?form=` (53b2).
- Any NFL file, and the NHL or tennis pages.
- Any sorting, ranking or coloring by value.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.

## Build steps

- [x] **Step 1 - Pure helpers** - `utils/nbaPlayer.ts`: `nbaPlayerPath(playerId, { date, market })` (the link 53c will use, omitting empty params), `nbaPlayerTabs(markets)`, `nbaSelectedMarket(params, markets)`, `nbaFormSample(games)` (drops null values, rounds the average to 2 places), `nbaStandardLine(market)`, `nbaNotLoadedCount(market, window)` and `nbaPlayerStatus(response)` (the status line text). *Done when:* `npm --prefix web run test` passes new `nbaPlayer.test.ts` cases for: the path with and without date and market; an invalid `?market=` falling back to the first tab; a null `value` dropped from the sample and counted as not loaded; the standard line chosen over demon and goblin and `null` when there is no standard rung; the status line with and without an opponent.
- [x] **Step 2 - Route and page shell** - register the route, add `NbaPlayerPage` with the head, injury tag, crumb (to the game page when there is a game, else to the NBA props board), and the loading, error, not-found, invalid-id and no-props states; document title registered through `useRegisterDetailTitle`. *Done when:* in the running app `#/nba/player/322853` shows the head and no tabs yet; `#/nba/player/999999999` shows the not-found message; `#/nba/player/322853?date=2020-01-01` shows the no-props state with a working link back; `#/nba/player/abc` shows not found; no console errors; the production build passes.
- [x] **Step 3 - Tabs and market sections without the chart** - the tab strip and `NbaPlayerMarketSection`: rungs table, gray model facts, caveat, sample line, and the reused injury and opponent evidence. *Done when:* in the running app a guard shows his markets as tabs in API order with `?market=` selecting one, a modelled market shows projection, gap, P(over) and flags matching the board's values for that line, double-double shows no model fields, a reload on `?market=assists` keeps the tab, and a screenshot at 1440 and 390 px shows no horizontal page scroll, no text under 11px and no red, green or other signal color on model values.
- [x] **Step 4 - Verify** - the Verify command and a last screenshot pass. *Done when:* `npm --prefix web run verify && cd api && python -m pytest` passes (dummy `DATABASE_URL`), and screenshots at 1440 and 390 px of a modelled tab, the double-double tab, the no-props state and the not-found state are attached to the review, with the existing NFL tests still passing.

## Files / areas

- New `web/src/utils/nbaPlayer.ts` and `nbaPlayer.test.ts`
- New `web/src/pages/NbaPlayerPage.tsx` and `web/src/pages/nba-player.css`
- New `web/src/components/nba/NbaPlayerPropTabs.tsx` (tab strip) and `NbaPlayerMarketSection.tsx`
- `web/src/routes/sportPages.tsx` (one route added)
- Read-only reuse: `NbaInjuryEvidence`, `NbaOpponentEvidence`, `PageHead`, `LoadingState`, `ErrorState`, `StatChip`, `useRegisterDetailTitle`

## Data / contracts

Load-bearing for 53c.

- Route: `/nba/player/:playerId`, query params `date` (YYYY-MM-DD, optional), `market` (a market key from the response, optional), `form` is reserved for 53b2 (`10` or `opp`, absent means Last 5). `nbaPlayerPath` is the only place a link to this page is built; 53c uses it for board and game-page rows.
- Data: `NbaPlayerProps` from 53a, unchanged.
- No new API shape.

## Testing

- Vitest for the pure helpers (Step 1), per the project gate: logic gets a test, React components do not.
- UI is verified in the running app with screenshots (the local API needs the Windows selector-loop launcher; the dev server proxies `/api`).
- Existing NFL tests must still pass.

## Notes for the AI

- Display only. Gray signal colors; no sorting or coloring by value; no UI text under 11px; no em dashes in code, comments or docs.
- Do not edit `nflFormWindow.ts`, `nflPropCards.ts`, `NflPropDetailSections.tsx`, `NflPlayerOtherMarketSection.tsx` or `nflOtherMarkets.ts`. If Step 4 cannot be built on the NHL session's extraction without an NFL edit, stop and ask.
- Import via the `~/*` alias, TanStack Query only through the hook, `LoadingState` and `ErrorState` for states, HashRouter links.
- For 53c: before deleting `NbaPropEvidencePanel` and `nba-prop-table.css`, move the `nba-prop-evidence__section` classes that `NbaInjuryEvidence` and `NbaOpponentEvidence` use into a stylesheet those components import.
- The local API: `C:\dev\SportAppV2\api\.venv`, `DATABASE_URL` from the main checkout's `api/app/.env`, selector-loop launcher; `npm.cmd` on Windows; this worktree's `web/node_modules` is a junction to the main checkout's.
