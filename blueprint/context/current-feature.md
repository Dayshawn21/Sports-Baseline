# Feature: NBA over probability, second method - 2026-27 confirmation

**From build-plan:** feature 44b (parent 44)
**Status:** spec ready for review; steps 1-4 can be built now, step 5 waits for the gate (about 2026-11-17)

## Goal

Score 44a's frozen P(over) families once on the pre-registered 2026-27 sample
(regular-season weeks 1-4), under 20g1's display rule unchanged, and record a
`show` or `hide` verdict per carried market. 44c serves only the markets this
run shows. Any run before the four weeks are fully played stops as `accruing`
without reading a single 2026-27 box score.

This is a backtest only: nothing served changes.

## In scope

- **A confirmation CLI** `python -m app.backtest.nba_over_probability_v2_confirm`:
  - **Default (gate) mode:** reads `sport_games` only. It prints, for 2026 weeks
    1-4, each week's `REG` game count, completed count, and whether the week is
    finished (`get_finished_weeks`), then `accruing` or `ready`. It loads no box
    score.
  - **`--score`:** checks the gate first. If any of weeks 1-4 is unfinished it
    prints `accruing` and exits before loading any box score. If a confirmation
    is already recorded (the generated module below exists), it refuses. Only
    then does it load box scores, score, print the report, and write the result.
- **What is scored (fixed in this spec, committed before the gate opens):**
  - **Cases:** 20f eligibility and the reference projection (`replay_cases`
    with `ARMS[REFERENCE_ARM]`, season 2026), restricted to `REG` games whose
    stored `sport_games.week` is 1-4 and to the six carried markets in
    `PARAMS_BY_MARKET`. A case needs a projection above zero.
  - **History loaded:** seasons 2023, 2024, 2025 and 2026, so prior-game depth
    matches serving (`get_prior_games` reads every stored season). 2023-25
    rows are projection inputs only. **No 2025-26 case is scored**, so the
    2025-26 holdout read count stays at 2.
  - **Probabilities:** each market's frozen family and parameters from
    `nba_over_probability_v2_fit.PARAMS_BY_MARKET`, read at 20g1's synthetic
    x.5 lines (`synthetic_lines`). Never refitted.
  - **Brier baseline:** the constant-sigma normal with each market's sigma
    from **all of 2024-25** (stdev of actual minus projection over the 2024-25
    reference replay, projection above zero). This mirrors 20g1, whose normal
    came from the fit season, not the scored one.
  - **Verdict:** `nba_display_verdict` with the imported constants (300 cases,
    ECE <= 0.02, no 200+-pair bin off by more than 0.05, Brier no worse than
    the normal).
  - **Drift guard:** before scoring, refit each carried market on the 2024-25
    replay and compare with the frozen parameters (relative tolerance 1e-9).
    A mismatch stops the run with the differences printed, for owner review.
    It never substitutes the refit.
