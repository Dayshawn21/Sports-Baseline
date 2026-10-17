# Feature: Tennis match detail page

**From build-plan:** feature 32a (parent: 32. Tennis detail pages)
**Status:** complete (2026-09-29)
**Branch:** `feature/tennis-match-page`

## Goal

Give every tennis match its own linkable page at `/tennis/match/:matchId`,
built after `prototypes/tennis-match.html`, and retire the
`PlayerComparisonModal`. The page shows the same probabilities, market and
edge the slate shows, plus the evidence the modal could not fit: how each
book's price moved, box-score form and the props on the match. Display only:
no probability, edge, rank or pick changes.

## Design reference

- `prototypes/tennis-match.html` - header, three-number hero, component
  breakdown, movement chart, recent form, and the sidebar (H2H, books now,
  serve and return, props).
- `prototypes/theme.css` - already ported into `web/src/index.css` in 31a, so
  this feature builds against the existing tokens and ports nothing.
- 31b's `web/src/components/tennis/tennis-slate.css` and 31c's prop card are
  the patterns for class naming and card styling.
- **Where the mockup and this spec differ, the spec wins:**
  - **Recent form shows the last 5 matches**, not 10: that is what
    `get_recent_completed_matches` returns today. The column the mockup calls
    Hold becomes **BP won** (`break_points_converted / break_chances_created`),
    because per-match hold is not stored.
  - **No "Track bet" button.** Recording a bet from this page is new behavior;
    it stays on the Bets page.
  - **No explanatory v6 note.** The mockup's "v6 carries most of the edge"
    sentence is editorial text the data does not produce.
  - **No flag relabeling.** Quality flags render through the existing
    `getDisplayFlags` / `getDisplayFlagLabel`, not the mockup's raw strings.
  - **The set 1 market toggle is dropped.** The chart covers moneyline and
    total games only.

## In scope

- **Backend**
  - `GET /tennis/matches/{match_id}`: match meta, both players, H2H overall
    and on the surface, the prediction, and the moneyline pick with edge and
    EV.
  - Scheduled and live matches predict through the **same batch path as
    `/predictions/today`**, so the page and the slate agree.
  - Completed matches show the **latest stored prediction generated before
    `start_utc`**, labeled "pre-match", never a fresh prediction that could
    see the result.
  - `GET /tennis/matches/{match_id}/odds-history?market=moneyline|total_games`:
    every stored `match_odds` row for the match and market, oldest first,
    capped at the start time.
- **Web**
  - A `/tennis/match/:matchId` route and a `TennisMatchPage`.
  - Sections: header, hero (ensemble, market, edge), component breakdown with
    weights and flags, movement chart, recent form, H2H, books now, serve and
    return, and props on the match.
  - Loading, error, not-found, and "no prediction" states.
  - The slate workspace's "Open match analysis" button becomes a link to the
    page.
  - `PlayerComparisonModal.tsx` is deleted, along with the slate's modal
    state.
  - Mobile: the two columns stack at the `useIsMobile` breakpoint.

## Out of scope

- The player page (32c) and model page (32b). Player names render as plain
  text here; 32c turns them into links.
- Recording a bet from the page.
- Any change to the prediction, edge, best-pick or confidence logic.
- A live-odds fallback for matches with no stored moneyline. The slate's best
  picks overlay live Odds-API.io prices when a stored price is missing
  (`_overlay_live_moneyline`); this page reads stored prices only, to keep the
  request budget untouched. Such a match shows its model probability with the
  market marked "no stored price".
- Cleaning up the unused `predict_match` in `predictor.py` or the unused
  `UnifiedMatchCard.tsx` (noted for a later `/audit`).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Shared batch prediction path** - split the body of
  `predict_today` into `predict_matches(db, registry, matches, ref_date)`;
  `predict_today` becomes `get_upcoming` plus that call, unchanged in
  behavior. Add `match_repo.get_match(db, match_id)`, any status, returning
  the existing `Match` plus the fields `Match` does not carry (`indoor`,
  `score`; `winner_id` is already on `Match`) in a small `MatchMeta` dataclass beside it; `Match`
  itself is unchanged, because `get_upcoming` and the predictor build it
  positionally. *Done when:* the existing predictor and best-picks tests pass
  unchanged, a new test shows `predict_today` and `predict_matches` on the
  same matches return equal outputs, and `/tennis/predictions/today` on the
  running API returns the same match count before and after.
