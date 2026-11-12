# Feature: Shrinkage shadow check

**From build-plan:** feature 66a (parent 66, Tennis shrinkage toward the market)
**Status:** not started (spec approved as written 2026-11-11: D1-D8 unchanged, `w = 0.5`, 400 affected matches per slice)

## Goal

Find out whether pulling the served tennis ensemble (`ensemble-v3+lgbm-v6`)
toward the de-vigged market, only where the two disagree by a lot, gives a
better forecast. The idea came from the live `/tennis/model` page on
2026-11-11: on WTA matches where the ensemble and the market differed by 3+
points, the price moved toward the model only 33.3% of 36 times (mean move
-0.45 points), which suggests the market is right on the big disagreements.

That page is the **motivating sample**, so it cannot also be the evidence.
This item keeps three things apart:

| Phase | Data | What it can decide |
|---|---|---|
| **Pre-registration** (Step 1) | none | Fixes the rule and the forward check in one commit before anything is read |
| **Exploration** (Steps 2-4) | Only data outside the motivating sample, all of it already read by earlier items | Can **stop** a slice early. Can never change the rule |
| **Judgment** (Steps 5-8, then a later run) | Only predictions made after the shadow goes live | The one verdict per slice: `adopt` or `keep served` |

Nothing served changes in 66a. Serving a passing slice is 66b.

## Decisions to review

| # | Decision | Why |
|---|---|---|
| D1 | **Threshold `T = 0.03`** (3 probability points, ensemble minus market at prediction, absolute). | It is 26a's `CLV_MIN_GAP`, fixed on 2026-09-25 before any `ensemble-v3` prediction existed. It was not picked by looking at outcomes. |
| D2 | **Weight `w = 0.5`**: at or above the threshold, the shadow keeps half the gap. `p_shadow = p_market + 0.5 * (p_ensemble - p_market)`. Below it, `p_shadow = p_ensemble`. | A hedge picked by reasoning, not by data. Under squared-error loss, if the market is right, halving the gap captures 75% of the gain of going all the way to the market. If the model is right, it costs 25% of what going all the way would cost. Halving also halves the per-match noise, so the check needs fewer matches than a full shrink. **If you would rather go all the way to the market (`w = 1`), say so before Step 1.** After Step 1 it is fixed. |
| D3 | **A hard step at the threshold**, as the existing `ELO_MAX_MARKET_GAP` gate does: a 2.9-point gap is kept, a 3.1-point gap becomes 1.55. | One rule, two numbers, no shape to tune. The gap order flips just above 3 points. That is fine for a shadow, and 66b decides how it is shown. |
| D4 | **Two slices, judged apart:** `ATP+WTA` and `CHALLENGER` (the served blend group, so WTA 125 rides with Challenger). They are never pooled. | Project rule. In the count below, ATP never reaches a 3-point gap under v3 (its market coefficient is 1.14), so `ATP+WTA` is WTA in practice. |
| D5 | **The metric is paired log loss, shadow minus served, on affected matches only** (gap at or above `T`). **Adopt** a slice only if `mean + 2 * SE < 0`, meaning the shadow is better by more than 2 SE. | Below the threshold the two forecasts are the same, so those matches only add zeros. 2 SE per the project rule, with two decisions. |
| D6 | **Minimum sample: 400 affected settled matches per slice**, from at least 30 distinct UTC start days, locked once. | See the sizing below. **This is the main cost of the item.** At about 2 affected WTA matches a day in season, `ATP+WTA` needs roughly 200 in-season days, which probably means mid-2027 with the December off-season. Challenger needs about 90 days. 250 would be faster but weaker. Pick before Step 1. |
| D7 | **The shadow is stored in a new sibling table** (`prediction_shadows`), not as extra rows in `predictions`. | `get_prestart_prediction` and `get_graded_predictions` take the newest row per match, whatever its version. A shadow row in `predictions` would be served and graded as the real model. |
| D8 | **The diagnostic's only power is to stop a slice.** It also scores the fixed rule, labeled exploration. If the rule loses to the served model by more than 2 SE on the Valuebetennis history for a slice, you decide whether to drop that slice before any storage is built. It can never retune `T` or `w`. | Spending six months on shadow rows only makes sense if the pattern shows up outside the sample that suggested it. Retuning on the diagnostic would just be overfitting on a different sample. |

