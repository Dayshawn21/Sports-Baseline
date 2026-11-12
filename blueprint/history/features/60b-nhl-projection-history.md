# Feature: NHL projection history

**From build-plan:** feature 60b (parent 60, Projection history chart on player pages)
**Status:** complete (2026-11-11)
**Branch:** `feature/nhl-projection-history` (cut in this worktree, off `master` at `b5e63872`)

## Goal

On `/nhl/player/:id`, chart each past game for one prop stat with the settled
result, the PrizePicks line and the `nhl-reference-v1` projection frozen before
puck drop, the same section 60a put on the tennis player page. It answers
"what did we project, and how did it go" from stored frozen rows only, never a
projection recomputed after the game.

## Design reference

No mockup. The shared `ProjectionHistoryChart` from 60a
(`web/src/components/shared/ProjectionHistoryChart.tsx`) is the visual: one
column per game, oldest to newest, result bar, per-game line tick, open ring for
the frozen projection, grayscale only. The section around it mirrors
`web/src/components/tennis/player/PlayerProjectionHistory.tsx` with a season
control in place of surface.

## In scope

- A repository read in `app/repositories/nhl.py` of one player's frozen,
  pre-puck-drop `nhl-reference-v1` rows on standard full-game lines of
  completed `REG` games, bounded below by `NHL_PROJECTION_HISTORY_FIRST_SEASON = 2026`,
  with the box-score values needed to settle and the opponent team.
- A settlement value helper beside `settle_frozen`, so the chart and the forward
  check agree on what voids, what is not loaded yet, and what the result was.
- The 60a per-game reducer reused for lines PrizePicks re-issued under a new
  prop id.
- `GET /nhl/players/{player_id}/projection-history`.
- Web type, API function, hook, a tested NHL history util (stat, season and
  opponent options, filtering, URL params), and a Projection history section on
  `NhlPlayerPage.tsx` with stat, season and opponent filters in the URL.

## Out of scope

- Demon and goblin lines. Dev data has 2,796 standard frozen rows on completed
  games against 30,968 demon and goblin; the parent item says standard only,
  and mixing alternate lines would put three lines per game on one chart.
- Playoff (`PST`) games. Freezing covers `REG` weeks only (56c4's
  `_WEEK_SCOPE`), so there is nothing frozen to show.
- Any season before 2026, and in particular the 2025-26 holdout
  (`HOLDOUT_SEASON = 2025` in `app/core/nhl_projection_backtest.py`). The floor
  constant keeps the SQL off it; no `--holdout`-style override.
- Any hit rate, accuracy, error metric, "beat the line" count, edge, rank, pick
  or color. The Model record page stays the only place NHL results are counted.
- A below-zero axis for plus/minus. A negative result draws a zero-height bar
  with its signed value label (the shared scale clamps at zero); that is honest
  and changing the shared chart is out of scope.
- Changing the tennis section, `projectionHistory.ts`'s tennis functions, the
  shared chart's props, `get_frozen_gradeable_lines`, or the ranking record.
- New migration or index (see the timing check in Step 2).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Settlement value helper** - in
  `api/app/core/nhl_prop_predictions.py` split `settle_frozen` into
  `frozen_actual(market, skater_row, goalie_row, game_has_box_scores) -> float | str`
  (the stat value in the market's unit, or the reason it is not a call:
  `stats_not_loaded`, `void_dnp`, `missing_stat`) and a `settle_frozen` that
  calls it and then `settle(value, line)`. Same order and same strings as
  today, so the forward check is unchanged.
  *Done when:* every existing test in `api/tests/test_nhl_prop_predictions.py`
  passes unedited, and new tests cover `frozen_actual` for a skater value, time
  on ice in minutes, a goalie value read from the goalie row, a non-starting
  goalie (`void_dnp`), a game with no box scores (`stats_not_loaded`) and a
  missing stat (`missing_stat`, never 0).

