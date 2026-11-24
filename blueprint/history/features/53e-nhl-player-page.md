# Feature: NHL player page (53e)

**From build-plan:** feature 53e (fifth sub-item of 53, NBA, NHL and tennis player pages)
**Status:** complete (2026-11-03)
**Branch:** this worktree's branch (`claude/nhl-player-page-dc0f41`), which holds master through 53d, 53d2, 53b2 and 53h

## Goal

A new page, `/nhl/player/:playerId`, that shows one NHL player's props for a
slate date as tabs, built the way 53b and 53b2 made the NBA page: one tab per
market the player has, each tab with the full-width recent form chart (Last 5 /
Last 10 / vs Opponent, game dates under the bars, the standard line drawn
across), the stored lines, and the injury and starting-goalie evidence. It
reads the 53d endpoint through `useNhlPlayerProps` and the chart comes from the
shared helpers 53d2 made sport-neutral. All twelve NHL markets are line-only, so
there is no projection, gap or probability anywhere on the page: it states the
market is not modelled. Display only: no new projection, edge, rank or pick;
gray signal colors.

## Design reference

None captured. The target is the NBA player page that is already on master:
`web/src/pages/NbaPlayerPage.tsx`, `components/nba/NbaPlayerPropTabs.tsx`,
`NbaPlayerMarketSection.tsx` and `NbaPlayerFormSection.tsx`, which share the
NFL page's layout classes. No `prototypes/` folder exists. Because no reference
image exists, Steps 3, 4 and 5 end with screenshots at 1440 and 390 px.

## What reading the code settled

