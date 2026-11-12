# Feature: Why over / Why under on tennis props

**From build-plan:** feature 63
**Status:** complete (2026-11-11)
**Branch:** `feature/prop-reasons` (this worktree, `.claude/worktrees/prop-reasons-66e160`)

## Goal

Give each PrizePicks tennis prop row a collapsible panel that says, in plain
lines, why the line could go over and why it could go under, next to a last-10
bar chart with the line drawn across it. The reasons come from a pure, tested
function in `app/core/`, built from numbers the board already computes and the
player's recent completed matches, so they cost nothing to serve and the same
inputs always give the same text. The panel explains the line; it is not a pick.

## Design reference

- Idea source: Outlier's per-prop "AI Analysis" (two short lists, "why it could
  go over" and "why it could go under", beside a last-10 chart with the line).
  Its look is not a target; the panel uses Lineform's existing table, chart and
  gray tokens.
- Chart: reuse `GameLogBars` (`web/src/components/nfl/NflPropDetailSections.tsx`),
  the same chart the tennis player page draws (53g). Its bars are already
  neutral (`--text-primary` above, `--chart-low` below,
  `components/shared/player-panel.css`).
- No mockup or image is needed: this is a new panel in an existing table, not a
  replication.

## In scope

- `app/core/tennis_prop_reasons.py`: pure rules turning one line's inputs into
  at most 3 over reasons, at most 3 under reasons and at most 2 caveats.
- A pure helper in the same module that turns the player's match log into the
  recent values for the line's stat, reusing `app/core/prop_settlement.py`
  (`parse_sets`, `actual_value`, `box_score_value`) and
  `app/core/tennis_grading.is_completed_score`. The prop's own match is always
  left out, so a line on a match that has already been played never explains
  itself with its own result.
- `GET /tennis/props/prizepicks/{prop_id}/reasons`, read-only, fetched only when
  a row's panel opens.
- A web type, API function, hook and a tested helper, then a toggle and an
  expanded row in `TennisPropTable`, so the panel appears on the tennis prop
  board and on the match page's prop panel (`MatchPropsPanel.tsx`), which reuses
  the table.
- Loading, error, no-history and unlinked-player states.

## Out of scope

- **DraftKings rows.** Its match-odds rows reuse `match_odds` ids, which collide
  with prop ids, and carry no player. Moneyline and win-a-set rows built in the
  browser are out too. A later item can add DraftKings player props.
- **Other sports** (NFL, NBA, NHL). The core rules are written for tennis inputs;
  sharing them is a later item once tennis has been used.
- **An LLM-written version.** No Claude call anywhere in this feature. If one is
  wanted later, it is its own build-plan item that goes through Ask Lineform
  (`app/services/ask/`): off unless `ASK_ENABLED=true`, 20 questions per client a
  day, the $1 global daily cap, paid runs never in Verify or CI, and it would
  phrase the deterministic reasons, never invent new ones.
- Any change to probabilities, projections, edges, ranks, sort order, adoption,
  `props-v3`/`props-v4`, snapshots or the forward check. The panel reads; it
  never writes.
