# Feature: Record strip on the prop boards

**From build-plan:** feature 59
**Status:** complete (2026-11-11)
**Branch:** `feature/record-strip` (this worktree, `.claude/worktrees/record-strip-96e87d`)

## Goal

Put each board's graded record where the decisions are made. A one-line strip
under the page head of the tennis, NFL, NBA and NHL prop boards states which
model version the board serves, how its graded picks have done (W-L and hit
rate against the break-even they must beat), and what has been dropped or
retired, with a link to the full Model page. Idea from baselineev.com, which
shows its auto-graded record at the top and keeps retired markets visible
rather than hiding them. Display only: nothing on the board changes but the
strip.

## In scope

- One pure helper, `web/src/utils/boardRecord.ts`, that turns an existing
  ranking or tier response into a `BoardRecord` (contract below), tested.
- One shared component, `web/src/components/shared/BoardRecordStrip.tsx`
  (plus a small CSS file), rendered between the `PageHead` (or tennis's
  `PropBoardHead`) and the rest of each board.
- The strip on all four boards, each fed by a hook that already exists and the
  same query key its Model page uses, so a visit to one warms the other.
- Quiet states: loading, unavailable (any error, including a production 503
  for a missing snapshot), and "no graded picks yet".

## Out of scope

- **CLV on the strip.** None of the four prop models has a closing-line
  measure: PrizePicks posts no closing price, so `/nfl/model/game-line-clv`
  grades NFL spreads and totals and the tennis `clv` rows in
  `/tennis/model/predictions` grade the match moneyline ensemble. Both are
  other models. Showing either on a prop board would read as the props'
  CLV. See open question 1.
- **Tennis props-v3 W-L.** The 48e forward check (`tennis-props-check-v1`) is
  a CLI that has not been run on real data and has no endpoint. The tennis
  strip names `props-v3` and reads "Forward check not run yet"; serving 48e's
  result is a later item (open question 2).
- NFL's other ranking versions (`nfl-targets-v1`, `nfl-volume-v1`). The NFL
  board serves v4, so the strip reads `NFL_V4_RANKING_MODEL` only, the way
  `summaryCounts` already does.
- Any new endpoint, schema, migration, snapshot writer or cache change.
- Any change to ranks, sorts, edges, P(over), versions, signal colors, the
  Model pages or the home record cards.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Ranking helper** - `boardRecord.ts` exports
  `rankingBoardRecord(ranking: PropRankingRecord<string | null> | undefined, status)`
  returning the `BoardRecord` contract. Live slices are `adopt` and
  `insufficient`; dropped slices are `reject`. W-L sums `hits` and
  `n - hits`; the hit rate is `hits / n`; the baseline is the pick-weighted
  mean of each slice's `breakEven` (so a goblin-heavy pool is not judged
  against the standard break-even). Zero picks gives `graded: null`. Tests in
  `boardRecord.test.ts` cover: no data (loading and error), zero frozen rows,
  zero picks with accruing slices, a mixed pool with the weighted baseline
  checked by hand, a pool with one rejected slice kept out of the live W-L
  and counted under dropped, and every slice rejected. *Done when:*
  `npm run test` passes with the new file and no page imports it yet.
- [x] **Step 2 - Strip component on the NBA board** - `BoardRecordStrip`
  renders one line: the version, `W-L`, hit rate vs baseline (both as
  percentages to one decimal), picks graded and a "Model page" link; a second
  muted segment lists dropped and retired counts with their own W-L. Always
  the neutral (gray) text color; no green or red, whatever the numbers say.
  Loading reads "Loading record"; an error reads "Record unavailable"; no
  graded picks reads "No graded picks yet". The NFL v4 version string is
  long (`opponent-dvp-tg-blend-usage-snap-v4`), so the version truncates with
  an ellipsis and carries the full string in `title`. `NbaPropBoardPage` renders it under
  `PageHead` from `useNbaModelRanking()`; the board's own loading and error
  paths never wait on it. *Done when:* `/nba/props` shows the strip with the
  same version and pick count `/nba/model` shows, the board still renders with
  the ranking request blocked in devtools, and the strip fits one or two lines
  at 375px with no horizontal scroll.
