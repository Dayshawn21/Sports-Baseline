# Feature: NFL model track record page

**From build-plan:** feature 33d (parent: 33. NFL redesign and detail pages)
**Status:** complete (2026-09-30)
**Branch:** `feature/nfl-model-page`

## Goal

Give the NFL models' graded record its own page at `/nfl/model`, the NFL
counterpart of 32b's `/tennis/model`. Today the record lives in four CLI
reports that only print text, three of them on the Tuesday `nfl-ingest.yml`
Summary page. This feature serves the same numbers as read-only endpoints and
lays them out after `prototypes/nfl-model.html`:

- **27j forward ranking check:** the four payout slices, progress toward
  their fixed verdict sample, and the verdict that decides 27h
- **27a PrizePicks line grading:** the model's hit rate on standard lines,
  overall, by market and by edge bucket, against the 57.7% break-even
- **28 game-line CLV:** spread and total, progress toward 150 picks and the
  verdict
- **27g P(over) calibration:** the 2025 fit's display verdict per market, and
  how served P(over) has held up on 2026 lines

It is display only: no projection, edge, rank, pick or P(over) changes, and no
rule is re-read or re-fixed. It is the last item-33 sub-feature.

## Design reference

- `prototypes/nfl-model.html` - header with the view switch, summary strip,
  slice cards, the two 27a cards, the two CLV cards with the rule box, the 27g
  table.
- `prototypes/theme.css` is already ported into `web/src/index.css` (31a), so
  there is nothing to port. `web/src/pages/tennis-model.css` and
  `web/src/components/tennis/model/` (32b) are the patterns for this page:
  reuse `ModelSection` rather than copy it.
- **Where the mockup and this spec differ, the spec wins:**
  - **No season select.** Only 2026 has forward data. The page grades the
    season `/nfl/current-week` returns; the endpoints take `?season=`.
  - **Three edge buckets, not four:** edge < 5%, 5-15%, >= 15%, as 27a's
    `BUCKETS` defines them.
  - **Slice error bars follow the rule's own math.** 27j dedupes goblin and
    demon ladders into one pick per bet, so every slice shows its binomial
    SE. The mockup's "goblin and demon carry no error bar" note came from
    26b's undeduped lines and is dropped. A unanimous rate (0% or 100%) or
    n < 2 shows no SE (32b's deviation).
  - **Summary strip:** "Prop slices adopted" (n of 4), "Game-line verdicts"
    (decided of 2, with the pass count), "Last settled week" (the highest
    fully played week 27j counts), and the projection version.
  - **The 27a headline is "all calls", not a fixed 48.1% on 750.** Numbers
    come from live data; the mockup's figures are placeholders (today it reads
    51.0% +/- 1.3 on 1,430 calls).
  - **The 27g section adds the forward read** (served P(over) against settled
    2026 lines, by odds type, with five reliability bins) under the fit table.
    Both are gray.
  - **No text below 11px** anywhere on the page, including tags and table
    cells (item 33 rule).

## In scope

- **Backend**
  - `app/core/track_record.py` - one shared pure helper, `verdict_signal`,
    and its docstring widened from tennis to both sports.
  - `app/core/nfl_over_probability_fit_report.py` (new, frozen constants) -
    the 27g fit's per-market display table, transcribed from the 27g archive
    and pinned by tests to the generated fit module.
  - `app/services/nfl/track_record.py` (new) - the shared loaders the CLIs
    and the page both use, pure page builders, and cached getters.
  - Four read-only routes under `/nfl/model/`.
  - The 27a, 27j and 28 CLIs call the shared loaders; their printed output is
    unchanged.
- **Web**
  - Types, API functions and hooks for the four routes.
  - Pure helpers in `src/utils/nflTrackRecord.ts`.
  - A **Model** view in the NFL `SportViewSwitch` (`/nfl/model`).
  - `NflModelPage` with the sections above, each with its own loading, error
    and empty state, stacking on mobile.

## Out of scope

- **Any change to a projection, edge, rank, pick, P(over) or verdict rule.**
  A slice reading `adopt` is shown, never acted on; acting on it is 27h.
