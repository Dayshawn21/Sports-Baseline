# Feature: Model track record page

**From build-plan:** feature 32b (parent: 32. Tennis detail pages)
**Status:** complete (2026-09-29)
**Branch:** `feature/tennis-model-page`

## Goal

Give the tennis model's graded record its own page at `/tennis/model`, built
after `prototypes/tennis-model.html`. Today the 26a, 26b and 26f grading lives
in three CLI reports that only print text. This feature serves the same numbers
as read-only endpoints and lays them out in the mockup's page:

- match-winner components against the market, with calibration
- closing-line value
- how blind PrizePicks overs settle against break-even
- hit rate by confidence tier

It is display only: no probability, edge, rank or pick changes. It also fixes
the tennis confidence-tier verdict rule, before any tier data is read, because
the build plan requires that.

## Design reference

- `prototypes/tennis-model.html` - header, four verdict cards, component table,
  calibration chart, CLV strip, PrizePicks table with range bars, tier cards.
- `prototypes/theme.css` - already ported into `web/src/index.css` in 31a, so
  there is nothing to port. 32a's `tennis-match.css` and
  `components/tennis/match/` are the patterns for class naming and cards.
- **Where the mockup and this spec differ, the spec wins:**
  - **No All/ATP/WTA toggle.** The component table shows every group the 26a
    report grades (ATP, WTA, ATP+WTA, CHALLENGER). The headline card and
    calibration use ATP+WTA. Challenger is never pooled with it.
  - **"Last graded"** is the response's `gradedAt`. It is computed on request
    and cached for 15 minutes, not a fixed Monday run.
  - **Goblin and demon lines show no error bar and are never colored.** Their
    lines stack several deep per player and stat and move together, so a
    binomial error would overstate the evidence (the 26b rule). The mockup's red
    goblin and demon rates become gray.
  - **Tier cards grade standard lines only**, under the rule below. PASS shows
    how many were snapshotted, not a hit rate.
  - **Numbers come from live data.** The mockup's figures are placeholders.

## In scope

- **Backend**
  - **`app/core/track_record.py` (pure).** The 2 SE color rules and the
    pre-registered tier verdict rule.
  - **`app/services/tennis/track_record.py`.** It loads through the existing
    repositories, aggregates into page-shaped dataclasses, and caches each
    section for 15 minutes with the existing `TimedSingleFlight`.
  - **Three read-only routes:** `GET /tennis/model/predictions`,
    `/tennis/model/prizepicks-lines` and `/tennis/model/prop-tiers`.
- **Web**
  - Types, API functions and hooks for the three routes.
  - A pure `src/utils/trackRecord.ts` for the signal classes, SE formatting,
    the verdict-card text, and the calibration chart geometry.
  - A **Model** view beside Slate and Props in the tennis `SportViewSwitch`.
  - `TennisModelPage` at `/tennis/model`, with the mockup's sections.
  - Loading, error and empty states for each section, and the stacked
    layout on mobile.

## Out of scope

- **Any change to the model, edge, rank, tiers or picks.** A tier verdict is
  shown, never acted on. Acting on one would be a new build-plan item, as 27h
  is for NFL.
- **Changing the three CLI reports.** They stay as they are, and the
  endpoints reuse their pure pieces (`settle_rows`, `grade`) and the
  `tennis_grading` core.
- **The player page (32c)** and links from the model page into matches.
- **A tour filter, date-range filter, or model-version picker.** Predictions
  grade `ensemble-v1+lgbm-v6`, as the 26a CLI does by default.
- A scheduled grading job, and storing grading results.
- Any NFL track record.

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

