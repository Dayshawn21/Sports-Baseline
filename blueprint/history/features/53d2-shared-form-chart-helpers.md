# Feature: Shared form chart helpers (53d2)

**From build-plan:** feature 53d2 (added to item 53 on 2026-11-02 so NBA 53b2 and NHL 53e share one chart)
**Status:** not started
**Branch:** `feature/shared-form-chart-helpers`, in worktree `.claude/worktrees/53d2-shared-form-chart`, cut from `master` at `b2298ae3`

## Goal

Make the NFL recent form chart reusable by NBA and NHL without copying it. Three
parts of it are NFL-specific today: the year shown under a bar date, the
"no earlier games ... since 2024" text, and bars that cannot go below zero. Each
takes a sport option with NFL's current value as the default, so every NFL page
renders exactly what it does now. NBA 53b and NHL 53e then call the same code
with their own values. Display only; no new data, endpoint or signal.

## Design reference

None new. The chart keeps its item 51 look (`nfl-prop-detail__*` CSS). The one
visual addition is a bar below a zero baseline, described under Data / contracts.

## What reading the code settled

| Question | Answer | Consequence |
|---|---|---|
| Date year rule | `formHistoryDate` (`nflFormWindow.ts`) calls a season "the calendar year, minus one for January and February", which is NFL's March rollover. The label shows the game's calendar year only when its season differs from now's. Callers: `GameLogBars`, `history()` in `nflPropDetail.ts`, and `nflFormWindow.test.ts`. | New optional `seasonStartMonth` (0-based month a new season-year begins). Default 2 (March) keeps NFL identical. NBA and NHL pass 7 (August), the rule `current_nhl_season` already uses, so an April playoff game viewed in November gets its year. |
| Empty text | `formEmptyText` hardcodes "since 2024" (NFL history floor `PROJECTION_FIRST_HISTORY_SEASON`). | New optional `sinceYear`, default 2024. NHL passes 2023; NBA its own. |
| Bars below zero | `formBars` scales on `max(line, values)` and clamps heights to 0-100, so a negative value draws a zero-height bar. NHL plus/minus is routinely negative. | Scale on a signed range and return a bottom offset for each bar. When no value or line is negative the result is identical to today (pinned by tests), so NFL cannot change. |
| Chart component | `GameLogBars` takes `{ row, sample }`, calls `formHistoryDate(bar.gameDate, now)`, and positions bars with `--h` from `bottom: 0`. | Add an optional `seasonStartMonth` prop and an optional per-bar `--b` offset. CSS adds `bottom: var(--b, 0)`; default 0 changes nothing. |
| Who else uses the pieces | `formBars` is also called by `recentBars` (board cards) and `DetailGameLog`; `FormSwitch` and the window helpers are already sport-neutral. | No signature change that breaks a caller; `FormSwitch`, `formOptions`, `resolveFormWindow`, `formSample`, `formTitle`, `formShortNote` are untouched. |
| Naming | Files are `nfl*`-named but the helpers are generic. | Renaming them is churn for a later item; this one adds options only. |

## In scope

- `formHistoryDate(date, now, seasonStartMonth = NFL_SEASON_START_MONTH)` and exported constants `NFL_SEASON_START_MONTH = 2`, `NFL_HISTORY_FROM_YEAR = 2024` in `nflFormWindow.ts`.
- `formEmptyText(row, window, sinceYear = NFL_HISTORY_FROM_YEAR)`.
- `formBars` over a signed range (below), `NflRecentBar` gaining an optional field.
- `GameLogBars` accepting `seasonStartMonth` and rendering the offset; CSS for the offset and a zero baseline in `nfl-prop-detail.css`.
- Vitest cases pinning NFL output and covering the new behavior.

## Out of scope

- Any NBA or NHL page, route, hook or constant (53b2, 53e). They pass their own numbers.
- Renaming `nflFormWindow.ts`, `nflPropCards.ts` or the `nfl-prop-detail__*` classes.
- Any change to the NFL pages' appearance, the NFL board, `FormSwitch` or the window helpers.
- Tennis's own chart helpers.
- Any new endpoint, migration or stored data.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.

## Build steps

