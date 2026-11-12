# Feature: Tennis projection history

**From build-plan:** feature 60a (parent 60, Projection history chart on player pages)
**Status:** complete (2026-11-11)
**Branch:** `feature/tennis-projection-history` (cut in this worktree, off `master`)

## Goal

On `/tennis/player/:id`, chart each past match for one prop stat with three
numbers side by side: what happened (the settled result), the PrizePicks line,
and the `props-v3` projection Lineform froze before that match started. It
answers "what did we project, and how did it go" from stored rows only, so the
chart can never flatter the model with a projection recomputed after the fact.

## Design reference

No mockup. Visually it follows the existing full-width form chart
(`GameLogBars` in `web/src/components/nfl/NflPropDetailSections.tsx`, styled by
`nfl-prop-detail__*`): one column per match, oldest to newest, value label on
top, opponent and date under the column. Two differences:

- the line is a short tick **per column** (lines move match to match), not one
  dashed rule across the plot;
- the frozen projection is a small open marker per column on the same scale.

Grayscale only, as `MiniBars` and `GameLogBars` are. The over/under shading of
the result bar against that match's line reuses the existing `is-over` /
`is-under` / `is-push` classes; no new color.

## In scope

- Repository read of the latest pre-start `props-v3` snapshot per line for one
  player's finished matches, with match context (date, tournament, round,
  surface, opponent).
- A pure reducer to one standard line per match and stat, and a pure point
  builder that settles the actual the same way the settled-props table does.
- `GET /tennis/players/{player_id}/projection-history`.
- Web type, API function, hook, a tested util for filter options / filtering /
  scale, the sport-neutral `ProjectionHistoryChart`, and a Projection history
  section on the tennis player page with stat, surface and opponent filters
  kept in the URL.

## Out of scope

- NHL (60b, sketched under Notes so its contract matches), NBA, NFL.
- `props-v4` shadow rows: they are never pooled with v3 and stay unserved.
- Demon and goblin alternate lines (standard lines only).
- Any hit rate, accuracy number, error metric, "beat the line" count, edge,
  pick, rank or color. The settled-props record already exists under Model
  record and stays the only place a record is shown.
- A season filter for tennis: snapshots begin 2026-09-25, so every row is the
  2026 season. The chart shows the date range instead; a season filter arrives
  with the first 2027 row (see Notes).
