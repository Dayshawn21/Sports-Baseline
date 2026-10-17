# Feature: NFL over probability

**From build-plan:** feature 27g
**Status:** complete (P(over) shown for receiving and rushing yards; six markets hidden by the pre-registered rule)

## Goal

Turn each NFL prop projection into a probability that the result lands over
the line, and show it beside the edge. The probability comes from per-market
outcome distributions fitted on 2025 replay residuals. It is shown only for
markets whose held-out calibration passes a rule fixed in this spec, before
any fit is scored.

**Why:** the edge is mean minus line, and 27b found that every market leans OVER
(`share_below` 54% to 64%). Yards are right-skewed, so a projection a few yards
above a near-median line is often still more likely to land under. A calibrated
P(over) removes that mean-versus-median bias. It is also the number 27h will
rank against each payout's break-even.

**Display only.** The feature changes no edge, rank, pick, signal board, or
projection, and bumps no `NFL_PROJECTION_MODEL_VERSION`.

## In scope

- **A pure distribution module.** Each group is one market and position, as in
  27b's `REPLAY_MARKETS_BY_POSITION`. For each group it fits an empirical
  distribution of `actual / projection`, stored as 41 quantiles (every 2.5%).
  P(over line) is read from it for any projection.
- **A pure calibration module.** Synthetic lines, a reliability table, expected
  calibration error (ECE), Brier score, a normal-distribution baseline, and the
  display verdict.
- **A fit CLI,** `python -m app.backtest.nfl_over_probability_fit`:
  - replays 2025 through the 27b harness's `production` arm
  - cross-fits by week parity, so every case is scored out of fold
  - prints each market's calibration and verdict
  - with `--write`, freezes the full-season tables for passing markets into a
    generated module
- **One scored run on 2025,** with the verdicts under Results.
- **Serving.** `/nfl/slate` lines gain nullable `p_over`, `p_under`, and
  `over_probability_version`. They are filled on every full-game line (standard,
  goblin, or demon) in a passing market that has a projection and enough
  baseline games.
- **Web:**
  - the evidence panel shows P(over) and P(under) for the selected line
  - each alternative-line tag shows its P(over)
  - both are muted, never colored as a signal
- **A forward read on real lines.** `python -m app.backtest.nfl_prizepicks_lines`
  adds a P(over) reliability section by odds type for stored 2026 lines. This is
  information only.

## Out of scope

- **Ranking, picks, or break-even comparison** by P(over). That is 27h, gated on
  27a's forward sample. No P(over) is colored, sorted by, or compared to a
  payout on screen.
- **Anytime TD.** Its projection is already a probability, and its market rating
  waits on 25c.
- **Projection changes.** Any mean shift, such as a median-anchored projection,
  goes through the 27b harness as its own variant.
- **Integer lines.** They can push, and v1 does not model push mass. They get
  null P(over) and are counted in the report. PrizePicks NFL lines are almost
  all x.5.
- **Splits beyond market and position** (projection size, home or away, game
  script). The report shows calibration by projection tercile for information.
  A split is a later variant if that read fails.
- **Storing P(over) per line** (a snapshot table like tennis 26f). 27a already
  replays today's code on past weeks. Frozen snapshots are a 27h question.
- **Segments** other than full game.
- **The prop board page** (`/nfl/board`). It ranks by edge share, and adding a
  probability column there reads as a signal. Only the evidence panel changes.

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

- [x] **Step 1 - The distribution (pure).** Add `app/core/nfl_over_probability.py`
  with:
  - `QUANTILE_LEVELS`: 41 levels, 0.0 to 1.0 in 0.025 steps.
  - `ratio_quantiles(pairs: Iterable[tuple[float, float]]) -> tuple[float, ...]`:
    - takes (projection, actual) pairs and skips any projection at or below 0
    - returns the 41 quantiles of `actual / projection`
    - uses linear interpolation between order statistics
    - raises on an empty input
  - `OverProbability` (frozen dataclass): `p_over` and `p_under`, which sum to 1.
  - `over_probability(quantiles, projection, line) -> OverProbability | None`:
    - returns None for an integer line or a projection at or below 0
    - otherwise reads the ratio CDF at `line / projection`, interpolating
      linearly between quantiles
    - below the lowest quantile, P(over) is 1.0; above the highest, 0.0
    - repeated quantile values (a mass at 0 yards) take the CDF's upper step, so
      "over 0.5 yards" excludes the zero mass

  *Done when:* unit tests show:
  - a symmetric table puts P(over) at 0.5 when the line equals the projection
  - a right-skewed table (median ratio 0.85) puts P(over) below 0.5 at
    line = projection
  - P(over) falls as the line rises
  - both table ends clamp
  - a table with a 20% mass at ratio 0 gives P(over 0.5) of 0.8 or less
  - integer lines and a zero projection return None
  - `ratio_quantiles` on a known list returns the expected 0%, 50%, and 100%
    values