- [x] **Step 3 - NHL board** - `NhlPropBoardPage` renders the strip from
  `useNhlModelRanking()`. Before wiring it, time a cold
  `GET /nhl/model/ranking` locally and note the API process memory before and
  after; if it is materially heavier than the cached NBA read, stop and ask
  (see Notes). *Done when:* `/nhl/props` shows the strip matching `/nhl/model`
  (built 2026-11-11: 297 graded picks, 188-109, all 4 slices accruing; a cold `/nhl/model/ranking` build took about 1.7 s for 1.3 KB, so no snapshot needed).
- [x] **Step 4 - NFL board** - `NflPropBoardPage` renders the strip from
  `useNflModelRanking(activeSeason)` (v4, the default version), keyed by the
  board's active season, not its week. *Done when:* `/nfl/props` shows the
  v4 version and the same pick count and adopted count `/nfl/model` shows for
  that season, and switching week does not refetch the ranking.
- [x] **Step 5 - Tennis helper and board** - add
  `tennisBoardRecord(tiers: ModelPropTiersResponse | undefined, status)` to
  `boardRecord.ts`: the live line names `props-v3` (the current
  `PROJECTION_VERSION` in `api/app/services/tennis/prop_snapshots.py`; no
  tennis props response carries it, so it is one exported web constant,
  `TENNIS_PROP_VERSION`, whose comment names that file) with
  "Forward check not run yet"; the retired segment sums the LOCK, STRONG and
  LEAN rows of `/tennis/model/prop-tiers` as "Retired: tiers (props-v2)" with
  `hits`, `decided - hits` and the response's single `breakEven`. Tests cover
  no data, all tiers empty, and summed tiers checked by hand.
  `TennisPropBoardPage` renders the strip from `useModelPropTiers()` under
  `PropBoardHead`. *Done when:* `npm run test` passes and `/tennis/props`
  shows `props-v3`, the not-run note and the retired tier W-L matching the
  `/tennis/model/prop-tiers` (built 2026-11-11: 331-320 over 651 decided; `/tennis/model` now shows only the tier verdicts, not the counts).
- [x] **Step 6 - Verify and guide** - run the Verify command; capture the four
  boards at desktop and 375px; update the employer interview guide if present
  (the record now sits on the boards). *Done when:* Verify passes and the four
  captures show the strip gray on every board.

## Files / areas

- New: `web/src/utils/boardRecord.ts`, `web/src/utils/boardRecord.test.ts`,
  `web/src/components/shared/BoardRecordStrip.tsx`,
  `web/src/components/shared/board-record-strip.css`
- Changed: `web/src/pages/NbaPropBoardPage.tsx`, `NhlPropBoardPage.tsx`,
  `NflPropBoardPage.tsx`, `TennisPropBoardPage.tsx`
- Reused, unchanged:
  - Endpoints: `GET /nba/model/ranking`, `GET /nhl/model/ranking`,
    `GET /nfl/model/ranking?season=`, `GET /tennis/model/prop-tiers`
  - Hooks: `useNbaModelRanking` (`hooks/useNba.ts`), `useNhlModelRanking`
    (`hooks/useNhl.ts`), `useNflModelRanking` (`hooks/useNflModelTrackRecord.ts`),
    `useModelPropTiers` (`hooks/useModelTrackRecord.ts`)
  - Types and utils: `PropRankingRecord` / `PropRankingSlice`
    (`types/propRanking.ts`), `ModelPropTiersResponse` (`types/tennis.ts`),
    `NFL_V4_RANKING_MODEL` (`utils/nflTrackRecord.ts`), the `views.model`
    paths in `utils/sportNav.ts` for the link, `HomeStatus`
    (`utils/home.ts`) for the status argument, as `homeRecords.ts` does
- Not used, and why: `trackRecord.ts` `signalClass` (the strip carries no
  signal color), `ModelClv.tsx` and `useNflModelClv` (CLV is out of scope)

## Data / contracts

Web only; no API shape changes. `BoardRecord` is new and **load-bearing** if
a later item adds prop CLV or the tennis 48e record, so lock it here:

```ts
export interface BoardRecordTally {
  wins: number
  losses: number
  hitRate: number    // wins / (wins + losses)
  baseline: number   // pick-weighted break-even
}

export interface BoardRecordSegment {
  kind: 'dropped' | 'retired'
  label: string                  // e.g. "2 slices dropped", "Retired: tiers (props-v2)"
  tally: BoardRecordTally | null // null when it has no decided picks
}

export interface BoardRecord {
  status: HomeStatus             // 'loading' | 'error' | 'ready'
  version: string | null         // null until loaded
  graded: BoardRecordTally | null
  note: string | null            // "No graded picks yet", "Forward check not run yet"
  liveSlices: number
  adoptedSlices: number
  setAside: BoardRecordSegment[] // dropped and retired, never folded into `graded`
  modelPath: string              // the sport's `views.model` from `utils/sportNav.ts`
}
```

