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
| Population | Settled singles matches whose last pre-start served prediction is `ensemble-v3+lgbm-v6` and has a stored `shrink-v1` shadow, a market price at prediction, and a completed score (`is_completed_score`). Retirements and walkovers are excluded and counted. |
| Slices | `ATP+WTA` and `CHALLENGER` (D4), each judged on its own |
| Affected | `abs(p1_ensemble_prob - p1_market_prob) >= 0.03` on the served row |
| Coverage | For each slice, served predictions with a market price that have no shadow row. Required at 98% or more, otherwise the slice is blocked for review. This prevents the writer from silently dropping matches. |
| Sample | Affected matches ordered by `start_utc`, through the first whole UTC start day that reaches **400** affected matches and **30** distinct start days, with a 3-day settlement lag. An unresolved match blocks its day and every later day. The sample is locked once, with no rolling or repeated verdict. |
| Metric | Paired per-match log loss, shadow minus served (`paired_loss_difference`) |
| Gate | `adopt` if `mean + 2.0 * SE < 0`, otherwise `keep served`. A finite SE is required. |
| Version continuity | If the served version changes before a slice locks, that slice stops accruing at the change, is reported as `accruing (interrupted)`, and needs a new rule version. Versions are never pooled. |
| Verdict | Below the floors: `accruing`, with counts only. At the lock: `adopt` or `keep served`. A `keep served` is final for `shrink-v1`. Extending the sample to seek a pass is not allowed. |
| Context, at the lock only | Shadow minus market at prediction, Brier, CLV of the served and shadow gaps on affected matches, and the gap-bucket split. Context never changes the verdict. |
| What `adopt` means | It authorizes 66b to serve `shrink-v1` for that slice under a new ensemble version. It is not evidence of a betting edge, and moneyline picks stay off. |

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

- [ ] **Step 1 - Pre-registration commit.** Add `app/core/tennis_shrink.py`
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
- [ ] **Step 2 - Live diagnostic (`--live`).** Add
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
- [ ] **Step 3 - History diagnostic (`--history`).** In the same module, add
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
- [ ] **Step 4 - Diagnostic review gate (no code).** Present both reports.
  For each slice, flag any slice where shrink-v1 minus v3 on the history's
  affected cases is worse by more than 2 SE (`mean - 2SE > 0`). You decide,
  per slice, whether to **continue** or **drop** it. The rule stays as
  committed either way.

  *Done when:* your decision per slice is recorded under Evidence. If both
  slices are dropped, the item stops here and goes to `/complete` as "dropped
  at diagnostic", with no storage built.
- [ ] **Step 5 - Shadow table.** Add the next free migration number (check
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
- [ ] **Step 6 - Writer.** In `app/ingest/predictions.py`, a pure
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
- [ ] **Step 7 - Forward check CLI.** Add a repository loader that returns the
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

- Pre-registration commit: _(Step 1)_
- Diagnostic `--live`: _(Step 2)_
- Diagnostic `--history`: _(Step 3)_
- Slice decisions: _(Step 4)_
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