- New migration or index (see the query-time check in Step 2).
- Changing `/tennis/players/{id}/props`, `get_graded_prop_snapshots` or the
  Model record section.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Repository read and line reducer** - in
  `api/app/repositories/prop_snapshots.py` add
  `get_player_projection_history(db, player_id, version) -> list[ProjectionHistorySnapshot]`.
  It reuses `_LINE_KEY` and `_LATEST_PRESTART_FINISHED_SQL` unchanged (so the
  pre-start and finished-match rules are exactly the graded read's), adds
  `s.player_id = :player_id` and `COALESCE(s.odds_type, 'standard') = 'standard'`
  (case-insensitive), and joins `matches` plus `players` for the opponent. It
  selects `stat_avg AS projection`, `line`, `stat_type`, `snapshot_at`,
  `player_is_p1`, `score`, `best_of`, and the match's date, tournament, round,
  surface, opponent id and name. In a new pure module
  `api/app/core/projection_history.py` add
  `latest_line_per_match(rows) -> list[...]`: when a match has more than one
  standard line for a stat (the line moved between daily fetches), keep the one
  with the latest `snapshot_at`, ties broken by the higher snapshot id (so
  the read also selects `s.id AS snapshot_id`).
  *Done when:* `api/tests/test_projection_history.py` covers one line, a moved
  line (later snapshot wins), a tie on `snapshot_at`, two stats on one match
  kept apart, and empty input; and the read run against the dev database for
  one player with stored snapshots returns rows whose count matches a hand
  `SELECT` with the same filters (recorded in the review packet).

- [x] **Step 2 - Point builder, schema and endpoint** - in
  `app/core/projection_history.py` add
  `history_point(row, join) -> ProjectionHistoryPoint | None` that normalizes the
  stat with `normalize_stat_type`, returns None for a void match
  (`is_completed_score` false) and settles the actual with `resolve_actual`
  (None actual kept as an unsettled point, counted, not charted). In
  `app/services/tennis/projection_history.py` add
  `build_projection_history(db, player_id) -> ProjectionHistory | None`: header
  check (None for an unknown player), the Step 1 read with `PROJECTION_VERSION`,
  box-score candidates from `box_score_repo.get_box_score_candidates` with the
  same sources as `build_player_props`, then the reducer and point builder;
  points sorted by match date then stat. Add the Pydantic models in
  `app/schemas/tennis.py` and the route in `app/routers/tennis.py` (thin, 404
  on None). Stats with no settlement source (fantasy score) yield only
  unsettled points and so never reach the chart.
  *Done when:* tests cover the point builder for a settled score stat, a
  box-score stat with and without a join, a void (retired) match, a null
  projection (kept, actual still charted), and fantasy score as unsettled;
  `curl /tennis/players/{id}/projection-history` returns the contract below
  for a player with snapshots, an empty `points` list for a known player with
  none, and 404 for an unknown id; the response time for the busiest player in
  the dev data is recorded, and if it is over about 300 ms the step stops and
  proposes a `player_id` index as a separate migration rather than adding one.

- [x] **Step 3 - Web contract and derivations** - `ProjectionHistory` and
  `ProjectionHistoryPoint` in `web/src/types/tennis.ts`;
  `fetchProjectionHistory` in `web/src/api/tennis.ts`;
  `useProjectionHistory(playerId)` in `web/src/hooks/useTennisPlayer.ts`
  (key `['tennis', 'player', playerId, 'projection-history']`, the file's
  `PLAYER_STALE_MS`, `retryUnlessNotFound`). New
  `web/src/utils/projectionHistory.ts` with:
  - `historyStatOptions(points)` - stats (keyed by `marketKey`, labeled by
    `marketTitle`) with at least one settled point, ordered by settled count,
    then label;
  - `historyFilterOptions(points, stat)` - surfaces and opponents present for
    that stat, opponents by match count then name;
  - `filterHistory(points, { stat, surface, opponentId })`;
  - `historyScale(points)` - one shared max over actual, line and projection
    (so the three marks are comparable), returning per-point height, line and
    projection percentages; a zero max yields zero heights, not NaN;
  - `parseHistoryParams` / `historySearch` for `?hstat=`, `?hsurface=`,
    `?hopp=`, dropping a surface or opponent that is not present for the
    chosen stat.
  *Done when:* `web/src/utils/projectionHistory.test.ts` covers each function,
  including a null projection, an all-zero sample, an unknown stat in the URL
  falling back to the first option, and a stale opponent param being dropped;
  `npm --prefix web run verify` passes.

- [x] **Step 4 - Chart component** - `web/src/components/shared/ProjectionHistoryChart.tsx`
  and `projection-history.css`. Sport-neutral props: `points` (date, opponent
  label, actual, line, projection), `dateLabel` and `valueLabel` formatters,
  and an `empty` message. Renders the columns described under Design
  reference, a one-line legend ("Bar result · tick line · ring frozen
  projection"), and an accessible label per column ("Mar 3 vs Sinner: 9 aces,
  line 7.5, projected 8.1"). A point with a null projection draws no ring and
  says "no projection" in its label. Wider than the container scrolls
  horizontally inside the chart, never the page.
  *Done when:* the build passes and the component renders on the page in
  Step 5 (component behavior is checked in the browser, not unit-tested, per
  the Testing section).

- [x] **Step 5 - Projection history section on the tennis page** -
  `web/src/components/tennis/player/PlayerProjectionHistory.tsx`, placed in
  `TennisPlayerPage.tsx` directly after `PlayerPropTabs`, under
  `<h2 className="nfl-player-section-title">Projection history <small>frozen pregame projections against results</small></h2>`.
  A `SegmentSwitch` of stats, a surface control (All plus the surfaces
  present) and an opponent control (All plus opponents present), all written
  to the URL through `historySearch` without disturbing `?market=`, `?match=`,
  `?form=` or `?prop=`. When the page's current market tab has history, it is
  the default stat. Under the chart, one gray line: version, date range and
  counts ("props-v3 · Sep 25 to Nov 10 · 14 matches charted, 2 not settled
  yet"). Loading and error use `LoadingState` and `ErrorState`; a player with no
  settled snapshots reads "No frozen projections have settled for {name} yet.
  Snapshots start 2026-09-25." and the filters are hidden.
  *Done when:* in the browser on the dev app, for a player with snapshots:
  the three marks match the API values for at least three columns checked by
  hand; switching stat, surface and opponent updates the chart and the URL,
  and reloading keeps the choice; the market tabs and form chart above behave
  as before; a player with no snapshots shows the empty text; no console
  errors; at 375 px wide the page does not scroll horizontally. Screenshots at
  desktop and 375 px in the review packet.

- [x] **Step 6 - Verify and docs** - run the Verify command; update the
  tennis player page passage of `docs/SportApp-Employer-Interview-Guide.md`
  if it is present (frozen-versus-recomputed is a good interview example);
  note the endpoint in `docs/commands.md` only if that file lists player
  endpoints. *Done when:* Verify passes and the review packet lists any doc
  edits.

## Files / areas

**API**
- `api/app/repositories/prop_snapshots.py` - `get_player_projection_history`, `ProjectionHistorySnapshot`
- `api/app/core/projection_history.py` (new) - `latest_line_per_match`, `history_point`, `ProjectionHistoryPoint`
- `api/app/services/tennis/projection_history.py` (new) - `build_projection_history`
- `api/app/schemas/tennis.py` - `ProjectionHistoryPointSchema`, `ProjectionHistoryResponse`
- `api/app/routers/tennis.py` - the route
- `api/tests/test_projection_history.py` (new)

**Web**
- `web/src/types/tennis.ts`, `web/src/api/tennis.ts`, `web/src/hooks/useTennisPlayer.ts`
- `web/src/utils/projectionHistory.ts` and `.test.ts` (new)
- `web/src/components/shared/ProjectionHistoryChart.tsx` and `projection-history.css` (new)
- `web/src/components/tennis/player/PlayerProjectionHistory.tsx` (new)
- `web/src/pages/TennisPlayerPage.tsx`

## Data / contracts

**Source table:** `prop_projection_snapshots` (migration `0034`), rows with
`projection_version = 'props-v3'`, joined to `matches` (status, score,
best_of, date, tournament, round, surface, p1/p2) and `players` (opponent
name). The projection is the frozen `stat_avg`; no other column is read as a
projection. Settlement inputs come from the existing box-score candidates
(`player_match_stats`, sources `tennisabstract` and `tennismylife`).

**Endpoint (load-bearing, 60b mirrors it):**
`GET /tennis/players/{player_id}/projection-history`, read-only, no query
params, 404 for an unknown player.

```json
{
  "projectionVersion": "props-v3",
  "points": [
    {
      "matchId": 123, "matchDate": "2026-10-04", "tournament": "Shanghai", "round": "R32",
      "surface": "Hard", "opponentId": 456, "opponentName": "J. Sinner",
      "stat": "aces", "line": 7.5, "projection": 8.1, "actual": 9,
      "snapshotAt": "2026-10-04T02:10:00Z"
    }
  ],
  "unsettled": 2
}
```

- `projection` is nullable (v3 stores no `stat_avg` when the projection was
  skipped); `actual` is never null in `points` (unsettled rows only add to
  `unsettled`).
- `stat` is `normalize_stat_type` output (lowercase, underscores). The web
  maps it through `marketKey` in `web/src/utils/tennisPropBoard.ts` to match
  the `?market=` tab keys and labels it with `marketTitle`; Step 3's test pins
  that a stored stat type and a board stat type land on the same key.
- Filtering happens in the browser: one player's standard v3 lines are a few
  hundred rows at most, so one cached response serves every filter.

**Sport-neutral chart point (load-bearing for 60b):**
`{ key: string, date: string, opponentLabel: string, actual: number, line: number, projection: number | null }`.

## Testing

Test gate on. Logic that ships a test in the same step:

| Step | Logic | Test |
|---|---|---|
| 1 | `latest_line_per_match` | `api/tests/test_projection_history.py` |
| 2 | `history_point` (void, unsettled, null projection, box-score join) | same file |
| 3 | stat and filter options, filtering, scale, URL params | `web/src/utils/projectionHistory.test.ts` |

Not unit-tested, per coding standards: the repository SQL (checked against a
hand `SELECT` on dev data), the route, and the React components (checked in the
browser with screenshots). Final gate: `npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- **Frozen only.** Never call `compute_stat_avg`, the props page builder or
  the simulation to fill a missing projection. A null `stat_avg` stays null.
- **Same pre-start rule as grading.** Reuse `_LATEST_PRESTART_FINISHED_SQL`
  rather than writing a looser filter; a snapshot taken after the start must
  never appear.
- **Layering.** SQL only in `app/repositories/prop_snapshots.py`; the reducer
  and point builder are pure in `app/core/`; the router stays thin.
- **Gray means reference.** v3 is a reference projection outside the slices
  48g adopts; the chart states facts and adds no record, color or ranking. The
  over/under shading is the existing grayscale treatment.
- **Render memory.** One player's rows, small and bounded, so it is safe on the
  request path; no snapshot table needed. If Step 2's timing says otherwise,
  stop and propose an index migration (manual, one command at a time against
  Neon) instead of caching.
- **No em dashes** in code comments, copy or docs.
- **Settlement reuse.** `past_prop` in `app/services/tennis/player_detail.py`
  already pairs `is_completed_score` and `resolve_actual`; `history_point`
  follows the same order so both tables agree on which matches settle. Do not
  refactor `past_prop` in this feature.
- **Tennis season filter later.** When any snapshot has a 2027 match date,
  add a season control beside surface in the same util; until then it would be
  a one-option control.

### 60b sketch (NHL, next feature, not built here)

- **Source tables:** `sport_prop_predictions` (`sport = 'nhl'`,
  `model_version = 'nhl-reference-v1'`, frozen `projection`) joined to
  `sport_prop_lines` (`segment = 'full_game'`, `odds_type` standard) and
  `sport_games` (`game_type = 'REG'`, `status = 'completed'`, season, home and
  away teams for the opponent), settled from `nhl_skater_game_stats` and
  `nhl_goalie_game_stats` with the same `settle_frozen` inputs
  `get_frozen_gradeable_lines` uses, and the same rule `l.fetched_at <
  g.start_utc AND p.generated_at < g.start_utc`.
- **Repository:** `get_player_projection_history(db, player_id, first_season)`
  in `app/repositories/nhl.py`, keeping the latest frozen row per
  `(provider, provider_prop_id)` as `get_frozen_gradeable_lines` does, then the
  same per-game reducer.
- **History floor and holdout:** a named constant
  `NHL_PROJECTION_HISTORY_FIRST_SEASON = 2026` (the first frozen season, from
  56c4) bounds the read, so the query never touches 2025, the 2025-26 holdout
  in `nhl_projection_backtest.HOLDOUT_SEASON`, even though no frozen rows exist
  there today.
- **Gated lines** (no confirmed goalie, injury gate) froze with a null
  projection: they chart as result and line only.
- **Endpoint:** `GET /nhl/players/{player_id}/projection-history`, same
  response shape with `season` per point; filters are season and opponent
  (no surface).
- **Page:** `NhlPlayerPage.tsx` renders the same `ProjectionHistoryChart`
  under the market tabs, with an NHL section component and the shared util
  extended with a season option.