## Testing

- Test gate is on. Step 1 and Step 5 add pure logic and ship
  `boardRecord.test.ts` (Vitest), with fixed fixtures, no clock.
- The component and page wiring are UI: verified by running the app against
  the local API and comparing each strip with its Model page, plus the 375px
  captures. No component tests, per `coding-standards.md`.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`
  (API tests run only as a regression check; no API file changes).

## Notes for the AI

- **Gray rule.** The strip is reference on every board, including any future
  adopted slice: it never takes `signal` or `signalClass`, and it is never
  green or red. The Model page stays the one place that colors a record.
  Nothing on the board (rank, sort, edge color) reads `BoardRecord`.
- **Render memory.** No new endpoint and no live build added to the request
  path. NFL and NBA ranking are served from `report_snapshots` in production
  (503 when missing, shown as "Record unavailable"). NHL ranking and tennis
  prop tiers are live builds behind 15-minute `TimedSingleFlight` caches that
  their Model pages already trigger; the strip makes the board a second
  caller of the same cached entry, not a new build. Step 3 measures the NHL
  cold read before relying on that. If it is heavy, the fix is an NHL
  ranking snapshot on the NBA pattern, which is its own item, not this one.
- **Never block the board.** Each strip query is independent of the board's
  queries; the board's `LoadingState` and `ErrorState` paths do not include
  it, and the strip has no retry button.
- **Same query keys as the Model pages.** Use the existing hooks unchanged so
  the cache is shared; do not add a lighter "summary" endpoint.
- **Pushes and exclusions** are already out of `n` and `hits` in the ranking
  record (`excluded` carries them), and out of `decided` in the tier record,
  so W-L needs no push handling.
- **Retired vs dropped.** "Dropped" means a slice the shared rule rejected for
  this version (a reject is final). "Retired" means a whole record the
  product stopped serving, today only tennis's props-v2 tiers (48f). Both
  stay visible on their own segment and never join the live W-L.
- **Tennis version drift.** `TENNIS_PROP_VERSION` duplicates a backend
  constant. If the served tennis projection version changes, this constant
  changes in the same diff; the 48g adopted pick's `projectionVersion` is the
  only served copy today, and only on adopted lines.
- Boards live at `/<sport>/props`; `/<sport>/board` is a legacy redirect.
- No em dashes in UI copy, comments or the commit message. Times are not
  shown. Follow `page-head-style`: the strip is data, no eyebrow or filler.

## Open questions for review

1. **CLV.** *Decided 2026-11-11 (owner): omit.* No prop model has a CLV
   measure, and another model's CLV (NFL game lines, tennis match moneyline)
   does not belong on a prop board. Revisit only if a prop CLV measure is
   built.
2. **Tennis props-v3 record.** Should a follow-up item serve 48e's forward
   check (after its first approved real run) through a snapshot so the tennis
   strip can show a live W-L? Out of scope here either way.

## Outcome

Completed 2026-11-11 on `feature/record-strip`. A gray record strip sits under
the page head of all four prop boards, built from `boardRecord.ts` (10 Vitest
tests) and the shared `BoardRecordStrip`, reading only the existing ranking and
tier hooks. Values on the day: NBA `nba-reference-v1` 501-377 (57.1% vs 56.8%),
NHL `nhl-reference-v1` 188-109 (63.3% vs 59.8%), NFL v4 119-97 (55.1% vs 59.2%)
with 2 slices dropped at 339-369, tennis `props-v3` with its forward check not
run and the retired props-v2 tiers at 331-320. Each was checked by hand against
its endpoint and Model page. A cold `/nhl/model/ranking` build took about 1.7 s
for 1.3 KB. Verify passed (web 1562 tests and build, API 6090). Not deployed.

Left open: the board-without-ranking path was not exercised live; the NBA
legend's "strip above" wording now sits under two strips; the strip counts
"0 of 2 live slices" on NFL where `/nfl/model` says "0 of 4";
`TENNIS_PROP_VERSION` mirrors a backend constant.