- [x] **Step 2 - Calibration and the display rule (pure).** Add
  `app/core/nfl_over_probability_calibration.py` with:
  - `synthetic_lines(projection) -> tuple[float, ...]`:
    - multiples 0.5, 0.75, 1.0, 1.25, and 1.5 of the projection, each snapped
      to `floor(value) + 0.5`
    - drops lines at or below 0 and duplicates
  - `CalibrationPair(predicted, over)` and `calibrate(pairs) ->
    CalibrationReport`:
    - n
    - Brier score
    - ECE over 10 equal-width predicted bins, weighted by pair count
    - per-bin rows: n, mean predicted, observed over rate
    - the worst gap among bins holding at least 200 pairs
  - `normal_over_probability(projection, sigma, line) -> float`: the baseline.
    A normal centered on the projection, with the fold's per-group residual
    standard deviation.
  - `display_verdict(cases_n, report, normal_brier) -> "show" | "hide" |
    "insufficient"`, applying the rule under Data / contracts.

  *Done when:* unit tests cover:
  - line snapping and dropping, including a projection under 1
  - ECE and Brier on a hand-computed set
  - the 200-pair minimum for the worst-gap check
  - each verdict branch at exactly n = 300, ECE = 0.02, worst gap = 0.05, and
    Brier equal to the normal's
- [x] **Step 3 - The fit CLI, cross-fitted.** Add
  `app/backtest/nfl_over_probability_fit.py` (`--season`, default 2025):
  - **Replay:** for weeks 1-18, `get_replay_rows`, then the harness's
    `replay_cases(rows, "production", season, week)`. This gives exactly the
    cases 27b scores: projection present and `edge_is_comparable`. Anytime TD is
    never among them.
  - **Cross-fit:** fit each group's quantiles on odd weeks and score even weeks,
    then the reverse, so every case has an out-of-fold P(over) at each of its
    synthetic lines. The normal baseline uses the same folds.
  - **Prints, per market** (positions pooled, which is what the verdict reads):
    - n cases and n pairs, ECE, worst gap, Brier, normal Brier, and the verdict
    - the reliability table
    - information only: calibration by position and by projection tercile, plus
      the pairs at the 1.0 multiple (line about equal to the projection), where
      the observed over rate is the OVER lean restated as a probability
  - **`--write`** writes `app/core/nfl_over_probability_fit.py`, a generated
    module with a header saying so and how to regenerate it:
    - `FIT_SEASON` and `FIT_PROJECTION_MODEL_VERSION`
    - `SHOWN_MARKETS`, the markets whose verdict is `show`
    - `QUANTILES_BY_GROUP`: `{(market, position): (41 floats)}`, fitted on all
      18 weeks, for shown markets only

  *Done when:*
  - a report test on synthetic cases checks one market row and its verdict
  - a writer test renders a two-group table and re-imports the rendered text
    (exec into a dict) to the same values
- [x] **Step 4 - The 2025 run.** Run the CLI once, then with `--write`.

  *Done when:*
  - Results holds each market's verdict table, the 1.0-multiple over rates,
    and the per-position and per-tercile reads.
  - Results records that this is the **sixth read of the 2025 replay**. No
    projection verdict is taken from it; the forward check is Step 7 and 27h.
  - The generated module is committed.
  - `pytest` passes.
  - If no market shows, record that. Steps 5 and 6 still ship: every line then
    serves null, and the panel shows nothing new.