- Persisting which panels are open (no URL or storage state).
- A head-to-head rule. The opponent figure the board already computes is used;
  a head-to-head sample would be too small to say anything.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Recent values from the match log** - in
  `app/core/tennis_prop_reasons.py`, the `RecentValue` dataclass and
  `recent_values(stat, entries)`: for each match-log entry, newest first, the
  stat's value from the player-oriented score (`actual_value(stat, sets, True)`)
  or the joined box score (`box_score_value`); entries whose score is not a
  completed match (retirements, walkovers), whose value is unknown, or whose
  `match_id` is the prop's own match are skipped; capped at 20. The input is a plain dataclass the service fills, so
  core never sees an ORM row. Before writing it, confirm the match log's `score`
  is player-first (the web's `fromSets` reads it as mine-theirs); if it is not,
  the helper takes `player_is_p1` per entry. *Done when:* tests cover a
  score stat, a box-score stat, a missing box score (skipped), a retirement
  (skipped), the prop's own match (skipped), an unsupported stat
  (`fantasy_score` returns an empty list), the 20 cap and newest-first order,
  and pass.
- [x] **Step 2 - Reason rules** - `ReasonInput`, `Reason`, `RecentSummary`,
  `PropReasons` and `build_reasons(input)` with the rules, thresholds and caps
  under **Factor rules**, plus `REASONS_VERSION = "reasons-v1"`. *Done when:*
  every test under **Testing / core** passes and no rule reads a clock, the
  database or a model file.
- [x] **Step 3 - Service** - `get_prizepicks_prop(db, prop_id)` in
  `app/repositories/props.py` (one row, `source = 'prizepicks'`, any date);
  `_match_log` in `app/services/tennis/player_detail.py` made public as
  `match_log` (callers updated, behavior unchanged); and a new
  `app/services/tennis/prop_reasons.py` with `build_prop_reasons(db, prop, line)`
  that takes the raw prop and its enriched `PropLine`, loads the last 20 log
  entries when the player is linked, fills `ReasonInput` (today's `best_of`
  comes from the raw prop, since `PropLine` does not carry it) and returns
  `PropReasons` plus the oldest-first chart values. *Done when:* `pytest` passes
  and a one-off call against a stored PrizePicks prop, run from a REPL and not
  committed, prints the reasons.
- [x] **Step 4 - Route** - the Pydantic response in `app/schemas/props.py` and
  the route in `app/routers/props.py`, which loads the prop, enriches it through
  the same `_enrich_props` the board uses (so the projection, sample and flags
  match the row) and calls the service. *Done when:* the route returns the shape
  under **Data / contracts** for a stored PrizePicks prop with a linked player
  (show the JSON and the response time), 404 for an unknown or non-PrizePicks
  id, 422 for a prop without a line, a no-history body for `fantasy_score`, and
  `pytest` passes, including a router test with the repository and service
  mocked for the 404 and 422 paths.
- [x] **Step 5 - Web data layer** - `TennisPropReasonsResponse` types in
  `web/src/types/tennis.ts`; `fetchTennisPropReasons(propId)` in
  `web/src/api/tennis.ts`; `useTennisPropReasons(propId, enabled)` in
  `web/src/hooks/` (key `['tennis', 'prop-reasons', { propId }]`, `staleTime`
  5 minutes, enabled only while the panel is open); and
  `web/src/utils/tennisPropReasons.ts` with `hasReasons(row)` (PrizePicks source,
  positive id and a numeric line, not a browser-built
  moneyline or win-a-set row) and `reasonsChartSample(recent, line)` (maps the
  response's oldest-first values to the `NflHistorySample` `GameLogBars` takes,
  through the existing `tennisFormSample`). *Done when:* Vitest covers both
  helpers (each excluded row kind, a push, an empty list) and `npm run build`
  passes. No UI yet.
- [x] **Step 6 - The panel** - `web/src/components/tennis/TennisPropReasons.tsx`
  and a toggle in `TennisPropTable`: a "Why over / under" text button in the
  Trust cell beside "Open player", only where `hasReasons(row)`;
  `aria-expanded`, `aria-controls`; the row's click handler ignores clicks on a
  `button` the way it ignores links, so opening the panel never navigates. An
  open row is followed by a full-width `<tr>` holding the chart, the two lists,
  the caveats and the "Reference, not a pick" label. Several panels may be open
  at once; open state lives in the table and resets when the market changes.
  States: inline loading text, inline error with a retry button, "No recent
  results to chart" when `recent` is empty (the caveat says why), and "Nothing in the
  recent data points this way" for an empty side. *Done when:* in the running app
  on a stored slate, a rated line and a line for review each open and close by
  mouse and keyboard without navigating; the row still opens the player page; the
  chart's values match the player page's Last 10 chart for the same player and
  market; nothing in the panel is green or red; screenshots at desktop width and
  at 375px show no horizontal scroll; the console has no errors; the match page's
  prop panel shows the same toggle.
- [x] **Step 7 - Docs** - the `/tennis/props` row of the API routes table in
  `project-overview.md` gains `prizepicks/{id}/reasons`; the build-plan map row
  for 63 reads complete at `/complete`; update
  `docs/SportApp-Employer-Interview-Guide.md` on disk if it exists (local,
  untracked, never staged) with the deterministic-explanations decision. *Done
  when:* Verify passes from the repo root.

- [x] **Repair - old line ids** (from the invariants review, low severity) -
  `recent_values` takes a `before` date and the service passes the line's UTC
  start day (`line_cutoff`, the fetch day when there is no start), so a line
  read by an old id is explained only by matches dated before it. *Done when:*
  core and service tests cover the cutoff, and a stored 2026-09-20 line charts
  only matches through 2026-09-19. Known limit, not fixed: an old line's
  projection reason still uses today's rolling stats, because the route
  enriches the line now; the web only opens today's board rows.

## Factor rules

All thresholds are named constants in the module. "Recent" means completed
matches only, newest first. A value equal to the line is a push and is left out
of every share's denominator.

| Constant | Value | Meaning |
|---|---|---|
| `WINDOW` | 10 | matches for the chart and the hit, center and trend rules |
| `SPLIT_WINDOW` | 20 | matches the surface rule may look back through |
| `MIN_VALUES` | 3 | fewer recent values than this turns off every history rule |
| `LEAN_SHARE` | 0.6 | a share at or above this leans over; at or below `1 - 0.6` leans under |
| `thin_margin(line)` | `max(0.5, 0.05 * line)` | a gap smaller than this is "thin" |
| `MIN_SURFACE_VALUES` | 3 | on-surface values the surface rule needs |
| `SMALL_SAMPLE_MATCHES` | 10 | imported from `app/core/rolling_stats.py`, not redefined |

**Reasons**, in priority order. Each rule adds at most one reason to one side;
each side keeps its first three.

1. `projection` - needs the board's projection (`stat_avg`, only when
   `projection_status == "ok"`). Gap at least `thin_margin` above the line: over,
   "Model projects 9.4, 1.9 above the line". Below: under, the same with
   "below". A smaller gap is caveat `thin_projection_gap` instead, never a side.
   This is the number the Gap column already shows, so the panel adds no new
   model claim.