- [x] **Step 2 - Match detail endpoint, upcoming matches** -
  `MatchDetailResponse` schema, and `GET /tennis/matches/{match_id}` for
  scheduled and live matches:
  - meta: status, start, tour and label, surface, indoor, tournament, round,
    best-of
  - both players: id, name, rank, hand, country, overall and surface ELO
  - H2H overall and on the surface
  - the `MatchPrediction`
  - `ml_pick` from `generate_ml_pick`
  - `prediction_source: "live"`
  Unknown id returns 404. *Done when:* pytest covers the 404 and the response
  mapping with a fake session, and a curl of a match from today's slate
  **that has a stored moneyline** returns the same `p1WinProb` and ML edge as
  `/predictions/today` and `/predictions/best-picks` for that match. A match
  priced only by the slate's live overlay is expected to differ; see Out of
  scope.
- [x] **Step 3 - Completed matches use the stored pre-match prediction** -
  repository `get_prestart_prediction(db, match_id, start_utc)` returns the
  latest `predictions` row with `generated_at < start_utc`, including weights,
  flags and model version. The endpoint maps it to the same `MatchPrediction`
  shape with `prediction_source: "stored"`, plus score and winner side.
  - No stored row gives `prediction: null` and `prediction_source: null`.
  - A completed match with no `start_utc` counts as having no pre-match row.
  - The moneyline for `ml_pick` is the one the prediction saw: the newest
    two-sided `match_odds` row fetched at or before `generated_at`, as 26a
    pairs them. It is not the close, because an edge that mixes a stored model
    number with a later price means nothing.
  *Done when:* pytest covers the stored mapping, the no-row case and the
  missing-start case, and a curl of a match completed yesterday returns
  `prediction_source: "stored"` with `generatedAt` before `startUtc`.
- [x] **Step 4 - Odds history endpoint** - repository and route for
  `GET /tennis/matches/{match_id}/odds-history`:
  - rows are book, p1 and p2 odds, line and `fetched_at`, oldest first
  - rows are filtered to `fetched_at < start_utc` when a start is known
  - unknown match returns 404, and a market outside `moneyline | total_games`
    returns 422
  *Done when:* pytest covers ordering, the start cap, 404 and 422, and a curl
  returns more than one row per book for a match fetched by several odds runs.
- [x] **Step 5 - Web data layer** - types in `src/types/tennis.ts`, the API
  functions `fetchMatchDetail` and `fetchMatchOddsHistory`, and the hooks
  `useMatchDetail` and `useMatchOddsHistory`. Query keys are
  `['tennis', 'match', matchId]` and
  `['tennis', 'match-odds', matchId, market]`, with a 5-minute staleTime.
  Add a pure `src/utils/matchOdds.ts`:
  - `buildMovementSeries(rows, side)` gives de-vigged p1 probability per book
    over time for moneyline, and the line per book for totals
  - `summarizeMove(series, modelProb)` gives the open, the latest, and the
    signed move toward the model in points
  *Done when:* Vitest covers de-vig per row, one-sided rows skipped,
  per-book grouping, a single-row book, the empty input, and toward, away
  and flat moves. `npm run build` passes.