- [x] **Step 1 - Color rules and the pre-registered tier rule.** Add the pure
  `app/core/track_record.py`:
  - `loss_signal(mean_diff, standard_error) -> Signal`: `"positive"` only when
    `mean_diff + 2 * se < 0`, which means the candidate beats the baseline on
    log loss. Otherwise `"neutral"`. A component losing to the market is
    expected, not a bet loss, so it is never red.
  - `rate_signal(rate, standard_error, break_even) -> Signal`:
    - `"positive"` when `rate - 2 * se > break_even`
    - `"negative"` when `rate + 2 * se < break_even`
    - `"neutral"` otherwise, or when `se` is None
  - The tier rule constants (see Data / contracts) and
    `tier_verdict(picks, as_of) -> TierVerdict`. `picks` are
    `(snapshot_date, hit)` pairs, and `as_of` is passed in, never read from a
    clock.

  *Done when:*
  - unit tests cover each signal branch, including `se=None`, and exactly 2 SE
    on the boundary
  - the verdict tests cover:
    - accruing below 200
    - a pass and a reject
    - an immature day that is ignored until it is 3 days old
    - whole days taken even past 200
    - picks on later days never changing the verdict
  - a constants test pins the rule, and asserts that `TIER_RULE_VERSION`
    equals `app.services.tennis.prop_snapshots.PROJECTION_VERSION`
  - **No tier data is read in this step.** Neither the tier report nor its
    loader is run until Step 1 is approved.
- [x] **Step 2 - Predictions endpoint.** In `app/services/tennis/track_record.py`:
  - a pure `build_prediction_grading(rows, model_version)` over
    `GradedPrediction` rows
  - the cached loader `get_prediction_grading(db)`
  - the schema and `GET /tennis/model/predictions`
  - groups, common subsets, exclusions, calibration and CLV computed exactly
    as `app/backtest/tennis_predictions.py` computes them

  *Done when:*
  - pytest covers the synthetic-row aggregation: counts, a component dropped
    from the common subset, the signal on `vs_market`, and CLV away equal to
    moved minus toward
  - a route test with the service stubbed passes
  - a curl on the running API matches the CLI's ATP+WTA ensemble-minus-market
    paired difference and the "all" CLV line, from the same database state
- [x] **Step 3 - PrizePicks lines endpoint.** Add a pure
  `build_line_settlement(rows, joins)` that calls the backtest's
  `settle_rows`, plus its cached loader and
  `GET /tennis/model/prizepicks-lines`. Each row is one stat and odds type,
  with:
  - settled, over, under and push shares
  - the over rate excluding pushes
  - the standard error (standard lines only)
  - the break-even, from `leg_decimal_odds`
  - `rate_signal`

  *Done when:*
  - pytest covers push exclusion from the over rate, no SE and a neutral signal
    for goblin and demon, and a negative signal on a synthetic standard row far
    below 57.7%
  - a curl matches the CLI's standard `total_games` over-hit rate
  - the first uncached request's time is noted in the review
- [x] **Step 4 - Prop tiers endpoint.**
  - Add `snapshot_at` to `GradedPropSnapshot` and its SELECT. This is
    additive, and the 26f CLI ignores it.
  - Add a pure `build_tier_grading(rows, joins, as_of)` that calls the
    backtest's `grade` and applies Step 1's rule, plus its cached loader
    (`as_of` = today, UTC) and `GET /tennis/model/prop-tiers`.
  - LOCK, STRONG and LEAN each get their running record, progress toward the
    verdict sample, and the verdict.
  - PASS gets the snapshotted count only.
  - Goblin and demon rows are counted as excluded. The loader already
    filters to `props-v2`.

  *Done when:*
  - pytest covers:
    - standard-only filtering
    - pushes not counting toward the sample
    - grouping by snapshot day
    - the verdict signal staying neutral while the tier is accruing
  - the existing 26f repository and report tests still pass
  - a curl returns the live tiers; this is the first read of tier data
- [x] **Step 5 - Web data layer.**
  - types in `src/types/tennis.ts`
  - `fetchModelPredictions`, `fetchModelPrizePicksLines` and
    `fetchModelPropTiers` in `src/api/tennis.ts`
  - the hooks `useModelPredictions`, `useModelPrizePicksLines` and
    `useModelPropTiers`, with keys `['tennis', 'model', '<section>']` and a
    15-minute `staleTime`
  - the pure `src/utils/trackRecord.ts`:
    - `signalClass(signal)` returns `pos`, `neg` or `''`
    - `seMultiple(mean, se)` formats "0.9 SE" and returns a dash for a
      missing SE
    - `ensembleVerdictText(group)` returns "Ahead" when the ensemble's signal
      is positive, "Not ahead" otherwise, and "No data" without a group
    - `calibrationPoints(bins, box)` returns x, y and radius, scaled by `n`

  *Done when:* Vitest covers every function, including empty bins and a
  missing SE, and `npm run build` passes.