- **Re-running the 27g fit.** It replays 2025 in about 15 minutes and would be
  a seventh read of that holdout. The page shows the fit that produced the
  served quantiles, as recorded at 27g Step 4.
- **27a's blind over/under table** (every settled line by market and odds
  type) and 27a's coverage caveats beyond a one-line count. They stay in the
  CLI.
- **The 25b prop-market holdout report** (sportsbook anytime TD). It is on the
  Summary page but not in this item's build-plan line.
- **Season or model-version pickers**, links from the page into games or
  players, a scheduled grading job, and storing grading results.
- **Fixing `TimedSingleFlight`'s failure logging** (it caches a failure and
  logs it as a "Live odds lookup"; 32b's known follow-up).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at
   the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Shared signal helper and the frozen 27g fit table.**
  - In `app/core/track_record.py`, add
    `verdict_signal(decided: bool, value, standard_error, baseline) -> Signal`:
    `"neutral"` while not decided, otherwise `rate_signal(value, se,
    baseline)`. Widen the module docstring to say it serves both sports.
  - Add `app/core/nfl_over_probability_fit_report.py`: `FIT_SEASON`,
    `FIT_PROJECTION_MODEL_VERSION`, and one frozen `FitMarketRow` per market
    (cases, pairs, ECE, worst gap, Brier, normal Brier, verdict, and the
    at-projection predicted and observed rates), copied from the 27g archive's
    Step 4 tables. The module docstring names the archive as its source.

  *Done when:*
  - pytest covers `verdict_signal`: undecided stays neutral even far past
    2 SE; decided goes positive, negative and neutral at the 2 SE boundary;
    a None SE is neutral
  - pinning tests assert that the report's `show` markets equal
    `nfl_over_probability_fit.SHOWN_MARKETS`, its version and season equal the
    generated module's, and every row's verdict agrees with the 27g rule
    constants (`MIN_CASES`, `MAX_ECE`, `MAX_BIN_GAP`, Brier vs normal)
  - the existing `test_track_record_core.py` still passes

- [x] **Step 2 - Shared loaders; CLIs unchanged.** In
  `app/services/nfl/track_record.py`, move each CLI's database loading out of
  its `_main` into an async loader both use:
  - `load_line_grading(db, season) -> LineGradingInputs` (results, edges,
    P(overs), moneyline timing): 27a's `build_slate` replay loop, unchanged
  - `load_ranking_calls(db, season) -> RankingInputs` (calls, exclusions,
    frozen-row count, coverage, finished weeks): 27j's loop
  - `load_clv_grades(db, season) -> list[ClvMarketGrade]`: 28's
    `game_models` plus `grade_market` for spread and total

  The three `_main`s shrink to "load, then print `report(...)`".

  *Done when:*
  - each CLI's stdout, captured on `master` just before the change and again
    after it from the same database state, is byte-identical (a diff of the
    two captures is in the review)
  - the existing `test_nfl_prizepicks_line_report.py`,
    `test_nfl_game_line_clv.py` and `test_nfl_ranking_check.py` pass

- [x] **Step 3 - Ranking and CLV endpoints.** Add the pure
  `build_ranking_record(inputs, model_version, over_probability_version)` and
  `build_clv_record(grades)`, their cached getters, the schemas, and
  `GET /nfl/model/ranking` and `GET /nfl/model/game-line-clv`.
  - Slices come from `slice_results`, unchanged. The rule's `insufficient`
    is passed through; the web labels it Accruing.
  - Each CLV market carries all, weeks 1-4 and weeks 5+ from `summarize`, and
    the verdict from `verdict`. While accruing, the headline summary is every
    pick; once decided it is the verdict sample.
  - Signals use `verdict_signal`: slices against their break-even, CLV
    against 0.

  *Done when:*
  - pytest covers, on synthetic inputs: an accruing slice staying neutral
    past 2 SE, a decided slice colored, SE dropped for a unanimous slice,
    `last_settled_week` as the highest finished week (null with none), a CLV
    market switching its headline to the verdict sample once decided
  - one route test per endpoint with the service stubbed, including a 503
    when the getter returns None
  - a curl for 2026 matches today's CLI output (slices 30 / 96 / 5 / 70
    picks, funnel 5,563 calls; spread +0.42 on 19 picks, total -0.17 on 18),
    re-read from the same database state