- [x] **Step 2 - Repository read** - in `api/app/repositories/nhl.py` add
  `NHL_PROJECTION_HISTORY_FIRST_SEASON = 2026` and
  `get_player_projection_history(db, player_id, model_version, first_season) -> list[NhlProjectionHistoryLine]`.
  The SQL follows `get_frozen_gradeable_lines` exactly where they overlap:
  `DISTINCT ON (l.provider, l.provider_prop_id)` with the same `ORDER BY`,
  `g.game_type = 'REG'`, `g.week IS NOT NULL`, `g.status = 'completed'`, `l.segment = 'full_game'`,
  `l.market IN :markets`, `l.player_id`, `l.provider_prop_id` not null, and
  `l.fetched_at < g.start_utc AND p.generated_at < g.start_utc`. It adds
  `l.player_id = :player_id`, `g.season >= :first_season`,
  `p.model_version = :model_version` and
  `COALESCE(lower(l.odds_type), 'standard') = 'standard'`, and selects the line
  id, game id, season, game date, market, line, `l.fetched_at`,
  `p.projection`, the skater and goalie settle columns plus `is_home`, the
  loaded-games flag, and the opponent team (id and `team_code`, picked from the
  game's home and away teams by the box score's `is_home`; null when the player
  has no box-score row, which only ever happens on a void or unloaded line).
  `NhlProjectionHistoryLine` is a frozen dataclass in
  `app/core/nhl_projection_history.py` (new, pure) whose fields use NHL names
  and which exposes `match_id`, `stat_type`, `snapshot_at` and `snapshot_id`
  as read-only properties (game id, market, line `fetched_at`, line id), so
  `latest_line_per_match` from `app/core/projection_history.py` accepts it
  unchanged.
  *Done when:* run against the dev database for Kirill Kaprizov (sport player
  `363180`) the read returns 13 rows across 2 games, matching the hand
  `SELECT` recorded under Data / contracts (counts as of 2026-11-11; if new
  games have landed, rerun the hand `SELECT` and match that instead); after
  `latest_line_per_match` there are 11 (the 2026-11-07 shots and time-on-ice
  lines were re-issued, and the later `fetched_at` wins); no row has a season
  below 2026; and the review
  packet records the read's warm time for the busiest player, stopping to
  propose a separate index migration if it is over about 300 ms.

- [x] **Step 3 - Point builder, schema and endpoint** - in
  `app/core/nhl_projection_history.py` add
  `nhl_history_point(line) -> NhlProjectionHistoryPoint | None`: `frozen_actual`
  on the row; `void_dnp` returns None (dropped, not counted, as a tennis
  retirement is); `stats_not_loaded` and `missing_stat` return a point with
  `actual=None` (counted as unsettled, never charted). A null frozen projection
  (gated line) stays null. The line's opponent is nullable (no box-score row
  means no `is_home`), but every settled point has a box-score row, so a point
  with an `actual` always has an opponent; the point type makes that explicit
  (opponent non-null on settled points, and an unloaded line is only counted).
  In `app/services/nhl/projection_history.py` (new)
  add `build_projection_history(db, player_id) -> NhlProjectionHistory | None`:
  `get_player` for the 404, the Step 2 read with
  `NHL_PROJECTION_REFERENCE_VERSION` and the floor constant, the reducer, the
  point builder, then points sorted by game date, game id and stat. Pydantic
  models `NhlProjectionHistoryPointSchema` and `NhlProjectionHistoryResponse`
  in `app/schemas/nhl.py`; the route in `app/routers/nhl.py`, thin, 404 on None.
  *Done when:* `api/tests/test_nhl_player_projection_history.py` covers the point
  builder for a settled skater line, a settled goalie line, a void skater, a
  non-starting goalie, an unloaded game, a gated line with a null projection
  (point kept, result still charted), time on ice in minutes, and the reducer
  on a re-issued line (later `fetched_at` wins, line id breaks a tie), plus
  `NHL_PROJECTION_HISTORY_FIRST_SEASON > HOLDOUT_SEASON`; `curl`
  of the endpoint on the local API returns the contract below for Kaprizov
  with 11 points or fewer plus `unsettled`, an empty `points` list for a known
  player with no frozen lines, and 404 for an unknown id.