- [x] **Step 5 - Serve on the slate.** In `app/services/nfl/slate.py` and
  `app/schemas/nfl.py`:
  - `NflSlateLineSchema` gains `p_over: float | None`, `p_under: float | None`,
    and `over_probability_version: str | None`, all defaulting to None.
  - `slate_over_probability(market, position, segment, games, projection, line)
    -> OverProbability | None`, in the core module. It returns None unless:
    - the segment is full game
    - the market is in `SHOWN_MARKETS` and the (market, position) group has a
      table
    - `games >= MIN_BASELINE_GAMES`
    - `FIT_PROJECTION_MODEL_VERSION == NFL_PROJECTION_MODEL_VERSION`, so a new
      projection never reads residuals fitted on an old one
    - `over_probability` itself returns a value

    Odds type is **not** a condition: goblin and demon lines get P(over) too.
  - `_slate_line` fills the three fields. Values are rounded to 3 places, and
    the version is `nfl-pover-v1` when filled.
  - Edge, rank, flags, and projection are untouched.

  *Done when:*
  - Unit tests show:
    - a shown-market goblin line gets P(over)
    - an anytime-TD line, a first-half line, a thin-sample line, and a
      version-mismatch line all get null
  - `/nfl/slate` JSON for 2026 weeks 2 and 3 (`build_slate`, fixed `now`) is
    byte-identical before and after once the three new keys are stripped
    (SHA-256).
  - Results records how many lines per odds type carry P(over).
- [x] **Step 6 - Evidence panel.** In `web/`:
  - `NflSlateLine` gains `pOver`, `pUnder`, and `overProbabilityVersion`
    (`number | null` and `string | null`).
  - `overProbabilityLabel(line)` in `src/utils/nflSignal.ts` returns
    `Over 44% · Under 56%`, or null.
  - The evidence panel shows it under the header. Each alternative-line tag
    appends ` · 71% over` when present.
  - Nothing is colored by it and nothing sorts by it.

  *Done when:*
  - a Vitest test covers the label, including null and rounding (0.4449 reads
    44%)
  - `npm run build` passes
  - a screenshot of `/nfl` week 3 shows the panel with a standard line's
    probabilities and alternative tags carrying theirs
- [x] **Step 7 - Forward read on 2026 lines.** In
  `app/backtest/nfl_prizepicks_lines.py`:
  - add a P(over) section, which rebuilds each settled line's P(over) through
    `build_slate` as it already does for edges
  - by odds type (standard, goblin, demon) and overall, print:
    - n
    - mean predicted P(over)
    - observed over rate with its standard error
    - Brier
    - a 5-bin reliability table
  - lines with null P(over) are counted, not scored
  - a pure helper in `app/core/nfl_line_grading.py` does the grouping

  *Done when:*
  - a grading test groups three settled lines by odds type correctly
  - the report runs for 2026, and Results records the section with the sample
    size stated plainly. It is a first read, not a verdict: 27h's
    pre-registered rule decides use.

## Files / areas

- `api/app/core/nfl_over_probability.py` (new) - quantiles, P(over), and the
  slate gate.
- `api/app/core/nfl_over_probability_calibration.py` (new) - synthetic lines,
  reliability, the verdict.
- `api/app/core/nfl_over_probability_fit.py` (new, generated by Step 4).
- `api/app/backtest/nfl_over_probability_fit.py` (new) - the fit CLI.
- `api/app/backtest/nfl_prizepicks_lines.py` - the forward section.
- `api/app/core/nfl_line_grading.py` - the grouping helper.
- `api/app/services/nfl/slate.py` and `api/app/schemas/nfl.py` - serving.
- `web/src/types/nfl.ts`, `web/src/utils/nflSignal.ts`, and
  `web/src/components/NflEvidencePanel.tsx`.
- Tests:
  - `test_nfl_over_probability.py` (new)
  - `test_nfl_over_probability_calibration.py` (new)
  - `test_nfl_over_probability_fit.py` (new)
  - `test_nfl_slate.py` or the existing slate test module
  - `test_nfl_line_grading.py`
  - `nflSignal.test.ts`

## Data / contracts

No schema change and no migration.

**API, load-bearing for 27h.** `/nfl/slate` lines gain three nullable fields,
camelCased on the wire:

| Field | Meaning |
|---|---|
| `p_over` | P(result > line), 0 to 1, 3 places |
| `p_under` | `1 - p_over`; no push mass in v1 |
| `over_probability_version` | `nfl-pover-v1` when filled, else null |

Null means not shown, for any of these reasons: market hidden by the verdict, TD
market, segment, thin sample, integer line, or a stale fit. It never means 0.5.

**Load-bearing:**
- **The fit is frozen code,** regenerated only by the CLI's `--write`, never
  hand-edited. Any bump of `NFL_PROJECTION_MODEL_VERSION` silently hides P(over)
  until the fit is regenerated on the new projection. That is deliberate:
  residuals belong to one projection.
- **`over_probability(quantiles, projection, line)` is the one function** 27h
  ranks with. It stays sport-agnostic (no NFL imports) so item 17 can move it
  beside `app/core/prop_probs.py`.
- **Fantasy residuals are PrizePicks points** against the PPR-based projection
  (27f). The fit absorbs that gap; do not correct it separately.

**The pre-registered display rule** is fixed 2026-09-26, before any fit is
scored. A market is **shown** only when all of these hold on the out-of-fold
2025 scores, positions pooled:

1. at least 300 cases
2. ECE of 0.02 or less across its synthetic-line pairs
3. no bin holding 200 or more pairs is off by more than 0.05 (mean predicted
   against observed)
4. Brier no worse than the normal baseline on the same pairs

Below 300 cases the verdict is `insufficient`, and otherwise `hide`. Each market
is scored once. A hidden market is not refitted with a different method in this
feature.

## Testing

- The test gate is on:
  - Steps 1 and 2 ship unit tests.
  - Step 3 ships report and writer tests.
  - Step 5 ships slate tests plus the stripped byte-identical check.
  - Step 6 ships a Vitest test, the build, and a screenshot.
  - Step 7 ships a grading test.
- Run with `cd api && .venv\Scripts\python.exe -m pytest`, and `cd web && npm run
  test && npm run build`.

## Notes for the AI

- **The 2025 fit is the build plan's own wording, and it bends the overview's
  "fitted inputs are fitted on 2024 only" rule.** That rule protects projection
  verdicts. 27g takes none: it fits a residual shape, cross-fitted so no case
  scores itself, and changes no projection. A 2024 replay would also be a poor
  stand-in, since it has no 2023 behind it and its early weeks are not
  production-shaped. State this in Results. The real confirmation is Step 7
  and 27h's forward rule.
- **Reuse, do not re-derive:**
  - `replay_cases` and `ARMS["production"]` from `app/backtest/nfl_projections.py`
  - `STAT_COLUMN_BY_MARKET` (already inside the replay actuals)
  - `MIN_BASELINE_GAMES` from `app/core/nfl_projection.py`
- **Performance.** The harness replay takes about 3 minutes a season. Replay
  once and cross-fit in memory; do not replay per fold.
- **Rushing yards can be negative** (QB kneels), so ratios can be negative. Keep
  them; the quantiles handle it.
- **A small projection** (an RB at 6 receiving yards) gives wide ratios. That is
  the true spread, not an outlier to trim. The tercile read in Step 3 shows
  whether it miscalibrates.
- **Expect some hides.** 27b's `share_below` of 54% to 64% means the
  line-equals-projection bin will observe roughly 36% to 46% over. A good
  distribution predicts that; a normal centered on the mean predicts 50% and
  should lose on Brier. Record whatever the run says.
- **Tennis precedent:** `app/core/prop_probs.py` widens sigmas from the market's
  goblin-to-demon gap. Do not borrow those constants; NFL fits its own.
- Standards:
  - `from __future__ import annotations`, `X | None`, no `Any`
  - `app/core/` stays pure; the generated module is data only
  - comment only the why
  - no em dashes in code, docs, or commit messages

## Results

### Step 4 - the 2025 fit

Run 2026-09-26, `python -m app.backtest.nfl_over_probability_fit --season 2025
--write` (14 min 53 s; see the runtime note below). Each case is scored out of
fold: fitted on the other week parity. **This is the sixth read of the 2025
replay.** No projection verdict is taken from it, because 27g fits a residual
shape and changes no projection. The fit uses 2025, not 2024, as the build
plan says: a 2024 replay has no 2023 data behind it, so its early weeks do not
look like production. The forward check is Step 7, then 27h's pre-registered
rule.