2. `hit_rate` - over share of the last `WINDOW` values. At or above
   `LEAN_SHARE`: over, "Cleared the line in 8 of 10 recent matches". At or below
   0.4: under, "Stayed under the line in 7 of 10 recent matches". Between: none.
3. `center` - average and median of the last `WINDOW` values. Both above the
   line: over, "Average 9.6 and median 9, both above the 7.5 line". Both at or
   below: under, the same wording. Split: one reason on the median's side, "Median
   6 is below the line; its highest values lift the average to 8.1" (or the
   mirror).
4. `trend` - needs at least 8 values. Last-5 average minus last-10 average at
   least `thin_margin`: over, "Last 5 average 10.2, up from 8.6 over 10".
   At most `-thin_margin`: under, "down from".
5. `surface` - needs today's surface and at least `MIN_SURFACE_VALUES` values on
   it in the last `SPLIT_WINDOW`. Over share at or above `LEAN_SHARE`: over, "On
   clay: over in 4 of 5 since Sep 14". At or below 0.4: under. An unknown
   surface skips the rule.
6. `format` - only volume stats (`total_games`, `total_games_won`, `aces`,
   `double_faults`, `break_points_won`). Best of five today while fewer than
   half of the last `WINDOW` were best of five: over, "Best of five today; most
   recent matches were best of three". Best of three today while at least half
   were best of five: under, the mirror. Set counts and first-set stats skip it.