- [x] **Step 4 - Web contract and NHL derivations** - `NhlProjectionHistory`
  and `NhlProjectionHistoryPoint` in `web/src/types/nhl.ts`;
  `fetchNhlProjectionHistory` in `web/src/api/nhl.ts`; a query factory and
  `useNhlProjectionHistory(playerId)` in `web/src/hooks/useNhl.ts` (key
  `['nhl', 'player', playerId, 'projection-history']`, 5 minute `staleTime`,
  the file's existing not-found retry rule). New
  `web/src/utils/nhlProjectionHistory.ts`, importing `HISTORY_STAT_PARAM`,
  `HISTORY_OPPONENT_PARAM` and `HistoryOpponentOption` from
  `~/utils/projectionHistory` rather than redefining them:
  - `nhlHistoryStatOptions(points)` - markets labeled with `nhlMarketLabel`,
    ordered by count then label;
  - `nhlHistoryFilterOptions(points, stat)` - seasons (newest first, labeled
    `2026-27`) and opponent teams (games faced, then team code);
  - `filterNhlHistory(points, { stat, season, opponentId })`, oldest game first;
  - `parseNhlHistoryParams` / `nhlHistorySearch` for `?hstat=`, `?hseason=`
    (new `HISTORY_SEASON_PARAM`) and `?hopp=`: an unknown stat falls back to
    the open `?market=` tab when it has history, else the first option, and a
    season or opponent that stat has no point for is dropped; other params
    (`date`, `market`) are left alone.
  *Done when:* `web/src/utils/nhlProjectionHistory.test.ts` covers each
  function, including a null projection, a goalie market, an unknown stat in
  the URL, the `?market=` default, a stale season and a stale opponent being
  dropped; `npm --prefix web run verify` passes.

- [x] **Step 5 - Projection history section on the NHL page** -
  `web/src/components/nhl/NhlPlayerProjectionHistory.tsx`, rendered in
  `NhlPlayerPage.tsx` after `PlayerContextSections` and before `PlayerFooter`,
  whether or not the page's date has lines (history does not depend on
  `?date=`). Heading
  `<h2 className="nfl-player-section-title">Projection history <small>frozen pregame projections against results</small></h2>`;
  a `SegmentSwitch` of stats, a season `SegmentSwitch` only when more than one
  season is present, and an opponent `Select` (All plus teams faced) when more
  than one. The default stat is the market tab the page has open (passed in
  as `openMarket`, so it holds with no `?market=` in the URL). The shared
  chart with `valueLabel` from `nhlHistoryValueLabel(stat, value)` (added to
  the Step 4 util with tests during this step: time on ice keeps two
  decimals so a 21.75 line and a 21.79 projection stay apart, plus/minus is
  signed) and the opponent label as the team code. On a phone the stat
  switch scrolls with whole labels rather than squeezing them. One gray footnote under the chart:
  version, date range and counts ("nhl-reference-v1 · Nov 5 to Nov 10 · 3
  games charted; 1 line across all stats not settled yet. Reference only:
  projections are as frozen before each game, never recomputed."). Loading
  and error use `LoadingState` and `ErrorState`; a player with nothing settled
  reads "No frozen projections have settled for {name} yet. NHL freezing
  started 2026-11-05." with the filters hidden. Any new style goes in
  `web/src/pages/nhl-player.css`.
  *Done when:* in the browser on the dev app for Kaprizov or another busy
  player: the three marks match the API values for at least three columns
  checked by hand; switching stat, season (if shown) and opponent updates the
  chart and the URL, a reload keeps the choice, and `?date=` and `?market=`
  survive; the market tabs, form and context sections above behave as before;
  a goalie page shows saves history; a player with no frozen lines shows the
  empty text; no console errors; at 375 px the page does not scroll
  horizontally. Screenshots at desktop and 375 px in the review packet.

- [x] **Step 6 - Verify and docs** - run the Verify command; update the NHL
  player page passage of `docs/SportApp-Employer-Interview-Guide.md` if it is
  present on disk (never staged); note the endpoint in `docs/commands.md` only
  if that file lists player endpoints. *Done when:* Verify passes and the
  review packet lists any doc edits.

## Files / areas

**API**
- `api/app/core/nhl_prop_predictions.py` - `frozen_actual`, `settle_frozen` calls it
- `api/app/core/nhl_projection_history.py` (new) - `NhlProjectionHistoryLine`, `NhlProjectionHistoryPoint`, `nhl_history_point`
- `api/app/repositories/nhl.py` - `NHL_PROJECTION_HISTORY_FIRST_SEASON`, `get_player_projection_history`
- `api/app/services/nhl/projection_history.py` (new) - `build_projection_history`
- `api/app/schemas/nhl.py` - the two models
- `api/app/routers/nhl.py` - the route
- `api/tests/test_nhl_prop_predictions.py` (added tests), `api/tests/test_nhl_player_projection_history.py` (new)

**Web**
- `web/src/types/nhl.ts`, `web/src/api/nhl.ts`, `web/src/hooks/useNhl.ts`
- `web/src/utils/nhlProjectionHistory.ts` and `.test.ts` (new)
- `web/src/components/nhl/NhlPlayerProjectionHistory.tsx` (new)
- `web/src/pages/NhlPlayerPage.tsx`, `web/src/pages/nhl-player.css`

Reused unchanged: `ProjectionHistoryChart.tsx` and its CSS, `historyScale` (called
inside the chart), `latest_line_per_match`, `SegmentSwitch`, `playerSearch`.

## Data / contracts

**Source tables:** `sport_prop_predictions` (`sport = 'nhl'`,
`model_version = 'nhl-reference-v1'`, the frozen `projection` column, no other
column read as a projection), `sport_prop_lines` (full game, standard, linked
player and prop id), `sport_games` (`REG`, `completed`, `season`, `start_utc`,
home and away team), `sport_teams` (opponent code), settled from
`nhl_skater_game_stats` and `nhl_goalie_game_stats` with the inputs
`get_frozen_gradeable_lines` passes to `settle_frozen`.

**Dev data checked 2026-11-11** (local `.env` database):

| Check | Result |
|---|---|
| Frozen NHL rows by season | only season 2026: 41,150 rows, all `nhl-reference-v1`, 2,351 null projections |
| Rows with `generated_at >= start_utc` or `fetched_at >= start_utc` | 0 and 0 (the rule still filters, as grading does) |
| Rows on games with null `start_utc` | 0 |
| Freezing span | first row 2026-11-05 18:21 UTC, 55 games touched |
| Standard, completed, pre-start, after `DISTINCT ON` prop id | 1,163 lines, 39 games, 389 players, 65 null projections (36 of them hits), game dates 2026-11-05 to 2026-11-10 |
| Same player, game and market with more than one prop id | 58 groups (re-issued lines), so the reducer is needed |
| Busiest player, Kirill Kaprizov (`363180`), season 2026 | 13 frozen standard lines, 11 game and market pairs, 2 games, 0 null projections, box scores loaded |
| Most games per player | 3 (Makar, Schaefer, McDavid: 12 lines each) |

So the chart starts thin (two or three games per player) and grows a game or
so every two days; that is expected and the footnote's date range says so.

Hand `SELECT` behind the Kaprizov counts (the Step 2 read must match it):

```sql
WITH frozen AS (
  SELECT DISTINCT ON (l.provider, l.provider_prop_id) l.id, l.game_id, l.market, l.line, l.fetched_at, p.projection
  FROM sport_prop_predictions p
  JOIN sport_prop_lines l ON l.sport = 'nhl' AND l.id = p.prop_line_id
  JOIN sport_games g ON g.sport = 'nhl' AND g.id = l.game_id
  WHERE p.sport = 'nhl' AND p.model_version = 'nhl-reference-v1' AND g.season >= 2026
    AND g.game_type = 'REG' AND g.status = 'completed' AND l.player_id = 363180
    AND l.provider_prop_id IS NOT NULL AND l.segment = 'full_game'
    AND COALESCE(lower(l.odds_type), 'standard') = 'standard'
    AND l.fetched_at < g.start_utc AND p.generated_at < g.start_utc
  ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC, p.generated_at DESC, p.id DESC
)
SELECT COUNT(*), COUNT(DISTINCT (game_id, market)), COUNT(DISTINCT game_id) FROM frozen;
-- 2026-11-11: 13, 11, 2
```

**Endpoint (load-bearing):** `GET /nhl/players/{player_id}/projection-history`,
read-only, no query params, 404 for an unknown player.

Ids below are illustrative; the line, projection and result are Kaprizov's
2026-11-07 re-issued shots line.

```json
{
  "projectionVersion": "nhl-reference-v1",
  "points": [
    {
      "gameId": 57140, "gameDate": "2026-11-07", "season": 2026,
      "opponentId": 12, "opponentName": "CHI",
      "stat": "shots_on_goal", "line": 3.0, "projection": 2.9, "actual": 5,
      "snapshotAt": "2026-11-08T00:47:54Z"
    }
  ],
  "unsettled": 0
}
```

- Same shape as tennis with NHL names: `gameId`/`gameDate` for
  `matchId`/`matchDate`, `season` added, and tennis's `tournament`, `round`
  and `surface` dropped. `opponentId` is a `sport_teams` id and
  `opponentName` its `team_code`.
- `stat` is the `NhlLineOnlyMarket` value, the same key as `?market=`.
- `actual` is a number (time on ice is minutes to two decimals, as
  `nhl_stat_value` returns), never null in `points`; `projection` is nullable.
- `snapshotAt` is the frozen line's `fetched_at`.
- Filtering happens in the browser: one player's standard lines are a few
  hundred a season at most.

**Season constant (load-bearing):** `NHL_PROJECTION_HISTORY_FIRST_SEASON = 2026`
in `app/repositories/nhl.py`, the first season 56c4 froze. It must stay above
`HOLDOUT_SEASON`; a test asserts `NHL_PROJECTION_HISTORY_FIRST_SEASON > HOLDOUT_SEASON`.

## Testing

Test gate on. Logic that ships a test in the same step:

| Step | Logic | Test |
|---|---|---|
| 1 | `frozen_actual`, `settle_frozen` unchanged | `api/tests/test_nhl_prop_predictions.py` |
| 3 | `nhl_history_point`, reducer on NHL rows, floor above holdout | `api/tests/test_nhl_player_projection_history.py` |
| 4 | stat, season and opponent options, filtering, URL params | `web/src/utils/nhlProjectionHistory.test.ts` |

Not unit-tested, per coding standards: the repository SQL (checked against the
hand `SELECT` counts above), the route (checked with `curl`), and the React
section (checked in the browser with screenshots). Final gate:
`npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- **Frozen only.** Never call `project_line`, the player props builder or any
  projection code to fill a missing projection. A gated line's null stays null
  and charts as result and line.
- **Same rules as the forward check.** The SQL copies
  `get_frozen_gradeable_lines`' filters and ordering and adds only the player,
  floor, version and standard filters; do not loosen `fetched_at < start_utc`
  or `generated_at < start_utc`. Settlement goes through `frozen_actual`, the
  same code `settle_frozen` uses.
- **Holdout.** Never read season 2025. The floor is a bound parameter from the
  named constant, not a literal in SQL, and there is no override.
- **Naming clash.** `nhl.py` already has `get_projection_history` (the backtest
  history read); the new function is `get_player_projection_history`. Do not
  rename either.
- **Layering.** SQL only in `app/repositories/nhl.py`; the line type, point
  builder and settlement are pure in `app/core/`; the router stays thin.
- **Gray means reference.** NHL projections are reference only (no adopted
  slice); the section states facts and adds no record, color or ranking. The
  over/under shading is the shared chart's existing grayscale treatment.
- **Render memory.** One player's rows, small and bounded, so it is safe on the
  request path with no snapshot table. If Step 2's timing says otherwise, stop
  and propose an index migration rather than caching.
- **Parallel sessions.** `nhl-goalie-skaters` (item 67) is changing NHL skater
  projections in another worktree and may touch `app/repositories/nhl.py` or
  the NHL player page; rebase onto `master` before `/complete` and resolve any
  overlap by hand. Its new version, if any, is not pooled here: this read pins
  `nhl-reference-v1`.
- **No em dashes** in code comments, copy or docs.

## Completion notes

- Verify (`npm --prefix web run verify && cd api && python -m pytest`) passed on
  2026-11-11: 103 web test files (1,610 tests), typecheck and build; 6,126 API
  tests (dummy `DATABASE_URL`, as CI).
- Dev data: the read matched the hand `SELECT` for Kaprizov (13 rows, 11 after
  the reducer, 2 games); 55 to 121 ms warm, so no index. Endpoint about 190 to
  240 ms end to end; 404 for an unknown id, empty `points` for a player with
  no frozen lines.
- Browser (local API plus dev web): marks matched the API for Kaprizov (shots,
  time on ice) and goalie Mackenzie Blackwood (saves); stat and opponent
  filters write `?hstat=` / `?hopp=` and survive a reload; `?date=` and
  `?market=` are kept; empty state shown; no horizontal scroll at 375 px; no
  console errors.
- Changes found in the browser and folded into Step 5: the default stat
  follows the page's open market tab, `nhlHistoryValueLabel` keeps two decimals
  for time on ice, and the stat switch scrolls with whole labels on a phone.
- Departures from the draft: the opponent comes from the box score's
  `opponent_team_id` (not derived from `is_home`); `_settle_rows` is shared by
  the forward check and this read; the tests live in
  `test_nhl_player_projection_history.py` because
  `test_nhl_projection_history.py` already covers the backtest history read.
- Not done: the interview guide lives only in the main checkout, which the
  worktree session could not edit; the drafted passage is in the shared
  side-session notes (`60b-guide-passage.md`).
- Not deployed.