**Verdict: two markets show, receiving yards and rushing yards.** Six hide.

| Market | Cases | Pairs | ECE | Worst gap | Brier | Normal | Verdict | Failed on |
|---|---|---|---|---|---|---|---|---|
| receiving yards | 4,549 | 21,857 | 0.010 | 0.014 | 0.2248 | 0.2326 | **show** | |
| rushing yards | 1,892 | 9,000 | 0.009 | 0.038 | 0.2232 | 0.2261 | **show** | |
| fantasy points | 5,235 | 23,013 | 0.015 | 0.068 | 0.2164 | 0.2209 | hide | worst gap (0.7-0.8 bin) |
| receptions | 4,570 | 14,352 | 0.031 | 0.052 | 0.2045 | 0.2084 | hide | ECE, worst gap |
| rushing attempts | 1,360 | 5,781 | 0.027 | 0.053 | 0.2050 | 0.2000 | hide | ECE, gap, Brier |
| passing yards | 582 | 2,906 | 0.013 | 0.047 | 0.1768 | 0.1691 | hide | Brier |
| passing attempts | 582 | 2,873 | 0.013 | 0.017 | 0.1574 | 0.1496 | hide | Brier |
| passing completions | 582 | 2,865 | 0.019 | 0.023 | 0.1573 | 0.1515 | hide | Brier |

**The OVER lean, restated as a probability.** At the line nearest the
projection, the fitted P(over) matches what happened in every market, and a
normal centered on the mean says about 50% everywhere:

| Market | n | Predicted | Observed | Normal |
|---|---|---|---|---|
| receiving yards | 4,549 | 0.380 | 0.381 | 0.500 |
| rushing yards | 1,892 | 0.390 | 0.393 | 0.500 |
| fantasy points | 5,235 | 0.402 | 0.404 | 0.499 |
| receptions | 4,570 | 0.404 | 0.415 | 0.496 |
| rushing attempts | 1,360 | 0.414 | 0.419 | 0.500 |
| passing attempts | 582 | 0.463 | 0.466 | 0.501 |
| passing completions | 582 | 0.482 | 0.488 | 0.500 |
| passing yards | 582 | 0.495 | 0.497 | 0.500 |

So a receiving-yards line set at the projection goes over only about 38% of
the time. That is the mean-versus-median bias 27b found, and it is why the edge
alone misleads.

**Reading it:**
- **Passing markets are calibrated but lose to the normal.** Passing yards and
  volume are close to symmetric, so a normal with the fold's spread is the
  better shape. The empirical fit also has only about 290 QB cases per fold, so
  its quantiles are noisy.
- **Fantasy just misses** on one bin: 699 pairs predicted 0.742, and 0.674
  went over.
- **Receptions and rushing attempts are counts.** The ratio scaling smooths
  over their integer steps, and their reliability tables drift at both ends.
- **By projection size (information only), shown markets are less calibrated
  within terciles than pooled:**

  | Market | Low ECE | Mid ECE | High ECE |
  |---|---|---|---|
  | receiving yards | 0.056 | 0.017 | 0.050 |
  | rushing yards | 0.070 | 0.047 | 0.065 |

  Brier still beats the normal in every receiving-yards tercile, and in the
  low and high rushing-yards terciles (mid: 0.2332 against 0.2314). Low and
  high projections are miscalibrated in ways that partly cancel when pooled. A
  projection-size split is the obvious later variant. It is out of scope here
  and would read the 2025 replay again.
- **Tail artifact.** Tiny projections put extreme ratios in the table's end
  quantiles; RB receiving yards' 100% quantile is 442.9. This only affects lines
  beyond the 97.5% quantile (about 7.8 times the projection), where P(over) is
  already under 2.5%.

**Generated module:** `app/core/nfl_over_probability_fit.py`, holding 5 groups
(receiving yards RB, TE and WR; rushing yards QB and RB) under
`opponent-dvp-tg-blend-usage-snap-v4`.