- **Report:** header (version, projection, pre-registration `ebd4aea`, this
  spec's checkpoint hash, seasons loaded, "2025-26 cases scored: 0"), the
  per-market table (family, cases, pairs, ECE, worst bin, Brier, normal Brier,
  verdict, failed checks), the two `not_carried` markets listed as such, the
  sample's coverage (games and cases per week), and whole-number-line P(push)
  predicted against observed for each carried market, labelled information only.
- **A generated result module** `app/core/nba_over_probability_v2_confirmation.py`,
  written once by `--score`:
  - `CONFIRMATION_SEASON`, `CONFIRMATION_WEEKS`, `OVER_PROBABILITY_VERSION`,
    `FIT_PROJECTION_MODEL_VERSION`, `SCORED_AT` (UTC ISO)
  - `SHOWN_MARKETS` and `HIDDEN_MARKETS` (frozensets), and `NOT_CARRIED`
    copied from the fit module
  - a per-market results table (cases, pairs, ECE, worst gap, Brier, normal
    Brier, verdict) for the record
  - added to `GENERATED_FITS` in `.agents/hooks/protect-files.mjs`
- **A repository read** `get_week_game_ids(db, season, weeks) -> dict[int, int]`
  (game id to week) in `app/repositories/nba.py`: `sport = 'nba'`,
  `game_type = 'REG'`, `week = ANY(:weeks)`.

## Out of scope

- Serving, freezing, ranking, page or `SPORT_STATUS` changes (44c).
- Refitting, retuning, or changing any family, parameter, market list, sample
  week or display constant. A failing market stays hidden for `nba-pover-v2`.
- Assists (stays on `nba-pover-v1`), threes and blocks (not carried).
- A second scoring run, a different sample, or reading 2025-26 outcomes.
- Projection or eligibility changes.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit.
   **Exception:** the step 3 checkpoint is required. It pins how the sample is
   scored before the gate opens, and its hash is recorded here.

Never accept a step you haven't read. If a diff is too big to review, the step
was too big, so split it.

## Build steps

- [x] **Step 1 - Pure confirmation scoring** - new
  `app/core/nba_over_probability_v2_confirmation_score.py`: filter cases to
  the sample (game ids in the week map, carried markets, projection above 0);
  per-market sigma from fit-season cases; score with the frozen params; the
  per-market evaluation (reuse `read_family`, `evaluate` and `ScoredLine`
  from 44a's modules); the drift comparison; the gate decision from
  `finished_weeks` (`ready` only when every confirmation week is finished).
  *Done when:* tests with synthetic cases show:
  - a case outside weeks 1-4, a non-`REG` game, a non-carried market or a
    zero projection is never scored
  - the normal's sigma comes from the fit-season cases, not the scored ones
  - the params scored are exactly the frozen ones (a test passes a different
    refit and proves it only trips the drift guard)
  - the gate is `accruing` with weeks {1, 2, 3} finished and `ready` with
    {1, 2, 3, 4, 5}
  - the fit module's `CONFIRMATION_SEASON`/`CONFIRMATION_WEEKS` equal the
    pre-registration module's
- [x] **Step 2 - Repository read** - `get_week_game_ids` as above. *Done when:*
  the query carries the sport and `REG` filters, and a read-only local call for
  season 2026 weeks 1-4 returns the week-1 games (opening night 2026-10-20
  onward) with no box-score table touched.
- [x] **Step 3 - CLI, report and result module** -
  `app/backtest/nba_over_probability_v2_confirm.py` with gate mode, `--score`,
  the report and `render_module`; the hook entry. *Done when:*
  - a CLI test proves `--score` with an unfinished week exits `accruing`
    without calling `get_projection_history` (patched loader asserted unused)
  - a CLI test proves `--score` refuses when the result module exists
  - a test re-renders the result module from fixed inputs and pins its format
  - a report-format test exists
  - Verify passes, and a **checkpoint commit** exists with its hash recorded
    below, before the gate opens
- [ ] **Step 4 - Gate run now** - run gate mode against the shared database
  and record its output below (expected `accruing`: weeks 1-4 not finished).
  *Done when:* the output is recorded and shows no box-score load. Also run
  `--score` once to record the `accruing` stop.
- [ ] **Step 5 - The one scoring run (after the gate opens; separate owner
  approval)** - once gate mode reads `ready` (about 2026-11-17, after the
  Monday box-score load), the owner approves, then `--score` runs once.
  *Done when:*
  - the full report is recorded below, with each market's verdict
  - the result module is written and the hook refuses an `Edit` of it
  - the 2025-26 holdout read count is recorded as unchanged (2)
  - Verify passes

## Files / areas

- New: `api/app/core/nba_over_probability_v2_confirmation_score.py`,
  `api/app/backtest/nba_over_probability_v2_confirm.py`,
  `api/app/core/nba_over_probability_v2_confirmation.py` (generated in step 5)
- New tests: `api/tests/test_nba_over_probability_v2_confirmation.py`,
  `api/tests/test_nba_over_probability_v2_confirm_cli.py`
- Changed: `api/app/repositories/nba.py` (`get_week_game_ids`),
  `.agents/hooks/protect-files.mjs` (one `GENERATED_FITS` entry)
- Read only: `nba_over_probability_v2.py`, `nba_over_probability_v2_fit.py`,
  `nba_over_probability_v2_crossfit.py`, `nba_over_probability.py`,
  `nba_projection_backtest.py`, `get_finished_weeks`, `get_projection_history`

## Data / contracts

- **No schema, API or UI change.**
- **Load-bearing for 44c:** `SHOWN_MARKETS` in the generated result module is
  the only list 44c may serve under `nba-pover-v2`. A test in 44c should import
  it rather than copy it. An empty `SHOWN_MARKETS` means 44c is dropped.
- **Load-bearing (scoring rules):** after the step 3 checkpoint, the sample
  filter, sigma source, history depth and drift guard are fixed. Changing any
  of them after that commit needs a recorded reason and owner approval, and is
  never allowed once the gate has opened.
- **Merge:** the step 3 checkpoint and `ebd4aea` are cited commits, so this
  branch merges `--ff-only`, never squashed.

## Testing

- Steps 1 and 3: unit tests with synthetic cases and patched loaders, no
  database, fixed timestamps.
- Steps 2, 4 and 5: real local runs recorded here as evidence, not tests.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- **Holdout discipline:** 2025-26 rows are loaded as prior games only; never
  call `replay_cases` with season 2025 here. The 2026-27 sample is read once,
  in step 5, with owner approval in that session.
- **Gate before load:** the `--score` path must call `get_finished_weeks` and
  the result-module check before `get_projection_history`. Import the database
  module inside `_main`, as 44a's CLI does.
- **Do not tune on a near miss.** 44a's `scaled_normal` Brier margins over the
  normal are 0.0003 to 0.0011, so a market can fail the Brier gate on noise. It
  stays hidden; a different method is a new item.
- Week 1 is Monday to Sunday holding opening night (2026-10-20); week 4 ends
  Sunday 2026-11-15; box scores load at 09:30 UTC the next morning. A postponed
  game never holds a week open.
- Run DB steps from `api/` with the venv Python and the Windows selector event
  loop. Loading four seasons may take a couple of minutes.
- Match 44a's module style and comment density. No em dashes.
- **Interview guide:** update at `/complete` with the confirmation result (a
  validation finding). It is untracked; never stage it.

## Results

- **Scoring-rules checkpoint (step 3):** _pending_
- **Gate run (step 4):** _pending_
- **Confirmation run (step 5):** _pending_