7. `opponent` - needs `opponent_stat_avg` and `opponent_matches_count` at least
   `SMALL_SAMPLE_MATCHES`. At least `thin_margin` above the line: over,
   "Opponent's matches average 9.8 for this stat" (wording follows the existing
   meaning of `opponent_stat_avg`, read before writing the text). Below: under.

**Caveats**, in priority order, at most two:

1. `no_player` - the prop has no linked player, so there is no match log.
2. `no_history` - the stat cannot be read from scores or box scores
   (`fantasy_score`: "Scores and box scores do not record this market, so there
   is no recent history"), or no completed match has a value ("No recent
   completed matches for this market").
3. `small_sample` - fewer than 5 recent values, or the rolling sample
   (`matches_count`) below `SMALL_SAMPLE_MATCHES`: "Only 4 completed matches in
   the sample" for the recent values, "The model's rolling stats rest on 6
   matches" for the rolling sample.
4. `stale_stats` - `stats_stale` is true: "Rolling stats are out of date".
5. `thin_margin` - the last-10 average sits within `thin_margin` of the line:
   "Average 7.7 sits within 0.5 of the line".
6. `thin_projection_gap` - from rule 1.

Numbers print with at most one decimal and no trailing `.0`; dates print as
`Sep 14`. Text is built in core so the API and the tests see the same strings.

## Files / areas

| File | Change |
|---|---|
| `api/app/core/tennis_prop_reasons.py` | new, pure: `recent_values`, `build_reasons`, dataclasses, constants |
| `api/tests/test_tennis_prop_reasons.py` | new, core tests |
| `api/app/repositories/props.py` | `get_prizepicks_prop` |
| `api/app/services/tennis/player_detail.py` | `_match_log` becomes public `match_log` |
| `api/app/services/tennis/prop_reasons.py` | new, loads the log and calls core |
| `api/app/schemas/props.py` | `PropReasonSchema`, `RecentValueSchema`, `RecentSummarySchema`, `TennisPropReasonsResponse` |
| `api/app/routers/props.py` | the reasons route |
| `api/tests/test_prop_reasons_route.py` | new, 404 and 422 paths with mocks |
| `web/src/types/tennis.ts` | response types |
| `web/src/api/tennis.ts` | `fetchTennisPropReasons` |
| `web/src/hooks/useTennisPropReasons.ts` | new hook |
| `web/src/utils/tennisPropReasons.ts` (+ `.test.ts`) | `hasReasons`, `reasonsChartSample` |
| `web/src/components/tennis/TennisPropReasons.tsx` | new panel |
| `web/src/components/tennis/TennisPropTable.tsx`, `tennis-prop-table.css` | toggle, expanded row, panel layout |
| `blueprint/context/project-overview.md` | API route row |

## Data / contracts

**Load-bearing:** the response shape and the reason `key` values. A later
DraftKings, other-sport or Ask-phrased version reuses both, so a key is never
renamed under `reasons-v1`; changing a rule's threshold or text bumps the
version.

`GET /tennis/props/prizepicks/{prop_id}/reasons` (camelCase, like every
`/tennis/props` response):

```json
{
  "propId": 123456,
  "playerId": 812,
  "statType": "aces",
  "line": 7.5,
  "version": "reasons-v1",
  "recent": [
    { "matchDate": "2026-10-29", "opponentName": "A. Player", "surface": "Hard", "bestOf": 3, "value": 9 }
  ],
  "summary": { "matches": 10, "over": 8, "under": 2, "push": 0, "average": 9.6, "median": 9.0 },
  "over": [ { "key": "hit_rate", "text": "Cleared the line in 8 of 10 recent matches" } ],
  "under": [ { "key": "trend", "text": "Last 5 average 7.2, down from 9.6 over 10" } ],
  "caveats": [ { "key": "small_sample", "text": "Only 4 completed matches in the sample" } ]
}
```

- `recent` is oldest first and at most `WINDOW` long (the chart's order); the
  core works newest first and the service reverses it.
- `summary` is null when there are fewer than `MIN_VALUES` values.
- `key` is one of `projection`, `hit_rate`, `center`, `trend`, `surface`,
  `format`, `opponent` (reasons) or `no_player`, `no_history`, `small_sample`,
  `stale_stats`, `thin_margin`, `thin_projection_gap` (caveats).
- 404: unknown id, or the id is not a PrizePicks prop. 422: the prop has no line.
- Read-only, no `require_api_key` (it spends nothing and writes nothing), and it
  takes the default per-client rate limit from `rule_for_path`. One prop's
  enrichment plus a 20-row log and its box-score join is light, so no
  `report_snapshots` copy is needed; `/check` records the response time on a
  stored prop to confirm.

No migration. No new stored data.

## Testing

**Core (`api/tests/test_tennis_prop_reasons.py`), fixed dates, no database:**

- 10 of 10 over: `hit_rate` and `center` on the over side with the exact texts.
- 2 of 10 over: `hit_rate` under. 5 of 10: no `hit_rate` reason.
- A push is left out of the share (7 of 9, not 7 of 10).
- Average above and median below the line: `center` on the under side with the
  "lift the average" text.
- Fewer than 3 values: no history reason, `small_sample` caveat, `summary` null.
- `fantasy_score` with a projection: only `projection` and `no_history`.
- Projection gap below `thin_margin`: `thin_projection_gap` caveat, no side.
- Trend needs 8 values; a rise of exactly `thin_margin` counts.
- Surface: 2 on-surface values skip it; unknown surface skips it.
- Format: best of five today for `aces` adds over; for `total_sets` adds nothing.
- Opponent below `SMALL_SAMPLE_MATCHES` matches is skipped.
- Caps and order: inputs that fire every rule return the first three per side in
  priority order and the first two caveats.
- No key appears twice across `over` and `under`.
- `thin_margin` is 0.5 for a 7.5 line and 1.075 for a 21.5 line (it prints as 1.1).
- Step 1's `recent_values` cases.

**Route:** 404 and 422 with the repository and service mocked; the happy path is
checked against a stored prop in `/check`, per the standard that route
integration is verified by running it.

**Web (Vitest):** `hasReasons` (PrizePicks yes; DraftKings, moneyline,
win-a-set, null line no; any market yes, since the endpoint answers fantasy score with its projection and a caveat) and `reasonsChartSample` (order, push,
empty).

**Manual (`/check`):** the Step 6 done-when, on the tennis prop board and the
match page, desktop and 375px, plus one prop whose stat is `fantasy_score` and,
if a stored slate has one, a prop with an unlinked player.

## Notes for the AI

- **`core/` stays pure.** `tennis_prop_reasons.py` imports only the standard
  library and other `app/core/` modules; the service fills plain dataclasses.
- **Gray.** Tennis prop slices are reference unless 48e adopted them, and this
  panel stays gray even on an adopted row: headings, bullets and labels use the
  neutral text tokens, never the signal greens or reds, and the panel says
  "Reference, not a pick". Run `/invariants-review` before `/complete`.
- The board's numbers come from `_enrich_props`; call it for the one prop rather
  than recomputing any projection, so the panel and the row cannot disagree.
- Reuse `prop_settlement` and `normalize_stat_type` (`app/core/prop_projection.py`)
  for stat names and values; do not port the web's `RECENT_STATS`.
- The row click navigates to the player page; the toggle must not.
- `TennisPropTable` is shared with `MatchPropsPanel`; keep the toggle working in
  both and check both.
- No `Any`, `X | None` in new Python, the `~/*` import alias, no em dashes in
  text, comments or the commit.
- Build-plan number 63 was assigned across the parallel worktrees on
  2026-11-11 (59 record strip, 60 projection history, 61 calculators, 62 prop
  board row polish, 64 tennis context filters); the entry sits right after 58
  because each branch adds only its own line.