- [x] **Step 6 - Route, Model view and page shell.**
  - Add `model: '/tennis/model'` to the tennis views in `sportNav.ts`. NFL has
    no model view, so the type becomes a per-sport partial, and
    `SportViewSwitch` renders only the views that sport has.
  - Add the route, `TennisModelPage` with its header and `gradedAt`, the
    section headings, and `tennis-model.css`.

  *Done when:*
  - `sportNav.test.ts` covers `/tennis/model` (the nav key is Tennis and the
    view is model) and NFL still showing only Slate and Props
  - from the slate at 1440px, the Model view lands on the page, and a reload
    keeps it, with a screenshot
  - `npm run build` and `npm run test` pass
- [x] **Step 7 - Verdict cards and component table.**
  - Four verdict cards: ensemble vs market, CLV, standard total-games overs,
    and tier progress.
  - The component table, grouped by tour, with the market as the baseline row
    and `vs_market` as the mean and its SE multiple.
  - Each card and the table read their own hook, with their own loading, error
    and empty state.

  *Done when:*
  - the table's ATP+WTA ensemble row matches the Step 2 curl
  - a screenshot at 1440px
  - with the API stopped, each section shows `ErrorState` and the page does
    not blank
- [x] **Step 8 - Calibration chart and CLV.**
  - An inline-SVG calibration chart with an Ensemble / Market / LightGBM v6
    toggle, grayscale, and a dashed diagonal.
  - The CLV strip: moved, toward share with a toward/away split bar, and mean
    move, plus the per-group lines under it.

  *Done when:* screenshots at 1440px and 390px show both, the toggle switches
  the series, and a source with no bins shows an empty state.
- [x] **Step 9 - PrizePicks table.** The stat, line type, settled, over, under
  and push columns, plus a range cell:
  - the dot is the over rate
  - the bar is plus or minus 1 SE, on standard lines only
  - a dashed amber mark shows break-even
  - the rate is colored only by its signal

  *Done when:* screenshots show standard rows with bars and goblin and demon
  rows without them, and a row's rate and color match the Step 3 curl.
- [x] **Step 10 - Tier cards and mobile pass.**
  - LOCK, STRONG and LEAN cards show hits over decided picks, the rate plus or
    minus SE, a progress bar toward 200, and the verdict label. They are gray
    unless the verdict's signal says otherwise.
  - The PASS card shows the snapshotted count.
  - The whole page stacks at the `useIsMobile` breakpoint.

  *Done when:*
  - screenshots at 1440px and 390px, with no horizontal page scroll at 390px
  - a tier with zero picks shows "No picks yet"
  - `npm run build`, `npm run test` and `pytest` all pass

## Files / areas

- **API**
  - `api/app/core/track_record.py` (new) - signals, tier rule
  - `api/app/services/tennis/track_record.py` (new) - aggregation, cached
    loaders
  - `api/app/repositories/prop_snapshots.py` - `snapshot_at` on
    `GradedPropSnapshot` (Step 4)
  - `api/app/schemas/tennis.py` - the three response models
  - `api/app/routers/tennis.py` - the three routes
  - `api/tests/test_track_record_core.py`,
    `api/tests/test_track_record_service.py` and
    `api/tests/test_track_record_routes.py` (new)
- **Web**
  - `web/src/App.tsx` - the route
  - `web/src/utils/sportNav.ts` and `sportNav.test.ts`,
    `web/src/components/shared/SportViewSwitch.tsx` - the Model view
  - `web/src/pages/TennisModelPage.tsx` and `web/src/pages/tennis-model.css`
    (new)
  - `web/src/components/tennis/model/` (new) - `ModelVerdictCards`,
    `ModelComponentTable`, `ModelCalibrationChart`, `ModelClv`,
    `ModelPrizePicksTable` and `ModelTierCards`
  - `web/src/api/tennis.ts`, `web/src/hooks/useModelTrackRecord.ts` (new),
    `web/src/types/tennis.ts`
  - `web/src/utils/trackRecord.ts` and `trackRecord.test.ts` (new)

## Data / contracts

No schema change and no migration. Every endpoint is read-only and open like
the other tennis GETs: it spends no quota and mutates nothing.

