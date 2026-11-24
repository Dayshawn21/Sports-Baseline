# Feature: Tennis context filters

**From build-plan:** feature 64a (parent 64, Context filters on the prop boards)
**Branch:** `feature/tennis-context-filters` (worktree `.claude/worktrees/board-filters-3c35d4`)
**Status:** complete (2026-11-11)

## Goal

Let a user narrow `/tennis/props` to the matches they care about: by surface,
best-of format, tour, and PrizePicks line type (standard, demon, goblin). The
idea comes from PickFinder's advanced filters. Display only: the filters choose
which rows show, never how a row is projected, rated, ranked or colored.

Item 64 was too big for one spec (three boards, three data sources), so it is
split. 64b (NBA) and 64c (NHL) are specced later; their data sources and test
plans are pinned in the cross-sport table below so they need no new research.

## Cross-sport filter table (all of item 64)

What each board's response already carries, checked on 2026-11-11 against
`web/src/types/{tennis,nba,nhl,nhlContext}.ts` and the routers.

| Sub | Filter | Values | Data source | API change |
|---|---|---|---|---|
| 64a | Surface | All / Hard / Clay / Grass | `PropLine.surface`, filled from the match prediction by `enrichTennisPropLines` | None |
| 64a | Best-of | All / Best of 3 / Best of 5 | Not in any board response today. `props.best_of` (relinked or match) reaches `_enrich` in `routers/props.py` and is dropped; `PredictionOutput.best_of` exists and `_to_schema` drops it | **Yes:** `bestOf: number \| null` on tennis `PropLine`, `bestOf: number` on `MatchPrediction` |
| 64a | Tour | All / ATP / WTA / Challenger / WTA 125 | Already a control (`TENNIS_TOUR_FILTERS`, `tourMatches`), held in `useState` | None; moves into the URL |
| 64a | Line type | Standard + demon (default) / Standard / Demon / Goblin | `PropLine.oddsType` via `payoutTier`; goblins dropped today by `enrichTennisPropLines(..., includeAlternates=false)` | None |
| 64b | Teammate out | Players listed `Out` on the date | `NbaPropBoardGame.injuryReport.injuries` (ESPN: `team`, `status`, `playerId`, `espnAthleteId`), already on `GET /nba/props` | None |
| 64c | Starting goalie | Any / Confirmed / Confirmed or expected | `NhlSlateGame.context.goalies` (`away`/`home`: `status`, `playerId`, `team`, plus `freshness`) from the cached `GET /nhl/slate`; the board game has no goalie context | None (second, cached request joined by `gameId`); fallback if review prefers: add `goalies` to the cached `/nhl/props` body |

Util tests per sub-feature:

- **64a** `web/src/utils/tennisPropBoard.test.ts` (extend): surface, best-of,
  tour, line-type matching, composition, URL parse and write, return path.
  `api/tests/test_props_router_best_of.py` (extend): `best_of` passes through,
  null when unlinked. A `MatchPrediction` schema test for `best_of`.
- **64b** new `web/src/utils/nbaTeammateOut.test.ts`: option list (only `Out`,
  case-insensitive; unavailable report lists none; stale report entries
  marked), row match (same game side via `gameSideTeam`, the injured player's
  own rows excluded, other games excluded), unknown id from an old link reads as
  no filter, composes with `filterBoardMarkets`.
- **64c** new `web/src/utils/nhlGoalieFilter.test.ts`: skater row passes on the
  opponent side's status, goalie row passes only for its own side's listed
  starter (`playerId` match), `expected` passes only "Confirmed or expected",
  `stale`/`unavailable` freshness and `unknown`/`not_reported` never pass, a
  game missing from the slate never passes, unknown param reads as Any.

## In scope (64a)

- `bestOf` on the tennis prop line and match prediction responses, and on the
  web types.
- One pure filter in `web/src/utils/tennisPropBoard.ts`:
  `TennisContextFilter = { surface, bestOf, tour, lineType }`, a URL parser and
  writer, and a matcher used by `buildTennisPropBoard`.
- Surface, Best-of and Line type controls beside the existing Source and Tour
  segments in `PropBoardFilters`; all four filters in the URL (`surface`, `bo`,
  `tour`, `line`), so a board link and the player-page Back keep them.
- Empty and old-link states: an unknown param value reads as All; a filter that
  empties the board shows the existing empty state naming the filters.

## Out of scope

- 64b (NBA) and 64c (NHL): later sub-features.
- Line-type filters on the NBA, NFL and NHL boards (the brief names tennis only).
- PickFinder's hit-rate, H2H, defense-vs-position and with-or-without-teammate
  history splits: each is new evidence, not a filter over loaded data.
- Indoor/outdoor: `indoor` is only on match detail; a later choice.
- Any change to projections, `isTennisRateable`, adoption, `compareLines`
  order, payout tags or gray colors. A goblin shown by the filter is a
  "Review" row unless 48g adopted it, exactly as today's adopted-goblin path.
- The tennis slate (`/tennis`) and the match and player pages.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - `bestOf` in the API** - add `best_of: Optional[int] = None` to
  `schemas/props.py` `PropLine` and set it in `_enrich` from `prop.best_of`
  (the raw value, **not** the `or 3` projection fallback); add
  `best_of: int` to `schemas/tennis.py` `MatchPrediction` and set it in
  `_to_schema`. *Done when:* the extended `test_props_router_best_of.py` shows
  `best_of` 5 and 3 passing through and `None` for an unlinked prop, a
  `MatchPrediction` test shows `best_of` serialized as `bestOf`, `pytest`
  passes, and `GET /props/prizepicks` and the today predictions response show
  `bestOf` locally.
