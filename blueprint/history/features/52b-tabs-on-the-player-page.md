# Feature: Tabs on the player page (52b)

**From build-plan:** feature 52b (second half of 52; 52a, the endpoint, is on master)
**Status:** complete (2026-11-02)
**Branch:** `feature/nfl-other-markets-tabs` (52a's branch, already squash-merged and identical to master; reused for 52b)

## Goal

On the NFL player page, the line-only markets (pass TDs, interceptions, combo
yards, FG made, kicking points, punts) become tabs in the same strip as the model
props. Each shows its stored line, the alternate lines, and the full-width recent
form chart with the Last 5 / Last 10 / vs Opponent switch and game dates. The
separate Other markets section is removed, and kicker and punter pages get the
tab strip. Display only: no projection, edge, rank, sort, pick or signal color.

## Design reference

None. It reuses the item 51 chart (`GameLogBars`, `FormSwitch`,
`nfl-prop-detail__*` CSS) and the 50b tab strip (`nfl-player-jump`).

## What reading the code settled

| Question | Answer | Consequence |
|---|---|---|
| Who owns the tab strip? | `NflPlayerProps.tsx`, rendered only when `week` (modelled lines) exists. `playerWeekLines` returns null for a kicker or punter, so they have no strip today. | The strip moves to a parent that renders when there are model tabs or line-only tabs. A kicker or punter gets the strip with only line-only tabs. The game-market and usage card above the strip needs a model line (`nflPropDetail(first.row...)`), so it stays tied to `week`. |
| Tab ids and `?market=` | Model and line-only markets are disjoint enums, so one `?market=<market>` can select either. `selectedPropMarket` only accepts the model list. | Pass it the combined list. `playerSearch` already keeps `form` when `market` changes. |
| Window switch | `formOptions`, `formSample`, `formTitle`, `formShortNote`, `formEmptyText` take a `FormRow` (`recentForm`, `recentFormLong`, `opponentHistory`, `opponentTeam`). | A pure adapter builds a `FormRow` from a 52a `NflOtherMarket`: `recentForm = recent[:5]`, `recentFormLong = recent`, `opponentHistory = opponentGames`, `opponentTeam = response.opponent`. The existing helpers and tests apply unchanged. |
| Not-loaded games | `NflHistoryResult.value` is a number; 52a returns `value: null` when a stat is not loaded. | The adapter leaves null games out of the bars and average and reports "N not loaded" in the head. It never draws a zero. |
| Chart line | `formBars` takes a line and a segment; the standard rung is the reference the game page already uses (`overAgainstStandard`). | Line mark = the standard rung when one exists, else none. Above/below shading is the existing gray `--text-primary` / `--chart-low`, not a signal color. |
| Rungs | `DetailLines` is built from a model row and carries P(over). | A small lines table for line-only: Type and Line, labeled reference, no P(over). |
| Data source | `useNflOtherMarkets(playerId, season, week)` (52a) with the player's own `season` and `week`. | One request per player page. The player page stops using `useNflWeekLineOnlyProps`; the board and game page keep it. |

## In scope

- Pure `utils/nflOtherMarkets.ts`: adapter to `FormRow` and sample, the headline
  (standard) line, the tab list (model markets then line-only in
  `LINE_ONLY_MARKETS` order), the not-loaded count.
- `components/nfl/NflPlayerOtherMarketSection.tsx`: head (market label, "Line 1.5 ·
  Reference, recent results only"), the switch and chart, the lines table, states.
- One tab strip for model and line-only tabs; `NflPlayerProps` generalized or a
  thin parent composes the strip and the selected section.
- Loading and error states for the line-only request that never block the model tabs.
- Remove `NflPlayerOtherMarkets.tsx` and its mount; remove `playerLineOnlyGroups`
  and its test if nothing else reads them.
- Generalize `GameLogBars` and `FormSwitch` to take the form row and bars input
  instead of a `NflSlateLine` (no behavior change for model tabs).

## Out of scope

- The 52a endpoint and the board and game endpoints.
- The game page's `NflLineOnlyProps` table and the board's line-only rows.
- The Game log table, This week's lines card (still model lines only), usage,
  record and footer.
- A projection, edge, rank, sort, pick, CLV or color for line-only markets.
- A game-market or usage card on kicker and punter pages.
- Playoff games and partial-game lines.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.

## Build steps

- [x] **Step 1 - Pure helpers and tests** - `utils/nflOtherMarkets.ts` and `nflOtherMarkets.test.ts`: `otherMarketFormRow`, `otherMarketSample` (drops null values, counts them), `standardLine`, `playerTabs(modelMarkets, otherMarkets)`. *Done when:* Vitest covers a market with 10 games (Last 5 equals the first five), a null value dropped and counted, no opponent (vs option disabled through the existing `formOptions`), a standard rung picked over a demon, no standard rung giving no line, a kicker with only line-only tabs, and model and line-only markets never colliding; `npm.cmd run test` passes.
- [x] **Step 2 - Line-only section** - `NflPlayerOtherMarketSection` with head, switch, full-width chart with dates, the lines table and states (no games, no meetings since 2024, a stat not loaded). Chart and switch are generalized so the model tabs render identically. *Done when:* `npm.cmd run build` passes and, in the running app, one quarterback model prop shows the same bars, dates and switch behavior as on master.
- [x] **Step 3 - Tabs and page wiring** - one strip, model tabs then line-only tabs; `?market=` selects either; kicker and punter pages show the strip without the model block; the old Other markets section and mount are removed. *Done when:* in the running app a quarterback shows model tabs plus Pass TDs, Interceptions and Pass+rush yards; selecting one shows its line, alternates and chart; `?market=interceptions&form=10` reloads to the same view; a kicker shows FG Made and Kicking Points tabs and a punter shows Punts; a running back has no extra tabs; no Other markets heading remains.
- [x] **Step 4 - Cleanup and Verify** - remove `playerLineOnlyGroups` and unused CSS or imports; no text under 11px; gray only. *Done when:* `npm --prefix web run verify && cd api && python -m pytest` passes (dummy `DATABASE_URL`) and a 375px capture of a line-only tab shows the chart full width with readable dates.

## Files / areas

- New `web/src/utils/nflOtherMarkets.ts` (+ test), `web/src/components/nfl/NflPlayerOtherMarketSection.tsx`
- `NflPlayerProps.tsx`, `NflPropDetailSections.tsx`, `web/src/pages/NflPlayerPage.tsx`, `web/src/utils/nflPlayer.ts` (+ test), `nfl-prop-detail.css` / `nfl-player.css`
- Removed: `web/src/components/nfl/NflPlayerOtherMarkets.tsx`

## Data / contracts

- Reads only the 52a `NflOtherMarkets` response; no API change.
- Selected tab is `?market=<market>`; the window stays `?form=10|opp` (Last 5 omitted). Changing tab keeps `form`. If `form=opp` is set on a market with no `opponentGames`, `resolveFormWindow` falls back to Last 5 for that view, as for model tabs.
- A line-only tab's DOM id is `prop-<market>`, matching `propSectionIds`.

## Testing

- Vitest for the pure helpers (Step 1). Components are verified in the running app with screenshots at desktop and 375px, per the testing gate.
- Manual list: a QB (Last 5, Last 10, vs opponent), a player with no meetings since 2024 (vs option disabled, note shown), a kicker, a punter, an RB with no line-only lines, a direct `?market=` link to a line-only market, Back from the board.

## Notes for the AI

- Display only. No projection, edge, rank, pick or signal color; label the tab "Reference, recent results only".
- No stored snapshot (52a), so no 503 path; if the request fails the line-only tabs show a quiet note and the model tabs keep working.
- HashRouter: no native `#` anchors. No UI text under 11px. No em dashes.
- `NflLineOnlyProps.tsx` (game page) must keep working untouched.
- The hosted API needs the 52a deploy before Step 3 can be checked live; otherwise run a local API against the shared database (Windows selector-loop launcher).
- Windows: `npm.cmd`; dev server on 3004 (`VITE_API_URL` for the hosted API).