- [x] **Step 1 - Date and empty-text options** - add the two constants and the two optional parameters; no caller changes. *Done when:* `nflFormWindow.test.ts` passes untouched, and new cases pass for: `seasonStartMonth = 7` showing `'26` for an April 2026 game viewed in November 2026, no year for an October 2026 game viewed in November 2026, no year for an April 2027 game viewed in May 2027, and a January game viewed in the next November showing its year; `formEmptyText(row, 'opp', 2023)` reading "since 2023" while the default still reads "since 2024"; `npm.cmd run test` passes.
- [x] **Step 2 - Signed bars** - `formBars` computes `lo = min(0, values, line)` and `hi = max(0, values, line)`, heights as shares of `hi - lo`, and adds `bottomPct` to a bar only when `lo < 0`. *Done when:* `nflPropCards.test.ts` passes untouched (including the TD case returning `{ bars: [], linePct: null }`), and new cases pass for: all-non-negative input returning exactly the objects it returns today (no `bottomPct` key on any bar); a mixed sample (`-2, 0, 3`) giving the negative bar a `bottomPct` at the zero line and a height of its magnitude; an all-negative sample; a line below zero placing `linePct` on the same scale; a single negative value; `formBarLabel(-2)` as `-2`.
- [x] **Step 3 - Chart component and CSS** - `GameLogBars` takes an optional `seasonStartMonth` (passed to `formHistoryDate`), sets `--b` on a bar when `bottomPct` is present, and the CSS draws bars and value labels from `var(--b, 0%)` plus a faint zero baseline only in signed plots. *Done when:* `npm.cmd run build` passes; in the running app a quarterback's model prop and a kicker's line-only tab look the same as on master at desktop and 375px for Last 5, Last 10 and vs Opponent (before and after screenshots compared); a signed sample rendered through a temporary, uncommitted harness shows the negative bar below the zero baseline with its label readable at 11px or larger, then the harness is removed.
- [x] **Step 4 - Verify and publish the names** - run the Verify command and list the exported names. *Done when:* `npm --prefix web run verify && cd api && python -m pytest` passes (dummy `DATABASE_URL`); the NBA (53b2) and NHL (53e) sessions are sent the final names and defaults.

## Files / areas

- `web/src/utils/nflFormWindow.ts` and `nflFormWindow.test.ts`
- `web/src/utils/nflPropCards.ts` (the `NflRecentBar` type lives here) and `nflPropCards.test.ts`
- `web/src/components/nfl/NflPropDetailSections.tsx` and `nfl-prop-detail.css`

## Data / contracts

Load-bearing for NBA 53b2 and NHL 53e. Defaults reproduce NFL exactly.

```
NFL_SEASON_START_MONTH = 2        # March, 0-based
NFL_HISTORY_FROM_YEAR  = 2024
formHistoryDate(date, now, seasonStartMonth = 2)   # NBA and NHL pass 7 (August)
formEmptyText(row, window, sinceYear = 2024)       # NHL passes 2023
formBars(sample, row): { bars: NflRecentBar[], linePct }
  NflRecentBar = { value, opponentTeam, gameDate, heightPct, vsLine, bottomPct? }
  # bottomPct is present only when the plot has a value or line below zero; it is the bar's
  # bottom edge as a share of the plot (the zero line for a positive bar, the bar's low end
  # for a negative one). Absent for all-non-negative input, as today.
GameLogBars({ row, sample, seasonStartMonth? })    # default NFL
```

- Value labels sit above a bar's top edge; a negative bar's label sits at the zero line.
- The chart stays gray (`--text-secondary`, `--text-primary`, `--chart-low`); no signal color.

## Testing

- Vitest for the pure helpers in Steps 1 and 2, including pins that NFL output is unchanged. Components are verified in the running app with before/after screenshots, per the testing gate.
- Manual list: QB model prop and a line-only tab at Last 5, Last 10 and vs Opponent, desktop and 375px; the temporary signed harness.

## Notes for the AI

- NFL behavior must not change. If a step would alter any NFL output, stop.
- Work in the `53d2-shared-form-chart` worktree on `feature/shared-form-chart-helpers`; do not stash, reset or switch branches, and the checkout other sessions use must stay untouched.
- This item edits `nflFormWindow.ts`, `nflPropCards.ts` and `NflPropDetailSections.tsx` with the user's approval; keep the diff to the options above.
- No text under 11px. HashRouter. No em dashes.
- Windows: `npm.cmd`; dev server on 3004.
- Coordination: NBA 53b2 and NHL 53e wait on this item; message both sessions the final names in Step 4.