- [x] **Step 4 - Prop-lines endpoint.** Add the pure
  `build_line_record(inputs)`, its cached getter, the schema and
  `GET /nfl/model/prop-lines`.
  - Calls are `one_call_per_player_game` graded by `model_hits`: all, the
    three edge buckets, each market with at least one call, and each week.
    `rate_signal` against the standard break-even.
  - The forward P(over) read is `over_probability_reads` per odds type plus
    the "all" reliability bins. It carries no signal.
  - Cache for 15 minutes like the other sections. The load replays
    `build_slate` for every week (about 23 s in-process today), so only the
    first visit in a window pays it. A longer TTL was rejected because
    `TimedSingleFlight` caches a failure for the whole window.

  *Done when:*
  - pytest covers: a market with zero calls omitted, bucket order fixed, a
    negative signal on a synthetic market far below 57.7%, P(over) rows
    carrying no signal
  - a route test with the service stubbed
  - a curl matches the CLI's "all", bucket and per-market rows, and the
    first uncached and cached request times are noted in the review

- [x] **Step 5 - Fit endpoint.** `GET /nfl/model/over-probability-fit` serves
  Step 1's frozen table plus the rule constants, and `served`: true only while
  `FIT_PROJECTION_MODEL_VERSION` equals `NFL_PROJECTION_MODEL_VERSION` (the
  same gate the slate uses). No database, no cache.

  *Done when:* a route test covers `served` both ways (version patched), and
  a curl returns eight markets with receiving and rushing yards shown.

