# Fix: Game dates on the recent form bars

**Type:** Fix
**Follow-up to:** item 51 (NFL recent form window, master `06b5b19c`)
**Branch:** `fix/nfl-form-dates` (cut from master by `/implement`)
**Status:** complete (2026-11-02)

## The problem

Each bar in the player page's recent form chart (Last 5 / Last 10 / vs
Opponent) is labeled only with the opponent code, so a reader cannot tell when
a game happened. That matters most for vs Opponent, where games can be from a
prior season, and for Last 10 across the season boundary.

The data is already in the slate history query, just not served:
`nfl_player_weekly_stats` rows join `sport_games`, which holds `game_date`,
`season` and `week` (both history queries in `repositories/nfl.py` and
`repositories/nfl_targets.py` read `g.season, g.week`).

## The fix

- API: add an optional `game_date` (ISO `YYYY-MM-DD`, from `sport_games.game_date`,
  the local game date, not `start_utc`, which is the next day in UTC for a night
  game) to `NflHistoryResultSchema`. Fill it in the slate path (history rows gain
  the column) and the targets path (`TargetsObservation` gains it, or reads it from
  the history game). It is on every history sample: `recentForm`,
  `recentFormLong`, `opponentHistory`, `opponentAllowedHistory`.
- Web: `NflHistoryResult.gameDate?: string | null`. Under each bar's opponent
  code the chart shows a short date, `Oct 12`; a game from an earlier season adds
  the year, `Oct 12 '25`. A pure formatter `formHistoryDate(date, season)` in
  `nflFormWindow.ts`, fixed-time tests. The TD text list gets the same date:
  `TD vs TEN · Oct 12`.
- A bar with no date (an older stored slate snapshot, or a null) shows no date
  line, never a placeholder; the opponent code stays.
- The board's mini bars and everything else that reads these samples are
  unchanged (the field is additive and unread there).

## Must not break

- Display only: no projection, edge, rank, sort or color changes; `recentForm`
  stays 5 games and `recentFormLong[:5]` still equals it; values and opponent
  codes unchanged.
- Last 5, Last 10 and vs Opponent still resolve from the same samples.
- Text stays at 11px or more; ten bars each with an opponent code and a date
  must still fit at 375px without horizontal page scroll (dates may stack on two
  lines or abbreviate; decide against a screenshot).
- A stored slate snapshot written before this ships has no `gameDate`: the chart
  must render as today until `nfl_slate_snapshot` runs.

## Build steps

- [x] **Step 1 - Serve the date** - add `game_date` to `NflHistoryResultSchema`,
  fill it in `slate.py` (history dicts gain `game_date` from the query) and
  `targets.py`. Python tests: a history row's date reaches `recent_form`,
  `recent_form_long` and `opponent_history`; a missing date is `None`; targets
  path likewise. *Done when:* `pytest` passes and a live build of week 8 returns
  a `gameDate` on every history value with values and opponents unchanged (diff
  against the stored slate, as in item 51 Step 1).
- [x] **Step 2 - Show the date** - `gameDate` on the web type; `formHistoryDate`
  with a Vitest test (same year, earlier year, null, malformed); bars and the TD
  text list show it; a snapshot without dates renders as before. *Done when:* in
  the running app each bar shows its date, a vs Opponent game from 2025 shows
  `'25`, ten bars fit at 375px with no horizontal scroll, no text under 11px, no
  console errors; Verify passes.

## Files / areas

- `api/app/schemas/nfl.py`, `api/app/services/nfl/slate.py`,
  `api/app/services/nfl/targets.py`, `api/app/repositories/nfl.py`,
  `api/app/repositories/nfl_targets.py`, their tests
- `web/src/types/nfl.ts`, `web/src/utils/nflFormWindow.ts` (+ test),
  `web/src/utils/nflPropCards.ts` (`NflRecentBar` carries the date),
  `web/src/utils/nflPropDetail.ts` (TD text),
  `web/src/components/nfl/NflPropDetailSections.tsx`, `nfl-prop-detail.css`

## Verify

- `npm --prefix web run verify && cd api && python -m pytest` (dummy
  `DATABASE_URL` locally, as CI does).
- Running app: `#/nfl/player/1350?market=rushing_yards`, switch Last 5, Last 10
  and vs BUF; the dates read as real game dates and the vs BUF games show the
  earlier-season year.
- Release note: dates appear in production after `nfl_slate_snapshot` runs, the
  same way `recentFormLong` did; it is the user's call to run it.

## Notes for the AI

- The repository history queries are bounded by `PROJECTION_FIRST_HISTORY_SEASON`;
  add a column to the existing SELECT, never a new read.
- No em dashes; comment only the why (for example why `game_date`, not `start_utc`).

## Built

- The year shows when a game is from an earlier NFL season than the current one (a January game belongs to the season that began the year before), not by calendar year. Dates are limited to `recentForm`, `recentFormLong` and `opponentHistory`; `opponentAllowedHistory` is other players' games and is not charted.
- The TD and history text read `78.0 vs BUF (Sep 7 '25)`.
