# Feature: NBA form chart (53b2)

**From build-plan:** feature 53b2 (split from 53b on 2026-11-02; 53d2 supplied the shared helpers)
**Status:** complete (2026-11-02)
**Branch:** this worktree's branch (`claude/nba-player-page-e5edff`), which is in sync with `origin/master` (53a, 53b and 53d2 are on it)

## Goal

Add the full-width recent form chart to each NBA market tab on
`/nba/player/:playerId`: bars for the player's last games against the market's
stat, the Last 5 / Last 10 / vs Opponent switch, game dates under the bars, and
the stored standard line drawn across. It reuses the NFL chart and window
helpers that 53d2 made sport-neutral and edits no NFL file. Display only: no
sorting or coloring by value beyond the chart's existing above-line and
below-line bar tones.

## Design reference

The NFL player page's chart on `NflPlayerOtherMarketSection.tsx`, the same
components with NBA data. It was reviewed and shipped in item 51 and 53d2, so
no new image is needed. The layout check is a screenshot at 1440 and 390 px in
Step 2.

## What reading the code settled

Verified against `origin/master` (22d186bb and later).

| Question | Answer | Consequence |
|---|---|---|
| Shared pieces | `GameLogBars({ row, sample, seasonStartMonth })`, `FormSwitch({ row, window })`, `parseFormWindow`, `resolveFormWindow`, `formSample`, `formTitle`, `formShortNote`, `formEmptyText(row, window, sinceYear)`, `formBarLabel`, `formHistoryDate(date, now, seasonStartMonth)`. NFL defaults are `NFL_SEASON_START_MONTH = 2` and `NFL_HISTORY_FROM_YEAR = 2024`. | Import them as they are. NBA passes `seasonStartMonth = 7` (August: there are no games between July and September, so a game from January to June belongs to the season that began the year before) and `sinceYear = 2023` (the first stored NBA season). |
| Row type | The helpers take `FormRow = Pick<NflSlateLine, 'recentForm' \| 'recentFormLong' \| 'opponentHistory' \| 'opponentTeam'>`. `NflHistorySample` is `{ average, values: [{ value, opponentTeam, gameDate? }] }`. | `NbaFormSample` (Step 1 of 53b) is structurally assignable, so a plain object of that shape type-checks with no NFL change. A Step 1 test pins this with a typed assignment. |
| Bars row | `GameLogBars` takes `row: Pick<NflBoardLine, 'market' \| 'line' \| 'segment'>`, where `market` is a plain string. The NFL other-markets section passes `{ market, line, segment: 'full_game' }`. | NBA passes the same, with `line` from `nbaStandardLine`, so a market with no standard rung draws bars and no line mark. |
| Double-double | NFL keeps a text list for anytime TD because a game is 0 or 1. `formBars` skips only the TD market. | Bars of 0 and 1 against 0.5 would be misleading, so double-double shows a dated Yes / No list instead of bars, using `nbaRecentValueLabel`. |
| Window switch | `FormSwitch` writes `?form=10` or `?form=opp` through `playerSearch`, keeping `market` and `date`. Last 5 is the default and is not written. | It works unchanged. `nbaPlayerPath` does not carry `form`. |
| Data limits | `recent` holds up to 10 games (a rookie had 6). `opponentGames` holds up to 20 (a sampled big man had 5; the guard had none). Null stats are left out of the sample. | `vs TOR` with no earlier games says "No earlier games against TOR since 2023." (the helper's text). Last 10 with 6 games says "6 of 10 games". A window with unloaded stats says "N not loaded". The vs Opponent chart shows only the 10 most recent, so 20 bars never crowd a phone. |
| Helper wording | The disabled vs Opponent tooltip reads "No opponent this week", an NFL word. | It only shows when `opponent` is null (no game that date), which the page does not render markets for. Accepted; no NFL edit. |
| CSS | The chart and switch classes live in `nfl-prop-detail.css`, which `NflPropDetailSections.tsx` imports. `NbaPlayerMarketSection` already uses the `nfl-prop-detail__section` and `__table` classes. | Importing `GameLogBars` and `FormSwitch` makes that dependency explicit. |

## In scope

- A pure `nbaFormRow(market, opponent)` in `utils/nbaPlayer.ts`: the `FormRow` the helpers take, with Last 5 from the first 5 recent games, Last 10 from all of them, and the opponent window from the 10 most recent opponent games.
- A form section on each market tab: head with the window title and summary (average of the window, short note, not-loaded count), the switch, the standard line legend, the bars with dates, the empty text, and the Yes / No list for double-double.
- Placement: the form section sits above the PrizePicks lines table, as on the NFL page.

## Out of scope

- Any NFL file, the shared helpers' behavior, the NHL and tennis pages.
- Any API change (53a's fields already carry what is needed).
- Rows opening the page, drawer removal and the shared evidence CSS move (53c).
- A game log or season summary card.
- Anything colored by value beyond the chart's own bar tones.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.

## Build steps

- [x] **Step 1 - Pure form row** - `nbaFormRow(market, opponent)` in `utils/nbaPlayer.ts` returning the helpers' `FormRow`, plus `NBA_SEASON_START_MONTH = 7` and `NBA_HISTORY_FROM_YEAR = 2023` constants and `nbaChartLine(market)` (the standard line, or null for double-double). *Done when:* `npm --prefix web run test` passes new cases for: Last 5 is the first five recent games and Last 10 all ten; null stats are dropped from every window; the opponent window shows at most the 10 most recent opponent games; `opponentTeam` is passed through and null when there is no opponent; the row feeds `formOptions`, `formSample` and `formShortNote` from `nflFormWindow` (Last 10 with 6 games gives "6 of 10 games", an empty opponent history gives the "since 2023" text); `nbaChartLine` is null for double-double and for a market with no standard rung; a typed assignment proves the row satisfies `FormRow` (checked by `tsc` in the build).
- [x] **Step 2 - Form section on each tab** - `NbaPlayerFormSection` (head, switch, legend, `GameLogBars` or the double-double list, empty text) rendered inside `NbaPlayerMarketSection` above the lines table. *Done when:* in the running app on a big man with 10 recent games the Last 5, Last 10 and vs TOR windows show 5, 10 and up to 10 bars with dates under them, and `?form=10` survives a reload and a tab change keeps it; a rookie with 6 games shows "6 of 10 games" on Last 10; a player with no earlier games against the opponent shows "No earlier games against TOR since 2023."; a market with no standard rung draws bars with no line mark; double-double shows a dated Yes / No list and no bars; a screenshot at 1440 and 390 px shows no horizontal page scroll, no text under 11px and no new signal color; the production build passes.
- [x] **Step 3 - Verify** - the Verify command, the NFL regression check and a last screenshot pass. *Done when:* `npm --prefix web run verify && cd api && python -m pytest` passes (dummy `DATABASE_URL`); `git diff origin/master --stat` shows no NFL file changed; the NFL player page still renders its chart and switch (spot check plus the existing NFL tests); screenshots at 1440 and 390 px of a modelled tab with the chart, the vs Opponent window, an empty window and the double-double list are attached.

## Files / areas

- `web/src/utils/nbaPlayer.ts` and `nbaPlayer.test.ts`
- New `web/src/components/nba/NbaPlayerFormSection.tsx`
- `web/src/components/nba/NbaPlayerMarketSection.tsx` (render the section)
- `web/src/pages/nba-player.css` (small additions only if the double-double list needs them)
- Read-only reuse: `GameLogBars`, `FormSwitch`, `parseFormWindow`, `resolveFormWindow`, `formSample`, `formTitle`, `formShortNote`, `formEmptyText`, `formOptions` and `playerSearch`

## Data / contracts

- No new API shape. `NbaPlayerMarket.recent` (up to 10) and `opponentGames` (up to 20) from 53a feed the chart; the chart shows the 10 most recent of `opponentGames`.
- `?form=` is `10` or `opp`; absent means Last 5. It is written by `FormSwitch` and read by `parseFormWindow`, unchanged.
- Load-bearing for 53c: `nbaPlayerPath` still builds links with only `date` and `market`; 53c must not add `form`.

## Testing

- Vitest for `nbaFormRow` and `nbaChartLine` (Step 1), per the project gate; React components are verified in the running app with screenshots.
- The local API needs the Windows selector-loop launcher (`C:\dev\SportAppV2\api\.venv`, `DATABASE_URL` from the main checkout's `api/app/.env`); use ports other than 8000 and 3001, which other sessions hold. This worktree's `web/node_modules` is a junction to the main checkout's.
- Existing NFL tests must pass unchanged.

## Notes for the AI

- Display only. Gray signal colors; no sorting or coloring by value; no UI text under 11px; no em dashes in code, comments or docs.
- Do not edit any NFL file (`nflFormWindow.ts`, `nflPropCards.ts`, `NflPropDetailSections.tsx`, `nfl-prop-detail.css` and the rest). If the shared helpers cannot do something NBA needs, stop and ask rather than changing them.
- Import via the `~/*` alias.
- Reference-line rule: the standard rung or nothing, never a guess among alternates.