- [x] **Step 6 - Web data layer.**
  - Types in `src/types/nfl.ts`; `fetchNflModelRanking`,
    `fetchNflModelPropLines`, `fetchNflModelClv` and `fetchNflModelFit` in
    `src/api/nfl.ts`. `fetchNflModelPropLines` passes a 90 s request timeout,
    because the shared client's 30 s would cut off its cold load.
  - Hooks in `src/hooks/useNflModelTrackRecord.ts`, keyed
    `['nfl', 'model', '<section>', { season }]`, enabled only with a season,
    `staleTime` 15 minutes.
  - Pure `src/utils/nflTrackRecord.ts`:
    - `sliceLabel(oddsType, side)` ("Standard over")
    - `verdictLabel(verdict)`: `insufficient` / `accruing` read Accruing
    - `sliceProgress(n, weeks, minPicks, minWeeks)`: the smaller of the two
      fractions (each through 32b's `sampleProgress`), so a slice with 200
      picks in one week is not shown full
    - `summaryCounts(ranking, clv)` for the strip, tolerating either missing
    - `signedPoints(value)` ("+0.42", a dash for null)

  Reuse 32b's `signalClass`, `seMultiple` and `sampleProgress` from
  `src/utils/trackRecord.ts` rather than copy them.

  *Done when:* Vitest covers every new function, including null inputs and the
  two-fraction progress case, and `npm run build` passes.

- [x] **Step 7 - Route, Model view, page shell and summary strip.**
  - Add `model: '/nfl/model'` to NFL's views in `sportNav.ts` and update its
    comment; the route in `App.tsx`.
  - Move `ModelSection` from `components/tennis/model/` to
    `components/shared/` with a sport-neutral empty class, and point the
    tennis sections at it (no visual change on `/tennis/model`).
  - `NflModelPage` with the eyebrow, title, subtitle, view switch, the
    summary strip, and the section headings; `nfl-model.css`.
  - The season comes from `useNflCurrentWeek`; without one, the page shows
    an empty state instead of calling the endpoints.

  *Done when:*
  - `sportNav.test.ts` covers `/nfl/model` (nav key NFL, view model) and
    tennis unchanged
  - `/tennis/model` still renders its loading and loaded states after the
    `ModelSection` move (a screenshot)
  - from `/nfl` at 1440px the Model view lands on the page and a reload keeps
    it, with a screenshot
  - `npm run build` and `npm run test` pass

- [x] **Step 8 - Slice cards.** Four 27j cards: label, verdict tag, progress
  bar, picks of 200, weeks of 4+, hit rate with SE, break-even; a coverage
  and funnel line under them; the rule note. Gray unless the slice's signal
  says otherwise.

  *Done when:* a screenshot at 1440px; the cards match the Step 3 curl; with
  the API stopped the section shows `ErrorState` and the rest of the page
  still renders.

- [x] **Step 9 - Line grading cards.** The 27a card (headline hit rate, SE,
  call count, break-even, per-market meter rows) and the edge-bucket card,
  using the mockup's meter with a break-even mark. The "replays today's code,
  not a frozen record" note stays.

  *Done when:* screenshots at 1440px; a row's rate and color match the Step 4
  curl; the section's loading state shows during the cold load.

- [x] **Step 10 - CLV cards.** Spread and total cards: mean CLV with SE and
  picks, progress toward 150, toward / away / flat, W-L-P vs entry, median
  entry lead time, weeks 1-4 against 5+; then the pre-registered rule box.

  *Done when:* screenshots at 1440px; the numbers match the Step 3 curl; a
  market with no picks shows "No picks yet".

- [x] **Step 11 - 27g section and mobile pass.** The fit table (market, shown
  or hidden, cases, ECE, worst gap, Brier against normal; hidden rows dim),
  the at-projection line, the rule note, then the forward read by odds type
  and its reliability bins. A "not served" note when `served` is false. The
  whole page stacks at the `useIsMobile` breakpoint.

  *Done when:*
  - screenshots at 1440px and 390px, no horizontal page scroll at 390px (a
    table may scroll inside its card)
  - no rendered text below 11px (a computed-style sweep in the browser)
  - `npm run build`, `npm run test` and `pytest` all pass

## Files / areas

- **API**
  - `api/app/core/track_record.py` - `verdict_signal`
  - `api/app/core/nfl_over_probability_fit_report.py` (new)
  - `api/app/services/nfl/track_record.py` (new) - loaders, builders, cached
    getters
  - `api/app/backtest/nfl_prizepicks_lines.py`, `nfl_ranking_check.py`,
    `nfl_game_line_clv.py` - `_main` calls the shared loaders
  - `api/app/schemas/nfl.py`, `api/app/routers/nfl.py` - four routes
  - `api/tests/test_nfl_track_record_service.py`,
    `test_nfl_track_record_routes.py`,
    `test_nfl_over_probability_fit_report.py` (new);
    `test_track_record_core.py` (extended)
- **Web**
  - `web/src/App.tsx`, `web/src/utils/sportNav.ts` and `sportNav.test.ts`
  - `web/src/components/shared/ModelSection.tsx` (moved from
    `components/tennis/model/`), and the tennis sections' imports
  - `web/src/pages/NflModelPage.tsx`, `web/src/pages/nfl-model.css` (new)
  - `web/src/components/nfl/model/` (new) - `NflModelSummary`,
    `NflRankingSlices`, `NflLineGrading`, `NflGameLineClv`,
    `NflOverProbabilityFit`
  - `web/src/api/nfl.ts`, `web/src/hooks/useNflModelTrackRecord.ts` (new),
    `web/src/types/nfl.ts`
  - `web/src/utils/nflTrackRecord.ts` and `nflTrackRecord.test.ts` (new)

## Data / contracts

No schema change and no migration. Every endpoint is a read-only GET, open like
the other NFL GETs: it spends no quota and mutates nothing. Each returns 503
when its cached load failed.

**Load-bearing:** the route `/nfl/model` and these four responses. 27h reads
the slice verdict from `/nfl/model/ranking`, and a later bettable game-line tag
reads the CLV verdict from `/nfl/model/game-line-clv`, rather than adding
endpoints.

```text
camelCase over the wire. Signal = "positive" | "neutral" | "negative"
Every section: graded_at: datetime; the three live ones also season: int

GET /nfl/model/ranking?season=                      # 27j; cached 15 min per season
  model_version: str, over_probability_version: str
  rule: { min_picks: 200, min_weeks: 4, min_pick_margin: 0.03 }
  finished_weeks: [int], last_settled_week: int | null
  frozen_rows: int, excluded: { <reason>: int }
  coverage: [{ week: int, lines: int, frozen: int }]
  funnel: { calls, with_p_over, picks, bets }
  slices: [{ odds_type: "standard" | "goblin" | "demon", side: "over" | "under",
             verdict: "insufficient" | "adopt" | "reject",
             n, weeks, hits: int,                   # the fixed sample once decided
             hit_rate: float | null,
             standard_error: float | null,          # null when n < 2 or unanimous
             break_even: float, signal: Signal }]   # neutral while insufficient

GET /nfl/model/prop-lines?season=                   # 27a + 27g forward; cached 15 min per season
  model_version: str, break_even: float             # standard, 57.7%
  coverage: { loaded, settled, void_dnp, unsettleable_segment, week_not_loaded }
  calls:   HitRow                                   # one per player-game and market
  by_edge: [HitRow & { bucket: "small" | "medium" | "large", label: str }]
  by_market: [HitRow & { market: str }]             # markets with calls only
  by_week:   [HitRow & { week: int }]
    HitRow = { calls, hits, pushes: int, hit_rate: float | null,
               standard_error: float | null, signal: Signal }
  over_probability: [{ odds_type: "standard" | "goblin" | "demon" | "all",
                       scored, unscored: int, mean_predicted, over_rate: float | null,
                       brier: float | null }]       # no signal, ever
  reliability: [{ n: int, mean_predicted: float, observed: float }]   # "all", 5 bins

GET /nfl/model/game-line-clv?season=                # 28; cached 15 min per season
  rule: { pick_threshold: 1.5, verdict_picks: 150 }
  markets: [{ market: "spread" | "total", model_version: "nfl-elo-v1" | "NFL_SCORING_V1",
              graded: int, excluded: { <reason>: int },
              median_lead_hours, min_lead_hours: float | null,
              verdict: "accruing" | "pass" | "reject", verdict_weeks: [int],
              headline: ClvRow,                     # every pick, or the verdict sample
              all, early, late: ClvRow,             # weeks 1-4 and 5+
              signal: Signal }]                     # neutral while accruing; vs 0 after
    ClvRow = { n: int, mean_clv, standard_error: float | null,
               toward, away, flat, wins, losses, pushes: int }

GET /nfl/model/over-probability-fit                 # 27g fit; static
  fit_season: 2025, projection_version: str, served: bool
  rule: { min_cases: 300, max_ece: 0.02, max_bin_gap: 0.05, min_bin_pairs: 200 }
  markets: [{ market, cases, pairs: int, ece: float, worst_gap: float | null,
              brier, normal_brier: float, verdict: "show" | "hide",
              at_projection_predicted, at_projection_observed: float }]
```

## Results

First live read, 2026-09-30, against the same database the CLIs read:

| Section | Endpoint | Matches the CLI |
|---|---|---|
| Ranking check (27j) | standard over 16/30 (53.3% +/- 9.1), standard under 50/96 (52.1% +/- 5.1), goblin over 5/5 (no error bar), demon over 33/70 (47.1% +/- 6.0); all four accruing after week 3; funnel 5,563 calls, 2,153 with P(over), 246 picks, 201 bets | yes |
| Line grading (27a) | 51.0% +/- 1.3 on 1,430 calls, **negative**; all three edge buckets (46.9%, 51.7%, 51.8%), receiving yards (46.5%) and rushing yards (47.5%) **negative**; the other six markets neutral | yes, every row |
| Game-line CLV (28) | spread +0.42 +/- 0.23 on 19 picks (6/1/12, 11-7-1), total -0.17 +/- 0.23 on 18 (3/3/12, 10-8-0); both accruing; median entry lead 78.5 h | yes |
| P(over) fit (27g) | the recorded 2025 table, 2 of 8 markets shown, `served` true | the 27g archive |
| P(over) forward read | 4,474 scored lines, predicted 37.8% against 41.9% over, Brier 0.2072 | yes |

The 27a, 27j and 28 CLIs printed byte-identical output before and after
their loaders moved into the service (72, 12 and 22 lines).

**Timing.** Ranking 5.9 s cold, CLV 0.7 s, prop lines 22.4 s alone and about
46 s when the page fires every section at once against an API with reload on;
cached requests about 0.2 s.

**Deviations from this spec, made during the build:**
- **The fit table is a frozen transcription,** confirmed by the user before
  Step 1, rather than a re-run of the fit. Its tests re-apply the real
  `display_verdict` to every row.
- **Break-even is the 27i rule's standard figure** (57.737%) on every section,
  not 27a's 2-pick Power constant (57.735%); they agree to three decimals.
- **The prop-lines loading message says "up to a minute",** not "about 20
  seconds", after the in-page cold load measured 46 s.
- **Wording:** the mockup's editorial "flat across buckets" sentence was
  dropped, as 32b dropped its CLV sentence; the pass count sits in the
  game-line chip's label ("Game-line verdicts, 0 passed").
- **Mobile:** the summary strip uses the slate's three columns, with the
  version chip spanning the row.

**Known follow-ups:**
- Warming the prop-lines cache at API startup would remove the slow first
  load. Not done; the section has its own loading state.
- `TimedSingleFlight` still caches a failure for its window and logs it as a
  "Live odds lookup" (32b's follow-up), now for the NFL sections too.
- `web/src/types/nfl.ts` opens with a comment calling the slate the web app's
  only NFL contract; it has been stale since 33a.

## Testing

The test gate is on (`pytest`, `npm run test`).

| Step | Test |
|---|---|
| 1 | pytest: `verdict_signal` branches and boundary; the fit table pinned to the generated module and the 27g rule |
| 2 | byte-identical CLI output before and after; existing CLI tests |
| 3-5 | pytest: pure builders on synthetic inputs, one route test per endpoint with the service stubbed; curls against the CLI output |
| 6 | Vitest: every `nflTrackRecord.ts` function |
| 7 | Vitest: `sportNav` |
| 7-11 | UI: build, then screenshots at 1440px and 390px against the mockup, per done-when |

Components are not unit-tested (coding standards). Run pytest as
`cd api && .venv\Scripts\python.exe -m pytest`.

## Notes for the AI

- **Layering.**
  - SQL stays in `app/repositories/nfl.py`; the loaders call its existing
    functions (`get_gradeable_prop_lines`, `get_frozen_gradeable_lines`,
    `get_finished_weeks`, `get_frozen_coverage`, `get_elo_games`,
    `get_game_line_clv_games`, and the slate readers 27a already uses).
  - Grading math is imported, never copied: `one_call_per_player_game` and
    `BUCKETS` from the 27a CLI, `game_models` and `EARLY_WEEKS` from the 28
    CLI, and the `app/core/` rule modules. Moving them out of `app/backtest/`
    is item-17 cleanup, as 32b decided.
  - The router stays thin; Pydantic lives only in `schemas/`.
- **No verdict rule changes.** `nfl_ranking_rule.py`, `nfl_ranking_check.py`
  and `nfl_game_line_clv.py` are read, never edited. 27j and 28 already
  report their slices on the Summary page, so reading them here is not a new
  look at held-out data.
- **Do not run the 27g fit CLI.** On 2026-09-30, during `/feature`, it was
  started to time it, stopped after 10 minutes, and its output was never read.
  The fit table comes from the 27g archive only.
- **Timing, first read 2026-09-30** (CLI wall time, including Python startup):
  CLV 3 s, ranking 6 s, 27a 26 s. Use `TimedSingleFlight` keyed by season, as
  32b does.
- **Green is a signal color.** It appears only on a positive signal: an
  adopted slice, a passing CLV verdict, or a 27a rate more than 2 SE above
  break-even. Red appears only on a negative signal. The 27g section,
  coverage lines and every accruing verdict stay grayscale. The page sets no
  `--nfl-green` override because its colors come from `is-positive` /
  `is-negative` classes on signals, not from NFL edges.
- **No text below 11px** (item 33 rule, and the memory note).
- **Styling.** `nfl-model.css` against `index.css` tokens; follow 32b's
  class naming. No hard-coded hex values.
- **Prototypes.** 33d is the last item-33 sub-feature, so its `/complete`
  discards `prototypes/` (as the overview states).
- **Windows.** Launch the API as in the memory note: set the selector event
  loop before uvicorn.
- No em dashes in code comments or docs.