- [x] **Step 2 - Web types and enrichment** - `bestOf?: number | null` on
  `PropLine`, `bestOf?: number` on `MatchPrediction`; `TennisBoardLine` gains
  `bestOf: number | null`, filled `line.bestOf ?? match?.bestOf ?? null`
  (same precedence as `surface`); moneyline and Win a Set rows take it from
  their match. *Done when:* a test shows a linked line, an unlinked line found
  by player name, and a line with no match each get the right `bestOf`, and
  `npm run test` passes. No UI change.
- [x] **Step 3 - The filter util** - `TennisContextFilter`, `TENNIS_SURFACE_FILTERS`,
  `TENNIS_BEST_OF_FILTERS`, `TENNIS_LINE_TYPE_FILTERS`,
  `parseTennisContextFilter(params)`, `withTennisContextFilter(params, filter)`
  and `tennisContextMatches(line, filter)`. Surface compares case-insensitively;
  a null surface or `bestOf` passes only All; line type uses `payoutTier`, so a
  non-PrizePicks row (null tier) passes only the default. `buildTennisPropBoard`
  takes the filter in place of its `tour` argument and passes
  `includeAlternates` when line type is Goblin. *Done when:* tests cover each
  filter's values, null fields, non-PrizePicks rows under a line-type choice,
  the goblin default (hidden) and Goblin choice (shown, in `other`, unless
  adopted), all four composed, unknown params reading as defaults, and a
  round trip parse/write that leaves `player` and `market` params untouched;
  existing `buildTennisPropBoard` tests pass after the signature change.
- [x] **Step 4 - Controls and URL** - `TennisPropBoardPage` reads the filter
  from the URL instead of `useState` for tour; `PropBoardFilters` gains
  Surface, Best-of and Line type segments (Line type disabled with a hint when
  Source is DraftKings, Market odds or Model only); `tennisBoardPath` carries
  the filter so the player-page Back returns to the same view; the market
  reset effect also fires on the new filters. *Done when:* in the browser each
  control narrows the rows and counts, the URL updates, reload and the
  player-page Back restore the view, a filter with no matches shows the empty
  state, the bar wraps cleanly at 375px with no horizontal scroll, and the
  console has no errors.
- [x] **Step 5 - Verify** - run the Verify command. *Done when:*
  `npm --prefix web run verify && cd api && python -m pytest` passes and
  `invariants-review` finds no gray-color, rank or sort change.

## Files / areas

- API: `api/app/schemas/props.py`, `api/app/routers/props.py` (`_enrich`),
  `api/app/schemas/tennis.py`, `api/app/routers/tennis.py` (`_to_schema`),
  `api/tests/test_props_router_best_of.py`, a `MatchPrediction` test.
- Web: `web/src/types/tennis.ts`, `web/src/utils/tennisPropBoard.ts` and its
  test, `web/src/components/tennis/TennisPropBoardControls.tsx`,
  `web/src/pages/TennisPropBoardPage.tsx`, `tennis-prop-board-filters.css`.

## Data / contracts

- **Load-bearing:** `PropLine.bestOf: number | null` (null means the prop is
  not linked to a match, never "assume 3") and `MatchPrediction.bestOf: number`.
  Both additive and optional on the web, so an older API still renders.
  The prediction's value is `infer_best_of(tour, tournament, round, best_of)`
  from `predictor.py` (the same format the model already uses), so a match the
  feed left blank still gets a format; the prop line's value is the stored
  `COALESCE(relinked.best_of, m.best_of)` and wins when present.
- **Load-bearing:** URL params `surface` (`hard|clay|grass`), `bo` (`3|5`),
  `tour` (`atp|wta|challenger|wta_125`), `line` (`standard|demon|goblin`);
  absent means the default. 64b adds `out`, 64c adds `goalie`, same rules.
- `best_of` is not added to `prop_projection_snapshots`; `prop_snapshots.py`
  builds its rows field by field, so snapshots and adoption are unchanged.

## Testing

- Logic with tests: Steps 1, 2 and 3 (listed in their done-whens and in the
  cross-sport table). Test files use fixed timestamps, per `format.test.ts`.
- No component tests (project standard): Step 4 is checked in the browser on a
  live board, including 375px width.
- Final gate: the Verify command in `AGENTS.md`.

## Notes for the AI

- 31c (2026-09-28) deliberately dropped a Standard/Goblin/Demon filter because
  it was "new behavior". The owner chose to add it now (competitor review,
  2026-11-11); the guard that keeps goblins out of the rated list stays.
- Goblins are hidden today for a reason (19c Step 8b: payout-shaped lines that
  look like edges). Default stays hidden; Goblin shows them only in the
  review bucket.
- Sibling worktrees are editing the prop boards in parallel (item 59 record
  strip, prop reasons, projection history). Keep edits to the files above and
  expect a rebase on `TennisPropBoardPage.tsx`.
- `project-overview.md` was not regenerated for item 64 (sibling sessions are
  adding items 59+ at the same time); regenerate with `/overview` once they
  merge.
- No em dashes; gray means reference; TanStack Query hooks only (no new hook
  is needed in 64a).