- [x] **Step 6 - Page shell, route, header and hero** - `TennisMatchPage`
  at `/tennis/match/:matchId`:
  - the back link to the slate, the player header, the tournament context,
    and the three-number hero
  - the shared `LoadingState` and `ErrorState`, a not-found state for 404,
    and a "no pre-match prediction stored" state
  - a completed match shows the score, the winner, and a "pre-match" label
    on the hero
  - the third tile headlines the moneyline pick's **EV**, the number the
    slate colors, and shows edge beside it in gray. It is green only when
    `ml_pick` exists with positive EV, as on the slate; otherwise it is gray
  - the slate's "Open match analysis" becomes a `Link` to the page
  *Done when:* at 1440px and at 390px:
  - clicking "Open match analysis" on the slate lands on the page
  - the page shows the same win probability and edge as the slate row
  - a reload keeps it
  - `/tennis/match/999999999` shows not-found
  - screenshots are captured
- [x] **Step 7 - Component breakdown** - the ELO, ML, market and ensemble
  rows with bars, a 50% reference mark, and the weights, plus quality flags
  through `getDisplayFlags`. A Challenger or WTA 125 match shows the ML row as
  "not trained for this tour". A missing component reads "no data", never 0%.
  *Done when:* screenshots show an ATP match with all four rows and a
  Challenger match with the ML row marked, and the weights match
  `ensembleWeights` from the API.
- [x] **Step 8 - Movement chart** - an inline-SVG chart card with a
  moneyline and total-games toggle, one line per book in grayscale, and a
  dashed model line for moneyline only. The footer carries the open and latest
  price and the move toward the model.
  - Empty state when a market has no rows.
  - A single-row book renders as a dot.
  *Done when:* screenshots show a match with several odds runs, a match with
  one run, and a Challenger match with no total-games rows.
- [x] **Step 9 - Recent form** - both players' last 5 from the existing
  `useMatchRecentForm`, with W/L chips and the columns score, aces, DF and BP
  won. A missing box score shows a dash, and a player with no prior matches
  shows an empty state. *Done when:* screenshots at 1440px and 390px show a
  populated match and a player with no box scores.
- [x] **Step 10 - Sidebar** -
  - **H2H:** overall and surface
  - **books now:** the newest row per book, from the odds history
  - **serve and return:** from `last_52_w`
  - **props on this match:** from the loaded prop source, filtered by
    `matchId`, linking to `/tennis/board`
  - every card has an empty state
  *Done when:* screenshots at 1440px and 390px show every card on a
  populated match, and a match with no props and no H2H shows the empty
  states rather than a blank card.
- [x] **Step 11 - Retire the modal** - delete `PlayerComparisonModal.tsx`
  and the slate's `selectedMatch` state and `openMatch` helper. Remove any
  import left orphaned. *Done when:* `rg PlayerComparisonModal web/src`
  returns nothing, `npm run build` and `npm run test` pass, `pytest` passes,
  and the slate still selects matches and opens the page.

## Files / areas

- **API**
  - `api/app/services/tennis/predictor.py` - `predict_matches` split (Step 1)
  - `api/app/repositories/matches.py` - `get_match`, odds history
  - `api/app/repositories/predictions.py` - `get_prestart_prediction`
  - `api/app/routers/tennis.py` - the two routes
  - `api/app/schemas/tennis.py` - `MatchDetailResponse`,
    `MatchPlayerDetail`, `MatchH2H`, `MatchOddsHistoryResponse`
  - `api/tests/test_match_detail.py` and `api/tests/test_match_odds_history.py`
    (new)
- **Web**
  - `web/src/App.tsx` - the route
  - `web/src/pages/TennisMatchPage.tsx` and `web/src/pages/tennis-match.css`
    (new)
  - `web/src/components/tennis/match/` - `MatchHero`, `MatchComponents`,
    `MatchOddsChart`, `MatchRecentForm`, and the sidebar cards (new)
  - `web/src/api/tennis.ts` and `web/src/hooks/useMatchDetail.ts`,
    `useMatchOddsHistory.ts`
  - `web/src/utils/matchOdds.ts` and `matchOdds.test.ts` (new)
  - `web/src/types/tennis.ts`
  - `web/src/pages/TennisIntelligencePage.tsx` and
    `components/tennis/TennisCommandCenter.tsx` - modal removal, link
  - `web/src/components/tennis/PlayerComparisonModal.tsx` - deleted