| Question | Answer | Consequence |
|---|---|---|
| Data | `useNhlPlayerProps(playerId, date)`, `validNhlPlayerId` and the `NhlPlayerProps` types exist (53d); 5 min `staleTime`, 404 not retried. | No API work. `date` comes from `?date=`; absent means the API default. |
| Route | NHL's `details` in `routes/sportPages.tsx` holds only `/nhl/game/:gameId`. | Add `/nhl/player/:playerId`. HashRouter. |
| Chart | `GameLogBars({ row, sample, seasonStartMonth })`, `FormSwitch`, `formSample`, `formTitle`, `formShortNote`, `formEmptyText(row, window, sinceYear)`, `formHistoryDate(date, now, seasonStartMonth)` are on master (53d2). `formBars` now draws negative values. | NHL passes `seasonStartMonth = 7` (games run October to June) and `sinceYear = 2023` (`NHL_FIRST_HISTORY_SEASON`). No NFL file is edited. |
| Plus/minus | Values can be negative; the lines can be below zero. | Drawn by the 53d2 signed bars. A Step 5 check shows a negative bar under the zero line at 11px or larger. |
| Time on ice | Values and lines are minutes (53d converts seconds). | Line labels use `nhlPropLineLabel` ("18.5 min"); bar labels use `formBarLabel`, which keeps one decimal. |
| Goalies | `recent` holds started games only and can be short or old (one goalie's last start was in April 2024). | Dates show under every bar, a short Last 10 says "N of 10 games", and a goalie market says "Started games only". |
| Reference line | NFL and NBA draw the standard rung or none. | NHL does the same. A market with only alternate rungs draws bars and no line, never a guess. |
| Evidence data | `injury` holds the player's own ESPN entry plus `fetchedAt`, `sourceTimestamp`, `freshness`; `goalies` holds both teams' expected or confirmed starter, or null when no context is stored. | A new `NhlPlayerEvidence` shows the player's injury entry and both goalies. A missing entry is not "healthy" (the game page's own caveat). |
| Evidence helpers | `nhlContextSource`, `nhlGoalieLabel`, `nhlInjuryDetails`, `nhlContextTime` in `utils/nhlContext.ts` are pure and take plain reports. The `nhl-game-context*` classes in `nhl-game.css` hang off a `.nhl-game-context` wrapper. | The new component reuses the helpers and the classes under that wrapper. `NhlGameContext.tsx` is not edited. `NhlPlayerInjury` has no `source` field, so a pure helper builds the report object the freshness function takes. |
| Not reusable | `NhlLineOnlyProps` (the game page's inline panel) is deleted in 53f. | 53e imports nothing from it. `nhl-game.css` stays (the game page needs it). |
| Shared URL helpers | `playerSearch` and `propSectionIds` in `utils/nflPlayer.ts` are sport-neutral pure functions; the NBA page imports them. | Import them as they are. |
| NBA helpers | `nbaPlayer.ts` holds NBA-typed copies of the path, tab, sample and window helpers. | NHL gets NHL-typed copies in `nhlPlayer.ts`. Folding the NBA and NHL copies into one set is a follow-up, not part of this item, because it edits NBA files that another session owns. |
| Entry points | Nothing links to the page until 53f. | Reach it by URL for now (`#/nhl/player/<id>`). 53f adds the game-page row links and removes the inline panel. |
| Page head | Project rule: compact title plus a period status line, no eyebrow or filler subtitle. | Title is the player; the status line is `POS · TEAM · vs OPP · date`. |

## In scope

- Route `/nhl/player/:playerId` and `NhlPlayerPage`.
- Page states: loading, error with retry, player not found (404), invalid id, and a player with no props on the date (links to that date's NHL slate).
- Head: name, position, team, opponent and date; the player's injury tag when ESPN lists one.
- Tab strip: one tab per market in API order, selected by `?market=` (invalid or absent selects the first); one market section per tab.
- Market section: the "not modelled" caveat, the form chart with its switch and dates, the lines table (line, offering, updated time in CT), and the injury and goalie evidence.
- Pure helpers with Vitest tests in `web/src/utils/nhlPlayer.ts`.

## Out of scope

- Game-page rows opening this page and removing `NhlLineOnlyProps` (53f).
- Any API field, endpoint or ingest (53d is merged). If the page needs a field the endpoint lacks, stop and amend 53d's contract.
- Any NFL, NBA or tennis file, and the shared chart helpers' behavior.
- Folding the NBA and NHL player helpers into one set.
- A projection, edge, rank, pick, P(over) or any model number (no NHL market is modelled).
- Sorting or coloring anything by value beyond the chart's own bar tones.
- An NHL slate-level props board or a link from the slate (not planned).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.

## Build steps

- [x] **Step 1 - Pure helpers** - `utils/nhlPlayer.ts`: `NHL_SEASON_START_MONTH = 7`, `NHL_HISTORY_FROM_YEAR = 2023`, `nhlPlayerPath(playerId, { date, market })` (the link 53f uses, empty params omitted), `nhlPlayerTabs(markets)`, `nhlSelectedMarket(params, markets)`, `nhlFormSample(games)` (drops null values, rounds the average to 2 places), `nhlFormRow(market, opponent)` (Last 5, Last 10, the 10 most recent opponent games), `nhlChartLine(market)` (the standard rung or null), `nhlNotLoadedCount(market, window)`, `nhlSampleNote(market)` ("Started games only" for goalie markets, else null), `nhlPlayerStatus(player)`, and `nhlPlayerInjuryReport(injury)` (the report object `nhlContextSource` takes). *Done when:* `npm --prefix web run test` passes new `nhlPlayer.test.ts` cases for: the path with and without date and market; an invalid `?market=` falling back to the first tab; a null `value` dropped from the sample and counted as not loaded; the standard line chosen over demon and goblin and null with no standard rung; a goalie market getting the started-games note and a skater market getting none; the status line with and without an opponent; a typed assignment pinning `nhlFormRow` to the shared `FormRow`.
- [x] **Step 2 - Route and page shell** - register the route, add `NhlPlayerPage` with the head, injury tag, crumb (to the game page when there is a game, else to the NHL slate for that date), and the loading, error, not-found, invalid-id and no-props states; register the document title with `useRegisterDetailTitle`. *Done when:* in the running app `#/nhl/player/<id>` shows the head and no tabs yet; an unknown id shows the not-found message; `?date=2020-01-01` shows the no-props state with a working link back; `#/nhl/player/abc` shows not found; no console errors; the production build passes.
- [x] **Step 3 - Tabs and lines** - the tab strip and `NhlPlayerMarketSection` with the not-modelled caveat and the lines table. *Done when:* in the running app a forward's markets are tabs in API order with `?market=` selecting one and surviving a reload, a time-on-ice tab reads "min" and a plus/minus tab signs its lines, every tab says it is not modelled and shows no model number, and a screenshot at 1440 and 390 px shows no horizontal page scroll, no text under 11px and no red, green or other signal color on any value.
- [x] **Step 4 - Evidence** - `NhlPlayerEvidence` in each market section: the player's injury entry with its source time and freshness, and both teams' goalies, the player's team first. *Done when:* in the running app a player with no injury entry says the report is a source report and not proof of availability, a slate with no stored goalie context says it is unavailable, and a screenshot at 1440 and 390 px shows no horizontal page scroll, no text under 11px and no signal color on any value.
- [x] **Step 5 - Form chart** - `NhlPlayerFormSection` above the lines table: the window title and summary (average, short note, not-loaded count, the goalie note), the switch, the line legend, and `GameLogBars` with dates. *Done when:* in the running app a forward shows Last 5, Last 10 and vs Opponent with dates and a legend that matches the standard rung; a plus/minus sample with a negative game shows its bar under a zero baseline with a readable label; a goalie shows "Started games only", dates, and "N of 10 games" when short; a window with no games says so in the shared empty text ("since 2023" for vs Opponent); switching windows keeps `market` and `date` in the URL; screenshots at 1440 and 390 px show no horizontal page scroll and no text under 11px.
- [x] **Step 6 - Verify** - the Verify command and a last screenshot pass. *Done when:* `npm --prefix web run verify && cd api && python -m pytest` passes (dummy `DATABASE_URL`), screenshots at 1440 and 390 px of a skater tab, a goalie tab, the no-props state and the not-found state are attached to the review, and the existing NFL and NBA tests still pass.

## Files / areas

- New `web/src/utils/nhlPlayer.ts` and `nhlPlayer.test.ts`
- New `web/src/pages/NhlPlayerPage.tsx` and `web/src/pages/nhl-player.css`
- New `web/src/components/nhl/NhlPlayerPropTabs.tsx`, `NhlPlayerMarketSection.tsx`, `NhlPlayerFormSection.tsx` and `NhlPlayerEvidence.tsx`
- `web/src/routes/sportPages.tsx` (one route added)
- Read-only reuse: `GameLogBars`, `FormSwitch` and the `nflFormWindow` / `nflPropCards` helpers, `playerSearch` and `propSectionIds`, `nhlContext.ts` helpers, `nhlLineOnly.ts` labels, `PageHead`, `LoadingState`, `ErrorState`, `useRegisterDetailTitle`, `nhl-game.css`

## Data / contracts

Load-bearing for 53f.

- Route: `/nhl/player/:playerId`, query params `date` (YYYY-MM-DD, optional), `market` (a market key from the response, optional), `form` (`10` or `opp`, absent means Last 5, written by the shared switch). `nhlPlayerPath` is the only place a link to this page is built; 53f uses it for game-page rows.
- Data: `NhlPlayerProps` from 53d, unchanged.
- No new API shape.

## Testing

- Vitest for the pure helpers (Step 1), per the project gate: logic gets a test, React components do not.
- UI is verified in the running app with screenshots. The local API needs the Windows selector-loop launcher and migration `0050` applied for non-empty NHL reads; the dev server proxies `/api`. Players for the checks come from the dev database (a forward, a goalie, a plus/minus sample with a negative game).
- Existing NFL and NBA tests must still pass.

## Notes for the AI

- Display only. Gray signal colors; no sorting or coloring by value; no UI text under 11px; no em dashes in code, comments or docs.
- Do not edit `nflFormWindow.ts`, `nflPropCards.ts`, `NflPropDetailSections.tsx`, any `Nba*` file, `NhlGameContext.tsx` or `NhlLineOnlyProps.tsx`. If a step cannot be built without one, stop and ask.
- Import via the `~/*` alias, TanStack Query only through the hook, `LoadingState` and `ErrorState` for states, HashRouter links.
- For 53f: before deleting `NhlLineOnlyProps`, check that nothing on this page imports from it, and keep `nhl-game.css` (the evidence here and the game page both use it).
- The local API: the main checkout's `api/.venv`, `DATABASE_URL` from the main checkout's `api/app/.env` (copy it in temporarily and remove it after), the selector-loop launcher, `npm.cmd` on Windows; this worktree's `web/node_modules` is a junction to the main checkout's.