**Sizing evidence (count-only, 2026-11-11).** This was a read-only query of
the last pre-start prediction per match, gap between `p1_ensemble_prob` and
`p1_market_prob`. It read no winners, scores or closing prices:

| Version | Group | Matches | Gap 3+ | Gap 5+ | Days with a 3+ gap |
|---|---|---|---|---|---|
| `ensemble-v3` (2026-10-01 to 11-11) | ATP | 310 | 0 | 0 | 0 |
| | WTA | 390 | 80 | 13 | 32 |
| | CHALLENGER | 1,100 | 184 | 4 | 37 |
| pre-v3 (2026-08-26 to 10-01) | ATP / WTA / CHALLENGER | 337 / 324 / 914 | (hand-set gaps, not v3's) | | |

Most v3 gaps are 3 to 5 points. At a 4-point gap, halving improves the
expected per-match log loss by about 0.002 if the market is right, with a
per-match spread near 0.04. On those numbers, a clean 2 SE pass would need
about 1,000 affected matches. **So 400 is enough to catch a large effect, not
a small one, and "keep served" is a likely result even if the idea is right.**
That is stated now so a weak result is never read as a reason to extend the
sample.

## In scope

- **Pre-registration commit** (Step 1): the rule and the forward check as
  constants and pure functions in `app/core/tennis_shrink.py`, with tests,
  committed alone with this spec. The commit hash is recorded here and in the
  module docstring by the next commit.
- **Read-only diagnostic** (Steps 2-3), `python -m app.backtest.tennis_shrink_diagnostic`,
  by gap bucket, on two sources outside the motivating sample:
  - `--live`: settled live matches with **no** `ensemble-v3` prediction
    (2026-08-26 to 2026-10-01), replayed through the frozen v3 blend with 26d's
    `live_fitted_prob`. CLV is measured from the price at prediction to the
    same book's close, as 26a does.
  - `--history`: Valuebetennis 2023 onward (2022 is excluded because the
    coefficients were fitted on it). v3 is applied to the Pinnacle **opening**
    price, which mimics the live timing where the blend sees a price earlier
    than the close. CLV is measured open to close.
- **Shadow storage** (Steps 5-6): a `prediction_shadows` table and a writer in
  the daily predictions job that stores the shrunk probability beside every
  new prediction that has a market price.
- **Forward check** (Step 7), `python -m app.backtest.tennis_shrink_check`:
  counts only by default, and `--score --slice <slice>` once a slice's floors
  are met.
- **Activation** (Step 8): docs, then the merge and push as their own
  approvals, and the recorded start date.

## Out of scope

- Any change to the served probability, `ENSEMBLE_VERSION`, best picks
  (`MONEYLINE_PICKS_ENABLED` stays `False`), the slate, the match page, the
  `/tennis/model` page or any signal color. That is 66b, and only for a slice
  that passes.
- Showing the shadow anywhere in the UI, or adding it to the model page's
  version switch, before the verdict.
- Other thresholds, weights, logit-space or continuous shrink forms, or
  per-tour weights. Each would be a new rule with its own version and its own
  fresh forward sample.
- Scoring the motivating sample (`ensemble-v3` rows before activation) with
  the rule, now or later. These rows can never enter the verdict.
- A scheduled run of the forward check. It is run by hand, like 26d's
  `--holdout`.
- Regenerating `project-overview.md` here (see Notes).

## Pre-registered rule (frozen at Step 1)

**Rule `shrink-v1`.** These choices are frozen by the Step 1 commit and are not
changed after any data is read.

| Field | Fixed choice |
|---|---|
| Inputs | The served row's `p1_ensemble_prob` and `p1_market_prob` (the de-vigged price that prediction saw), and its tour group (`fitted_group`) |
| Gap | `g = p1_ensemble_prob - p1_market_prob` |
| Shadow | If `abs(g) >= 0.03`: `p_market + 0.5 * g`. Otherwise `p_ensemble`. No market price: no shadow. |
| Symmetry | Swapping the players gives `1 - p`, the same as the served blend |
| Version string | `shrink-v1`. The stored `model_version` is the served version plus `+shrink-v1`, for example `ensemble-v3+lgbm-v6+shrink-v1` |

**Forward check `tennis-shrink-check-v1`.**

| Field | Fixed choice |
|---|---|
| Start | The first full UTC day after the first production shadow row is written (recorded in Step 8). No earlier match can enter, and the rule is never applied retroactively to stored rows. |
| Population | Settled singles matches whose last pre-start served prediction carries the slice's pinned version (`ATP+WTA`: `ensemble-v3+lgbm-v6`; `CHALLENGER`: `ensemble-v3+lgbm-none`, amendment A1) and has a stored `shrink-v1` shadow, a market price at prediction, and a completed score (`is_completed_score`). Retirements and walkovers are excluded and counted. |
| Slices | `ATP+WTA` and `CHALLENGER` (D4), each judged on its own |
| Affected | `abs(p1_ensemble_prob - p1_market_prob) >= 0.03` on the served row |
| Coverage | For each slice, served predictions with a market price that have no shadow row. Required at 98% or more, otherwise the slice is blocked for review. This prevents the writer from silently dropping matches. |
| Sample | Affected matches ordered by `start_utc`, through the first whole UTC start day that reaches **400** affected matches and **30** distinct start days, with a 3-day settlement lag. An unresolved match blocks its day and every later day. A match still unresolved 14 days after its start is dropped and counted as "never resolved" (amendment A2). The sample is locked once, with no rolling or repeated verdict. |
| Metric | Paired per-match log loss, shadow minus served (`paired_loss_difference`) |
| Gate | `adopt` if `mean + 2.0 * SE < 0`, otherwise `keep served`. A finite SE is required. |
| Version continuity | If the served version changes before a slice locks, that slice stops accruing at the change, is reported as `accruing (interrupted)`, and needs a new rule version. Versions are never pooled. |
| Verdict | Below the floors: `accruing`, with counts only. At the lock: `adopt` or `keep served`. A `keep served` is final for `shrink-v1`. Extending the sample to seek a pass is not allowed. |
| Context, at the lock only | Shadow minus market at prediction, Brier, CLV of the served and shadow gaps on affected matches, and the gap-bucket split. Context never changes the verdict. |
| What `adopt` means | It authorizes 66b to serve `shrink-v1` for that slice under a new ensemble version. It is not evidence of a betting edge, and moneyline picks stay off. |

### Pre-activation amendments (owner-approved 2026-11-11, before any shadow row existed)

Both amendments were found while writing Step 7, from row counts and stored
version strings. No outcome, score or loss was read to find them. The rule
(`shrink-v1`: threshold, weight, form) and the gate are unchanged from
`5d99a7f0`.

- **A1 - pinned version per slice.** Challenger predictions are stored as
  `ensemble-v3+lgbm-none`, because there is no LightGBM model for Challenger.
  So a single `ensemble-v3+lgbm-v6` pin would have left the Challenger slice
  empty.
- **A2 - matches that never resolve.** Of the 1,809 matches since 2026-10-01
  with a prediction and a start more than 4 days ago, 11 are stuck
  `scheduled` and 1 is `completed` with no winner. Under "unresolved blocks
  every later day", one stale affected match would freeze a slice forever.
  A match still unresolved 14 days after its start is now dropped and
  counted. Its outcome is unknown, so dropping it does not select on
  results.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

**Step 1 is the one exception:** its commit is required, not optional,
because its hash is the proof that the rule came first.

## Build steps

- [x] **Step 1 - Pre-registration commit.** Add `app/core/tennis_shrink.py`
  (pure, no I/O):
  - constants `SHRINK_VERSION = "shrink-v1"`, `SHRINK_THRESHOLD = 0.03`,
    `SHRINK_WEIGHT = 0.5`, `CHECK_VERSION = "tennis-shrink-check-v1"`,
    `MIN_AFFECTED = 400`, `MIN_DAYS = 30`, `SETTLEMENT_LAG_DAYS = 3`,
    `MIN_COVERAGE = 0.98`, `GATE_STANDARD_ERRORS = 2.0`,
    `SLICES = ("ATP+WTA", "CHALLENGER")`
  - `shrink_toward_market(ensemble, market) -> float`, `is_affected(ensemble, market) -> bool`,
    `shadow_version(served_version) -> str`, `slice_for(tour) -> str`,
    `gap_bucket(gap) -> str` (buckets `<1`, `1-3`, `3-5`, `5+` points),
    `verdict(difference, affected, days) -> Literal["accruing", "adopt", "keep served"]`

  The step ends with one commit holding only this module, its tests and this
  spec, with the rule tables above unchanged. Record its short hash under
  Evidence. A follow-up commit adds the hash to the module docstring.

  *Done when:*
  - Tests pass for: a gap of exactly 0.03 shrinks and 0.0299 does not; both
    signs; player-swap symmetry; output equals the market plus half the gap;
    the version string; bucket edges; the verdict at the floor, below it, at
    `mean + 2SE` exactly 0 (this reads `keep served`), and with a missing SE.
  - The commit exists before any Step 2 code runs against data.
- [x] **Step 2 - Live diagnostic (`--live`).** Add
  `app/backtest/tennis_shrink_diagnostic.py` with a pure `live_report(rows)`:
  - Keep `get_graded_predictions` rows for matches that have **no**
    `ensemble-v3` prediction at all, and take the latest pre-start row per
    match (26d's `live_rows`). The new filter is a pure function over rows.
  - Replay v3 with `live_fitted_prob`.
  - For each group (ATP, WTA, ATP+WTA, CHALLENGER) and each gap bucket,
    print: n, log loss for replayed v3 and the market, v3 minus market ±SE,
    shrink-v1 minus v3 ±SE (3+ buckets only), and CLV (eligible, moved,
    toward rate, mean move).
  - Print a header saying "exploration, not a verdict; these rows were read
    by 26a and 26d", plus exclusion counts.

  *Done when:*
  - A synthetic-row test checks that a match with any v3 row is excluded, the
    bucket assignment, that the shrink difference is zero below the threshold,
    and the section headers.
  - One read-only run on the live database is pasted under Evidence.
- [x] **Step 3 - History diagnostic (`--history`).** In the same module, add
  a pure `history_report(cases)` over `ClosingLineCase`:
  - Seasons 2023 onward. Read it through `--data-dir`; the CSVs live in the
    main checkout's `api/data/valuebetennis`.
  - v3 is `market_anchored_prob` on `open_prob`, with ELO dropped when
    `elo_is_unreliable(elo, open, None)`.
  - Print the same bucket table, with the open as "market", the close as a
    reference row, and CLV open to close.
  - Label 2023-2025 as read twice (26c, 26d) and 2026 as read by 40a.

  *Done when:*
  - A synthetic-case test checks that 2022 is excluded, that the open (not the
    close) feeds the blend, and the buckets.
  - One run is pasted under Evidence.
- [x] **Step 4 - Diagnostic review gate (no code).** Present both reports.
  For each slice, flag any slice where shrink-v1 minus v3 on the history's
  affected cases is worse by more than 2 SE (`mean - 2SE > 0`). You decide,
  per slice, whether to **continue** or **drop** it. The rule stays as
  committed either way.

  *Done when:* your decision per slice is recorded under Evidence. If both
  slices are dropped, the item stops here and goes to `/complete` as "dropped
  at diagnostic", with no storage built.
- [x] **Step 5 - Shadow table.** Add the next free migration number (check
  sibling worktrees first; master's highest is `0053`). It creates
  `prediction_shadows`:
  - `id`
  - `prediction_id` -> `predictions.id`, on delete cascade
  - `model_version text not null`
  - `p1_prob double precision not null`
  - `created_at timestamptz default now()`
  - a unique key on (`prediction_id`, `model_version`)

  In `app/repositories/predictions.py`, add `insert_prediction_shadow`. The
  existing loaders stay untouched.

  *Done when:*
  - A recorded-SQL test covers the insert.
  - The migration upgrade and downgrade are shown, then applied to Neon as one
    manual command after your yes.
- [x] **Step 6 - Writer.** In `app/ingest/predictions.py`, a pure
  `shadow_insert_args(prediction, served_version)` returns `None` without a
  market price. Otherwise it returns `shrink_toward_market` under
  `shadow_version(served_version)`. `persist_predictions` writes the shadow in
  the same transaction, using the id `insert_prediction` returns. A shadow is
  stored even when it equals the served value, so coverage can be counted.
  The served row's arguments are unchanged.

  *Done when:*
  - Tests show `prediction_insert_args` output is unchanged, there is no
    shadow without a market, there is an equal shadow below the threshold,
    and there is a shrunk shadow above it.
  - A local run against a disposable or dev database is shown only if you
    approve it. Otherwise it is proven by tests only and the first real write
    happens in Step 8.
- [x] **Step 7 - Forward check CLI.** Add a repository loader that returns the
  served row joined to its shadow, split into two functions:
  - a **count loader** that selects no winner, score or closing-price column
  - a **score loader** that is used only under `--score`

  Add `app/backtest/tennis_shrink_check.py`:
  - The default mode prints, per slice: the start date, affected count, days,
    coverage and whether the floors are met.
  - `--score --slice X` refuses until the floors and coverage are met. It then
    locks the sample as defined above and prints the verdict and the context.
  - It is read-only.

  *Done when:*
  - Tests show that count mode never calls the score loader, the sample lock
    stops at the first whole day reaching both floors, an unresolved earlier
    match blocks the lock, the coverage gate works, and a served-version
    change interrupts the slice.
  - A count run against the live database reads 0 affected (nothing is
    active yet).
- [ ] **Step 8 - Docs and activation.**
  - Add both commands to `docs/commands.md` and to the AGENTS.md Ingest list.
  - Update the tennis "model today" notes in `docs/tennis-actions.md` if the
    predictions step's output changes.
  - Update the interview guide if it exists.
  - Merge the branch with `--ff-only` so the Step 1 commit stays reachable,
    as its own approval. Push as a separate approval.
  - After the first production `tennis-predictions.yml` run, record the first
    shadow row's timestamp and the check's start date under Evidence.

  *Done when:*
  - A count run after that job shows shadow rows with 100% coverage for that
    day.
  - The start date is recorded.
  - The verdict itself is a later, separately approved `--score` run per
    slice, not part of 66a's completion.

## Files / areas

- `api/app/core/tennis_shrink.py` (new) - the rule, forward-check constants, verdict
- `api/app/backtest/tennis_shrink_diagnostic.py` (new) - `--live` and `--history`
- `api/app/backtest/tennis_shrink_check.py` (new) - count and score modes
- `api/app/db/migrations/versions/00NN_prediction_shadows.py` (new)
- `api/app/repositories/predictions.py` - shadow insert and the two shadow loaders
- `api/app/ingest/predictions.py` - writes the shadow beside each prediction
- `api/tests/test_tennis_shrink*.py`, `api/tests/test_predictions_ingest*.py` (new or extended)
- `docs/commands.md`, `AGENTS.md`, `docs/tennis-actions.md` - commands and notes
- Reused unchanged: `app/core/tennis_grading.py`, `app/backtest/tennis_market_blend.py`
  (`live_rows`, `live_fitted_prob`), `app/backtest/tennis_closing_lines.py`,
  `app/services/tennis/ensemble.py`

## Data / contracts

- **`prediction_shadows` (load-bearing for 66b and any later shadow):** one row
  per (`prediction_id`, `model_version`). The probability is for p1, as on
  `predictions`. A served prediction can carry several shadows under
  different versions, and none of them is ever read by a serving path.
- **Shadow version strings:** `<served model_version>+<rule version>`. Rule
  versions are never reused or edited. A changed `T` or `w` is `shrink-v2`.
- **`app/core/tennis_shrink.py` constants are frozen** from the Step 1 commit.
  An edit to any of them invalidates `tennis-shrink-check-v1`.
- No API, schema or response change for any existing endpoint.

## Testing

Test gate on (`pytest`). Logic that needs tests: the rule and verdict (Step 1),
the diagnostic filters and buckets (Steps 2-3), the shadow insert SQL (Step 5),
the shadow mapper (Step 6), and the count/score split, sample lock, coverage
and interruption (Step 7). There is no UI work, so there are no browser checks.
The final gate is the Verify command from the repo root. Real-data runs
(Steps 2, 3, 7 and 8) are read-only and pasted as evidence.

## Notes for the AI

- **Order is the point.** Step 1's commit comes before any data read in this
  item. Steps 2-3 read only already-read data and can only stop a slice.
  Judging data is only what accrues after Step 8. Never compute `shrink-v1` on
  stored `ensemble-v3` rows from before activation, even "just to look".
- **Never print outcome-based numbers in count mode,** including interim log
  loss tables. Counts only until the lock.
- **Merge with `--ff-only`**, not squash, because Step 1's hash is cited (owner
  rule, see memory and 44a). Push is a separate yes.
- `core/` stays pure. Repositories own the SQL. Challenger is never pooled
  with ATP/WTA.
- **Overview not regenerated in this worktree.** Several sibling worktrees are
  changing `blueprint/build-plan.md` at once, so a regeneration here would
  conflict. Regenerate `project-overview.md` once after the parallel items
  land, or at `/complete`.
- Build-plan number 66 is claimed in the shared side-session notes
  (`build-plan-numbers.md`).
- The count-only sizing query above was a scratch script outside the repo.
  It read no results and is not part of the item.
- No em dashes in anything written for this item.

## Evidence

- Pre-registration commit: `5d99a7f0` (`5d99a7f0f39c076ddc2c06482ed275c4236be39c`),
  2026-11-11, on `feature/tennis-shrinkage`. It holds only
  `app/core/tennis_shrink.py`, `tests/test_tennis_shrink.py` and this spec.
  No diagnostic or forward data had been read for item 66 before it. Verify
  passed before the commit: web verify green, API 6,123 passed.
- Diagnostic `--live` (run once 2026-11-11, read-only, exploration only):
  `python -m app.backtest.tennis_shrink_diagnostic --live`.
  - Rows: 3,374 settled graded matches. 1,823 are scorable by 26d's live
    filter. 987 were dropped for having any `ensemble-v3` prediction. That
    leaves 836, from 2026-08-26 to 2026-10-01: ATP 208, WTA 230, Challenger
    398.
  - ATP: no v3 gap of 3+ points, matching the count above.
  - In the table, the affected (3+) rows are paired log loss ± one SE, with
    negative favoring the first forecast. The CLV columns are moved prices,
    the share that moved toward v3, and the mean move in points.

    | Slice | n | v3 - market | shrink-v1 - v3 | CLV moved | Toward | Mean |
    |---|---|---|---|---|---|---|
    | ATP+WTA (WTA only) | 63 | +0.0047 ± 0.0112 | -0.0033 ± 0.0056 | 21 | 33.3% | -0.26 |
    | CHALLENGER | 134 | -0.0016 ± 0.0081 | -0.0003 ± 0.0042 | 74 | 36.5% | -0.66 |

  - WTA by bucket: the 3-5 bucket is shrink -0.0001 ± 0.0051 (n 47). The 5+
    bucket is -0.0130 ± 0.0166 (n 16, CLV toward 16.7%).
  - Below 3 points, the CLV toward rate is 44-68% in every group.
  - Reading: the motivating CLV pattern shows up outside the motivating
    sample. Moved prices go against v3 at 3+ points in both slices,
    strongest in Challenger. The log-loss effect of the rule is within one
    SE everywhere. Nothing here is a verdict, and the Step 4 stop test reads
    the history diagnostic.
- Diagnostic `--history` (run once 2026-11-11, exploration only):
  `python -m app.backtest.tennis_shrink_diagnostic --history --data-dir <main checkout>/api/data/valuebetennis`.
  - Rows: 467,485 cases in all. 54,884 were kept: 26c's scored ATP and WTA
    sets plus its Challenger set, 2023 to 2026-09-30, with an opening price.
  - Two exclusions:
    - 2022, the season the coefficients were fitted on.
    - Matches on or after 2026-10-01. This exclusion was added in this step
      because Valuebetennis 2026 holds the same matches as the motivating
      sample, priced by Pinnacle.
  - ELO is gated at a 15-point gap to the open (no prior-match count).
  - In the table, the affected (3+) rows are paired log loss ± one SE. The
    market is the de-vigged Pinnacle open, and CLV is open to close.

    | Slice | n | v3 - open | shrink-v1 - v3 | CLV moved | Toward | Mean | v3 - close (reference) |
    |---|---|---|---|---|---|---|---|
    | ATP+WTA (WTA only) | 2,242 | +0.0021 ± 0.0022 | -0.0024 ± 0.0011 | 2,238 | 48.8% | -0.32 | +0.0049 ± 0.0028 |
    | CHALLENGER | 9,124 | -0.0029 ± 0.0009 | +0.0005 ± 0.0005 | 8,638 | 59.4% | +0.31 | +0.0012 ± 0.0011 |

  - WTA by bucket: the 3-5 bucket is shrink -0.0010 ± 0.0012 (n 1,552). The
    5+ bucket is -0.0055 ± 0.0024 (n 690, CLV toward 45.6%, mean -0.66).
  - ATP has no 3+ gaps here either.
  - **Step 4 stop test** (drop a slice if shrink-v1 minus v3 on the
    history's affected cases has `mean - 2SE > 0`):
    - ATP+WTA: -0.0046, not triggered.
    - CHALLENGER: -0.0005, not triggered.
  - Reading:
    - WTA agrees with the live pattern. On Pinnacle, the rule beats v3 by
      about 2.2 SE, mostly from the 5+ bucket.
    - Challenger disagrees. On Pinnacle, v3 beats the open at 3+ points by
      about 3 SE, and the close moved toward v3 59.4% of the time, the
      opposite of the live 36.5% on DraftKings and FanDuel prices. The rule
      is about 1 SE worse there.
    - So the live Challenger pattern may be a soft-book effect rather than
      v3 being wrong.
    - None of this is a verdict, and the rule is unchanged.
- Slice decisions (owner, 2026-11-11): **continue both** `ATP+WTA` and
  `CHALLENGER`. Neither tripped the stop test. Challenger's history result
  (v3 ahead of the Pinnacle open) is noted as a reason the forward check may
  read `keep served`, not as a reason to drop it. The rule is unchanged from
  `5d99a7f0`.
- Shadow table (Step 5, 2026-11-11): migration `0054_prediction_shadows`
  was applied to Neon after the owner's yes and a passing Verify (web green,
  API 6,141 passed).
  - The command was `alembic -c <scratch ini> upgrade 0054`, with
    `script_location` set to this worktree's migrations.
  - Before: head `0053`, no table. After: head `0054`, and
    `prediction_shadows` exists and is empty.
  - Until this branch merges, Neon is ahead of master's migrations. No other
    item may take `0054`; this is claimed in the side-session notes.
- Forward check (Step 7, 2026-11-11): `python -m app.backtest.tennis_shrink_check`
  on the live database printed `tennis-shrink-check-v1: no shrink-v1 shadow rows yet;
  nothing is active. Affected 0.` Verify passed (web green, API 6,167 passed).
  - Not built: the spec's lock-time CLV context. The loaders carry no closing
    price, and it never affects the verdict. The diagnostic and the model
    page still give CLV.
- Activation timestamp and start date: _(Step 8)_

## Draft critique and changes

- **Shadow rows in `predictions` would have been served.** The first draft
  stored the shadow as a second `predictions` row. `get_prestart_prediction`
  takes the newest row of any version, so the shadow would have reached the
  slate and the grading. The shadow moved to a sibling table (D7).
- **The diagnostic could have become a tuning pass.** It now scores only the
  committed rule, and its only outcome is continue or drop per slice (D8,
  Step 4). Step 1 moved ahead of it, so the rule comes before every data
  read, not only the forward ones.
- **The "2022" trap.** The history diagnostic excludes the fit season. It
  replays the opening price, not the close, because the close is what v3 was
  fitted on and would hide the timing mismatch.
- **ATP is inert.** The count showed no v3 ATP gap at 3+ points, so
  `ATP+WTA` is effectively WTA. The slice was kept as the project's standard
  group, and the fact is stated so a thin ATP count is not a surprise.
- **Power stated up front.** The sizing estimate showed 400 affected matches
  only catches a large effect. The "no extension to seek a pass" rule and D6's
  timing make that cost visible before approval, instead of after a weak
  result.
- **Coverage gate added.** A silently failing writer would have made affected
  matches go missing in a non-random way. The check now requires 98%
  coverage.
- **Split.** Serving is a separate conditional 66b, so 66a ends at a verdict
  that changes nothing served.