## Data / contracts

No schema change and no migration.

**Load-bearing:** `MatchDetailResponse` and the route `/tennis/match/:matchId`.
32c links player ids from this response and links back to this route; later
match-level features extend this response instead of adding another endpoint.

```text
GET /tennis/matches/{match_id}           camelCase over the wire
MatchDetailResponse
  match_id: int
  status: "scheduled" | "live" | "completed" | str
  start_utc: datetime | null
  tour: str, tour_label: str
  surface: str | null, indoor: bool | null
  tournament: str | null, round: str | null, best_of: int
  score: str | null                  # completed only
  winner_side: "p1" | "p2" | null    # completed only
  p1, p2: MatchPlayerDetail
    player_id: int, name: str
    rank: int | null                 # from the match row
    hand: "R" | "L" | null, country: str | null
    elo: float | null, elo_surface: float | null
  h2h: MatchH2H
    p1_wins: int, p2_wins: int
    surface_p1_wins: int | null, surface_p2_wins: int | null
  prediction: MatchPrediction | null     # existing schema, unchanged
  prediction_source: "live" | "stored" | null
  prediction_generated_at: datetime | null   # stored only
  model_version: str | null                  # stored only
  ml_pick: BestPickSchema | null             # existing schema, unchanged

GET /tennis/matches/{match_id}/odds-history?market=moneyline|total_games
MatchOddsHistoryResponse
  match_id: int, market: str
  rows: [{ book: str, p1_odds: int | null, p2_odds: int | null,
           line: float | null, fetched_at: datetime }]   # oldest first
```

- The existing `/matches/{match_id}/recent-form` is reused unchanged.
- **Prediction sources:** scheduled and live matches predict live. A completed
  match reads its stored pre-start row. A cancelled or walkover match, or any
  other status, is treated like a completed one.
- **Props** come from the already cached prop-source query (PrizePicks by
  default), filtered client-side by `matchId`. They cover today's props only,
  which is what the prop board shows.

## Testing

The test gate is on (`pytest`, `npm run test`).

| Step | Test |
|---|---|
| 1 | pytest: `predict_matches` equals `predict_today` on the same fake matches |
| 2 | pytest: 404, response mapping, `ml_pick` present and absent |
| 3 | pytest: stored mapping, no stored row, no `start_utc` |
| 4 | pytest: ordering, start cap, 404, 422 on a bad market |
| 5 | Vitest: `buildMovementSeries` and `summarizeMove` (de-vig, grouping, empty, single row, move direction) |
| 6-10 | UI: build, then screenshots at 1440px and 390px against the mockup, per done-when |
| 11 | full `npm run build`, `npm run test`, `pytest` |

Components are not unit-tested (coding standards).

## Notes for the AI

- **Layering.** SQL lives in repositories. The router stays thin and delegates
  to the predictor service and `generate_ml_pick`. No I/O goes in `app/core/`,
  and no Pydantic below the router.
- **One prediction path.** The page must never compute a probability the
  slate would not. Step 1 exists so both go through `predict_matches`; do not
  call the unused `predict_match`, whose inputs differ.
- **No leakage.** A completed match never runs the live predictor, and every
  stored read is capped at `start_utc`.
- **Color rules.** Green is reserved for a positive `ml_pick` edge, the same
  rule as the slate. Component bars, the chart lines, H2H and the form tables
  stay grayscale. Tour tags keep their accents.
- **Odds.** De-vig with the existing helper in `web/src/utils/odds.ts` if it
  has one; otherwise add a pure one beside it with a test. Never
  re-implement de-vigging in a component.
- **Styling.** Styles live in `tennis-match.css` against `index.css` tokens.
  Follow the prototype layout: a `minmax(0, 1fr) 420px` grid that stacks on
  mobile. No hard-coded hex values except the three chart grays, which become
  tokens if a token does not already fit.
- **Windows.** Launch the API as in the memory note: set the selector event
  loop before uvicorn.
- No em dashes in code comments or docs.
