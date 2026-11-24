# Feature: Tennis props on the player page (53g)

**From build-plan:** feature 53g (first tennis half of item 53; 53h makes the rows open the page and removes the drawer)
**Status:** complete (2026-11-02)
**Branch:** `claude/tennis-player-props-7ac68a` (cut from `feature/nba-player-page` at 7a4dc878, one docs commit ahead of master)

## Goal

On `/tennis/player/:id`, today's props for the player become tabs, one per market (Total games, Aces, Double faults, Moneyline, Win a Set, and any line-only market). Each tab shows the same evidence the board drawer shows today (pick, line, EV, tier, trust, why this signal, context, projection inputs, quality notes) plus a full-width recent form chart with dates and a Last 5 / Last 10 / vs Opponent switch. Display only: nothing the board does not already compute, no new projection, edge, rank, pick or color.

## Design reference

None. Reuses the board drawer's content (`TennisPropEvidencePanel`), the tennis bar chart (`recentStatBars`), the player page layout (`tennis-player-layout`) and the NFL window pattern (`nflFormWindow.ts`, 51) as a model only.

## What reading the code settled

| Question | Answer | Consequence |
|---|---|---|
| Where do today's props come from? | No per-player API. The board builds them client-side from four feeds (`usePrizePicksProps`, `useDKProps`, `useTennisToday` for moneyline, `useBestPicks` for Win a Set) through `buildTennisPropBoard`/`enrichTennisPropLines`. `/tennis/players/{id}/props` is settled past props only. | No new endpoint. The page reuses the four existing hooks (query keys shared with the board, so no duplicate requests) and filters to the player. The "endpoint vs tabs" split is not needed. |
| Which lines are the player's? | `PropLine.playerId` can be null (moneyline and Win a Set rows are built from predictions); `linePlayer` already falls back to a normalized name. | `playerLines` matches `playerId`, else normalized name against `playerName`. A name collision across tours is possible but the existing drawer accepts the same risk; noted below. |
| Several matches on one slate? | A line carries `matchId`; a player normally has one match a day, but a late-night and next-morning match, or a rescheduled one, can both be in the feeds. | Tabs are by market. Inside a tab, lines are grouped by match (start time order). With one match there is no match control; with two, a small "Match" picker (`?match=<id>`) selects which match's lines and form opponent apply. |
| Last 5 / Last 10 / vs Opponent in tennis | The board drawer's bars come from `/matches/{id}/recent-form` (last 5 for both players, one request per match, 38d2). The player page already loads `/players/{id}/matches?limit=` (cap 50), whose rows carry date, opponent id and name, score, aces, double faults and break points. | Last N = the newest N completed matches in the log. vs Opponent = log rows with `opponentId` equal to the selected match's opponent (from `useTennisToday` `p1Id`/`p2Id`, else absent). No per-match form request on the player page. One log request (limit 50) feeds every tab and window. |
| Can the existing evidence content be reused? | `TennisPropEvidencePanel` mixes the summary body with a per-match form request and both players' histories. `LineSummary`, `ContextFacts` and `FormStats` are file-private. | Extract an exported `TennisPropEvidenceBody` (header summary, why this signal, context, projection inputs, quality notes) from the panel; the drawer renders body plus its existing form sections, unchanged. The player page renders body plus its own chart. 53h later deletes the drawer wrapper. |
| Does `recentStatBars` fit a log row? | It takes `RecentMatchResult` (date, opponent, score, result, aces, doubleFaults, breakChancesCreated, breakPointsConverted). Log rows have the same fields under `bpCreated`/`bpWon`. | A pure adapter `logRowToRecent`. Markets `recentStatBars` cannot settle (not in `RECENT_STATS`) show the line and "No recent results for this market", never a zero. |
| Colors | Board EV tone (`evTone` green/red) and `is-negative` pick tone live in `propCard`. | The body keeps those exact classes inside the same element types. Bar shading stays the existing `is-above`/`is-below` classes (check they are not signal colors; see Notes). No color is added anywhere. |
| Model vs no model | `isBoardRateable` splits rated lines from "lines for review"; both exist today. | Rated lines render as the board does. Lines for review render line only, with the existing "Lines for review" label and no EV, rank or pick. |

## In scope