**Load-bearing:** the route `/tennis/model` and these three responses. 32c
links here, and a later tennis tier-adoption item reads the tier verdict.

```text
camelCase over the wire. Signal = "positive" | "neutral" | "negative"

GET /tennis/model/predictions
  graded_at: datetime, model_version: str
  counts: { settled, other_versions, incomplete, graded, with_market, with_close }
  groups: [{ group: "ATP" | "WTA" | "ATP+WTA" | "CHALLENGER", n: int,
             components: [{ name: "market" | "ensemble" | "elo" | "ml",
                            log_loss: float, brier: float,
                            vs_market: { mean: float, standard_error: float | null,
                                         signal: Signal } | null }] }]   # market row: null
  calibration: [{ source: "ensemble" | "market" | "ml",                  # ATP+WTA, common subset
                  bins: [{ low, high, n, mean_predicted, actual_rate }] }]
  clv: [{ group: "all" | "ATP" | "WTA" | "ATP+WTA" | "CHALLENGER", min_gap: float,
          eligible: int, moved: int, toward: int, away: int, mean_move_toward: float }]

GET /tennis/model/prizepicks-lines
  graded_at: datetime
  excluded: { live, promo, incomplete_score, unjoined, not_settleable }
  rows: [{ stat: str, odds_type: "standard" | "goblin" | "demon", settled: int,
           over_share, under_share, push_share: float,
           over_rate: float | null,            # excludes pushes
           standard_error: float | null,       # standard only
           break_even: float | null, signal: Signal }]

GET /tennis/model/prop-tiers
  graded_at: datetime, projection_version: str
  verdict_sample: int, break_even: float
  excluded: { non_standard: int, awaiting: int }
  tiers: [{ tier: "LOCK" | "STRONG" | "LEAN", decided: int, hits: int, pushes: int,
            hit_rate: float | null, standard_error: float | null,
            verdict: "accruing" | "pass" | "reject",
            verdict_hit_rate: float | null, signal: Signal }]
  pass_snapshotted: int
```

**The pre-registered tier rule.** It is fixed in Step 1, before any tier data
is read, and pinned by a test. Tennis has had no tier rule until now; NFL's
equivalent is 27i.

| Constant | Value |
|---|---|
| `TIER_RULE_VERSION` | `props-v2`. The rule grades only this projection version, and a version bump starts a fresh sample. |
| Picks | each line's graded snapshot (the latest pre-start one, from `get_graded_prop_snapshots`), **standard lines only**, graded by the 26f `grade` (pushes excluded) |
| Tiers | LOCK, STRONG, LEAN. PASS is not a pick. |
| `TIER_MATURITY_DAYS` | 3. A snapshot day (the UTC date of `snapshot_at`) counts only once it is at least 3 days before `as_of`, because box-score stats settle after the next day's refetch (26e). |
| `TIER_VERDICT_SAMPLE` | per tier, the first whole mature snapshot days, oldest first, whose decided picks reach 200. It is every pick on those days, so it may hold slightly more than 200. Later days never change it, and a pick that settles late on an earlier mature day is not lost, because days are only counted once mature. |
| `TIER_BREAK_EVEN` | `1 / STANDARD_LEG_DECIMAL`, 57.7% |
| Pass | verdict-sample hit rate minus 2 SE > break-even |
| Reject | the sample is full and the rule does not pass. A reject is final for `props-v2`. |
| Accruing | fewer than 200 decided picks |

- **Signal:** neutral while accruing. Once the verdict is in, `rate_signal` is
  applied to the verdict sample.
- **Correlation:** picks on the same player and match are correlated, so the
  binomial SE understates the uncertainty. This is accepted and stated, as in
  NFL's 27i rule, and the 2 SE bar is held rather than loosened.

## Results

First live read, 2026-09-29, against the same database the CLIs read:

| Section | Endpoint | Matches the CLI |
|---|---|---|
| Predictions (26a) | 1,121 graded, 774 with a market price; ATP+WTA ensemble minus market +0.0060 +/- 0.0068 (neutral); CLV 193 of 347 moved prices toward the ensemble (55.6%), mean +0.30 pts over 774 | yes, every count and difference |
| PrizePicks lines (26b, 26e) | standard total games 48.4% +/- 1.6% on 1,053 lines; aces, break points won, total games, games won and tie breaks read **negative** (more than 2 SE below 57.7%); every goblin and demon row neutral | yes, every standard row and exclusion |
| Prop tiers (26f) | LOCK 8/11, STRONG 3/6, LEAN 4/8, all **accruing** with a verdict sample of 0: `props-v2` began 2026-09-27, so no snapshot day is 3 days old yet; 47 PASS snapshots, 269 goblin and demon picks excluded, 24 standard picks awaiting settlement | first read of tier data, after the rule was fixed |

First uncached requests took 2.4 s (predictions), 5.6 s (lines) and 2.2 s
(tiers); cached ones about 12 ms.

**Deviations from this spec, made during the build:**
- **A unanimous line rate gets no error bar.** A 0% or 100% over rate has a
  binomial SE of 0, which would have colored a stat with a handful of lines as
  certain. Such rows get no SE and stay neutral. The tier rule is unchanged.
- **`verdict_sample_size`** was added to each tier row for the progress bar.
- **Class names are `is-positive` / `is-negative`**, the codebase's existing
  convention, not `pos` / `neg`.
- **Wording:** the fourth card is "Confidence tiers" (it shows hit rate
  against break-even, not calibration); the CLV card and footnote say the mean
  move is over all priced matches, unmoved ones counting as 0; the mockup's
  editorial CLV sentence was dropped; the calibration toggle's selected state
  is gray, not green.
- `rateRange` and `sampleProgress` joined the Step 5 util so all page math is
  tested in one file.

**Known follow-ups:**
- `TimedSingleFlight` caches a failure for its 15-minute window and logs it as
  a "Live odds lookup". The shared cache was left unchanged.
- On phones the PrizePicks table scrolls sideways inside its card (0 px page
  overflow); hiding columns on mobile was considered and declined.

## Testing

The test gate is on (`pytest`, `npm run test`).

| Step | Test |
|---|---|
| 1 | pytest: signal branches and the boundary, verdict states, the frozen sample, pinned constants |
| 2-4 | pytest: pure aggregation on synthetic rows, one route test each with the service stubbed; a curl against the CLI output |
| 5 | Vitest: every `trackRecord.ts` function, and the `sportNav` changes |
| 6-10 | UI: build, then screenshots at 1440px and 390px against the mockup, per done-when |

Components are not unit-tested (coding standards). Run pytest as
`cd api && .venv\Scripts\python.exe -m pytest`.

## Notes for the AI

- **Layering.**
  - SQL stays in the existing repositories: `get_graded_predictions`,
    `get_settleable_prizepicks_lines`, `get_box_score_candidates` and
    `get_graded_prop_snapshots`.
  - The router stays thin, and Pydantic lives only in `schemas/`.
  - `app/core/track_record.py` stays pure.
  - The service imports `settle_rows` and `grade` from the `app/backtest/`
    modules. They are already pure and tested, and moving them is item-17
    cleanup. Do not copy them.
- **Tier data is not read before Step 1 is approved.** Do not run
  `python -m app.backtest.tennis_prop_snapshots` or the tier loader until then.
  On 2026-09-29, during `/feature`, that report was run once to time it, and
  its output was discarded unread.
- **Green is a signal color.** It appears only where a signal is positive
  under the 2 SE rules. Red appears only on a negative rate signal. Component
  rows, calibration, CLV and every accruing tier stay grayscale. Tour accents
  are not used on this page.
- **Caching.** Use `TimedSingleFlight` from
  `app/services/tennis/live_odds_cache.py` with a 15-minute TTL per section,
  so concurrent loads share one computation. On 2026-09-29 the three CLIs took
  about 2.3 s, 4.3 s and 2.0 s including Python startup.
- **Styling.** Styles go in `tennis-model.css` against `index.css` tokens. Use
  the mockup's `minmax(0, 1.3fr) minmax(0, 1fr)` grid, stacking on mobile. No
  hard-coded hex values beyond what 32a already tokenized.
- **Prototypes stay.** 31d, 31e and 32c still use `prototypes/`, so this
  feature's `/complete` does not discard it.
- **Windows.** Launch the API as in the memory note: set the selector event
  loop before uvicorn.
- No em dashes in code comments or docs.