**Runtime note.** The replay took 14 min 53 s, against 3 min 33 s in 27e. Each
week's `get_replay_rows` query runs about 50 s, with no lock waits. The likely
cause is stale planner statistics on `nfl_player_weekly_stats` after 27f's
backfill. This is not investigated here.

### Step 5 - served on the slate

`/nfl/slate` JSON for 2026 weeks 2 and 3 (`build_slate`, `now` 2026-09-26
12:00 UTC), with `pOver`, `pUnder` and `overProbabilityVersion` stripped, is
byte-identical before and after. The SHA-256 is `b2eed0ff...` (week 2) and
`c8e6f825...` (week 3). Edge, rank, flags and projection are unchanged.

Lines carrying P(over):

| Market | Week | Standard | Goblin | Demon |
|---|---|---|---|---|
| receiving yards | 2 | 176 | 530 | 837 |
| rushing yards | 2 | 74 | 199 | 285 |
| receiving yards | 3 | 84 | 158 | 227 |
| rushing yards | 3 | 58 | 92 | 132 |

Week 3 mean P(over):
- receiving yards: standard 0.402, goblin 0.568, demon 0.267
- rushing yards: standard 0.397, goblin 0.544, demon 0.259

Standard lines sit under 50% on average, as the fit's OVER-lean read predicts.
For example, Kyle Pitts' receiving line (projection 48.6 against 35.5) carries
a +13.1 edge but only a 53.7% P(over).

### Step 6 - evidence panel

`npm run test` passes (182 tests) and `npm run build` passes. Screenshots of
`/#/nfl` 2026 week 3, from a branch API on port 8011 and Vite on port 3021:
- **Kyle Pitts, TE receiving yards:** +13.1 edge, "Over 54% · Under 46%".
  Alternative tags run from Goblin 11.5 (75% over) to Demon 86.5 (22% over).
- **Olamide Zaccheaus, WR receiving yards** (Playwright MCP,
  `.playwright-mcp/27g-evidence-panel.png`, gitignored): +10.1 edge,
  "Over 60% · Under 40%". Tags run from Goblin 0.5 (79%) to Demon 55.5 (9%).

The probability line is muted secondary text. Nothing on the page is colored or
sorted by it.

### Step 7 - forward read on 2026 lines

Run 2026-09-26, `python -m app.backtest.nfl_prizepicks_lines --season 2026`
(22 s). **This is a first read, not a verdict.** Almost every settled line is
from week 2 (666 of 751 standard calls in the model section), and every rung of
a player's goblin and demon ladder counts. The lines are strongly correlated,
so the standard errors below are too small. 27h's pre-registered rule decides
use.

| Odds type | Scored | No P(over) | Predicted | Over | Brier |
|---|---|---|---|---|---|
| standard | 277 | 551 | 41.9% | 44.8% +/- 3.0 | 0.2734 |
| goblin | 802 | 1,079 | 55.9% | 64.1% +/- 1.7 | 0.2441 |
| demon | 1,242 | 1,968 | 25.9% | 24.6% +/- 1.2 | 0.1771 |
| all | 2,321 | 3,598 | 38.2% | 40.6% +/- 1.0 | 0.2117 |

"No P(over)" is mostly the six hidden markets, plus thin samples.

Reliability, all odds types:

| Lines | Predicted | Over |
|---|---|---|
| 492 | 10.4% | 12.2% |
| 737 | 30.8% | 38.5% |
| 710 | 48.9% | 48.5% |
| 369 | 67.7% | 67.5% |
| 13 | 82.7% | 46.2% |

**Reading it:**
- **Demon and middle-bin lines track closely.** Where predicted is 45% or
  above, the prediction lands within a point of the result.
- **Goblins go over more often than predicted:** 64.1% observed against 55.9%
  predicted. The 20-40% bin is 7.7 points low too. Either week 2 ran hot for
  low lines, or P(over) is too pessimistic below the projection. One week
  cannot tell these apart. This is the number 27h has to watch: goblins are
  where a break-even comparison would first tempt a pick.
- **Standard lines hit 44.8%, against 41.9% predicted,** which is within about
  one standard error. Either way they are well under 50%, which is the OVER
  lean the fit set out to show.