- Pure `utils/tennisPlayerProps.ts`: `playerLines`, `playerMarketTabs` (market order = the board's, tab list from rated plus review lines), `matchOptions` (group by `matchId`), `logRowToRecent`, `formWindowSample` (Last 5, Last 10, vs Opponent by `opponentId`), `formWindowOptions` (with disabled reasons), `parseTennisFormWindow`.
- `TennisPropEvidenceBody` extracted from the drawer panel with no change to the drawer's output.
- `components/tennis/player/PlayerPropTabs.tsx`: tab strip, optional match picker, body, window switch, full-width chart with dates and opponent, states.
- Page wiring on `TennisPlayerPage` between the ELO card and serve/return (or first, if the layout reads better; decided with a screenshot). URL state: `?market=`, `?form=10|opp`, `?match=`; Last 5 and the first tab are omitted from the URL. HashRouter safe.
- Loading and error states for the props feeds that never block the rest of the page; a player with no lines today shows nothing (no empty section), as the settled-props block does today.

## Out of scope

- 53h: board and match page rows opening this page, and removing the drawer or `TennisPropEvidencePanel`.
- Any API, schema, ingest or model change; `buildTennisPropBoard`, ranking, trust, EV, tiers, quality flags.
- Alternate lines (non-adopted goblins and demons). The page follows the board (alternates hidden); showing rungs is a later decision.
- Both players' histories and the serve/return comparison from the drawer (the page already has the player's serve/return and match log; the opponent is not this player's page).
- Last 5 bars for moneyline and Win a Set (not settled by box score; they show the pick and evidence only, as the drawer does).
- Changes to NFL, NBA or NHL files.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Pure helpers and tests (web)** - `utils/tennisPlayerProps.ts` and `tennisPlayerProps.test.ts` with the helpers listed above. *Done when:* Vitest covers lines matched by id and by name only, another player's lines excluded, two matches grouped and ordered by start time, a market with only lines for review still giving a tab, Last 5 equal to the newest five log rows, Last 10 short of ten reporting its count, vs Opponent filtered by `opponentId` and disabled when the match has no opponent id or no meetings, `logRowToRecent` mapping `bpWon` to `breakPointsConverted`, and an unsettled market giving no bars; `npm.cmd run test` passes.
- [x] **Step 2 - Extract the evidence body (web)** - move the summary, why this signal, context, projection inputs and quality notes out of `TennisPropEvidencePanel` into an exported `TennisPropEvidenceBody`; the panel renders it plus its existing form sections. *Done when:* `npm.cmd run build` passes and, in the running app, a board drawer for one Total games row and one Moneyline row is visually identical to master (same text, EV color, bars, histories).
- [x] **Step 3 - Tabs, chart and switch (web)** - `PlayerPropTabs` with the tab strip, match picker, body, window switch, full-width dated chart (`recentStatBars` on adapted log rows, line = the prop's line), the opponent's name on the vs Opponent label, and states. Wired into `TennisPlayerPage` with the `usePlayerMatches` limit-50 request. *Done when:* in the running app a player with PrizePicks lines shows one tab per market; Last 5 / Last 10 / vs Opponent change the bars and dates; `?market=aces&form=opp` reloads to the same view; a player with two matches shows the match picker and switching it changes lines and the vs Opponent opponent; a moneyline tab shows evidence and no chart; a player with no lines shows no props section; a line for review shows exactly what the board shows for it (dimmed there), under a "Lines for review" label, with no rank or pick added.
- [x] **Step 4 - Cleanup and Verify** - no text under 11px, gray only beyond the board's EV rule, 375px capture, `npm --prefix web run verify && cd api && python -m pytest` (dummy `DATABASE_URL`). *Done when:* verify passes and a 375px capture shows the chart full width with readable dates and no horizontal scroll.

## Files / areas

- New `web/src/utils/tennisPlayerProps.ts` (+ test), `web/src/components/tennis/player/PlayerPropTabs.tsx`, tennis player CSS (`tennis-player.css`)
- Changed `web/src/components/tennis/TennisPropEvidencePanel.tsx` (extraction only), `web/src/pages/TennisPlayerPage.tsx`, `web/src/hooks/useTennisPlayer.ts` (limit parameter)
- Untouched: all API files, NFL/NBA/NHL files, `tennisPropBoard.ts`, `tennisPropCards.ts` (read only)

## Data / contracts

- No API change. Reads `PropLine`/`TennisBoardLine`, `MatchPrediction.p1Id/p2Id`, and `PlayerMatchLogRow` (limit 50, the existing cap).
- Load-bearing for 53h: `TennisPropEvidenceBody` and the `?market=`, `?form=`, `?match=` URL shape. 53h will link rows to `/tennis/player/:id?market=<statType>&match=<matchId>`.

## Testing

- Vitest for step 1 (pure logic). Components verified in the running app with desktop and 375px screenshots, per the testing gate.
- Manual: ATP and WTA player with Total games, Aces, Double faults and moneyline; a player with two matches; a player with no lines; a player with no earlier meetings; a market with no settleable stat; direct URL with `market`, `form`, `match`.

## Notes for the AI

- Display only. Keep `evTone` green/red and the pick tones exactly as `propCard` emits them; add no other signal color. Bars use the existing `is-above`/`is-below`; if those classes are colored, keep them as the drawer has them and add nothing.
- Do not edit NFL files; `nflFormWindow.ts` is a model, not an import (it is typed to `NflSlateLine`). The tennis window helpers live in `tennisPlayerProps.ts`.
- Not-played scores (retirements, walkovers) yield null bar values via `playerSets`; never draw zero.
- Tennis ids: the log's `opponentId` is a `players.id`; `MatchPrediction.p1Id/p2Id` are optional, so vs Opponent can be disabled.
- HashRouter. No UI text under 11px. No em dashes. `npm.cmd` on Windows; local API needs the selector-loop launcher.
- Interview guide: update `docs/SportApp-Employer-Interview-Guide.md` at `/complete` only if it describes where tennis props are viewed.
