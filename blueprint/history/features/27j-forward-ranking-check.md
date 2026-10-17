# Feature: Forward ranking check

**From build-plan:** feature 27j
**Status:** completed (2026-09-26)

## Goal

Settle the predictions 27i freezes before kickoff, and apply 27i's
pre-registered ranking rule to them for each payout slice: standard over,
standard under, goblin over, and demon over. The weekly report shows each
slice's running sample and, once the sample is fixed, its one-time verdict.
27h may rank by P(over) only on a slice whose verdict is `adopt`.

This is read-only: no model, schema, ranking, or UI change.

## In scope

- Settling frozen `nfl_prop_predictions` rows through 27a's `settle_line`.
- Applying `app/core/nfl_ranking_rule.py` unchanged: `to_pick`,
  `one_pick_per_bet`, `verdict_sample`, `slice_verdict`.
- Grading only rows under the current `NFL_PROJECTION_MODEL_VERSION` and
  `OVER_PROBABILITY_VERSION`, with other versions counted as their own
  exclusion.
- Coverage context: how many of 27a's settled full-game lines had a frozen
  prediction at all.
- `python -m app.backtest.nfl_ranking_check [--season 2026]`, plus a step that
  writes the report to the Tuesday `nfl-ingest.yml` Summary page.

## Out of scope

- Any ranking or display change. That is 27h, and only after an `adopt`.
- Changing any constant in `nfl_ranking_rule.py`. A change there is a new rule
  under a new version, not an edit.
- Replaying the slate to fill in missing frozen rows. 27i forbids it: a line
  with no frozen row counts as unfrozen.
- `nfl_prop_results`, which stays unused.
- First-half and first-quarter lines. `settle_line` cannot settle them, and
  they are counted as `unsettleable_segment`.
- Rewording 27h's build-plan line (overview open question 21). That is a plan
  edit to make before `/feature 27h`.

## Decision: which frozen row is graded (overview open question 24)

**Grade the latest frozen pre-kickoff row of each provider prop, settled at
the line it was frozen on.**

27i's contract said 27j grades the row on the line 27a grades (the last
pre-kickoff snapshot) and counts it as unfrozen when that snapshot has no
frozen row. That breaks whenever a snapshot is taken after the last freeze:
- the freeze step fails
- a snapshot runs without the freeze step, as Saturday 2026-09-26 23:00 UTC did
  before the push

In those cases a real, pre-kickoff prediction for the same prop exists, and it
would be thrown away.

Grading the latest frozen row instead:
- **Is still leak-free.** Every frozen row is generated before kickoff, and the
  choice depends only on timestamps, never on the result.
- **Is the bet the model actually offered.** The prediction is paired with the
  line it was computed against, so a later line move cannot misgrade it.
- **Keeps 27i's "never replay" rule.** A provider prop with no frozen row at
  all stays unfrozen and is reported as a coverage gap.

27a is unchanged and still grades the newest snapshot. The two reports can
differ on a prop whose line moved after the last freeze, and that is
intended: 27a grades the line, 27j grades the frozen call.

**Two further rules, fixed now before any week has settled:**
- **Only fully played weeks count.** A week reaches the rule only when every
  regular-season game in it is completed and its stats are loaded.
  `verdict_sample` treats every week it sees as whole, so a half-played week
  could otherwise fix a sample that then changes (the same guard as item 28).
- **Pushes are not picks.** A whole-number line that lands exactly is counted
  and reported as a push, and never enters `slice_verdict`. `FrozenCall` has
  no push outcome, and PrizePicks refunds it.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Frozen calls and slice results (core)** - create
  `app/core/nfl_ranking_check.py`:
  - `FrozenLine`: a `GradeableLine` plus the frozen `p_over`, `p_under`,
    `model_version` and `over_probability_version`
  - `to_frozen_call(line, finished_weeks)`, which returns a `FrozenCall`, or an
    exclusion reason drawn from:
    - `wrong_version`
    - `week_not_finished`
    - `settle_line`'s own outcome (`unsettleable_segment`, `week_not_loaded`,
      `void_dnp`)
    - `push`
  - `slice_results(calls)`, which returns one `SliceResult` per slice plus the
    pick funnel:
    - calls
    - calls with a P(over)
    - picks before dedupe (`to_pick`)
    - picks after `one_pick_per_bet`

    All four slices are always present. An empty slice reads `insufficient`
    with n = 0 instead of raising, as `slice_verdict` would.

  Add `tests/test_nfl_ranking_check.py`. *Done when:* tests pass for:
  - a settled over and a settled under becoming calls with the right outcome
  - each exclusion reason, including a push and a completed game in an
    unfinished week
  - a row under another model or P(over) version excluded
  - a null P(over) giving a call but no pick
  - two ladder rungs of one bet collapsing to one pick
  - all four slices present when some are empty
  - a slice reaching `adopt` on fixed data, with the verdict matching
    `slice_verdict` called directly
- [x] **Step 2 - Repository read** - add to `app/repositories/nfl.py`:
  - `get_frozen_gradeable_lines(db, season)`: per provider prop, the latest
    `nfl_prop_predictions` row whose line snapshot was fetched before kickoff,
    joined to that snapshot's line, stats, and snaps. It is shaped like
    `get_gradeable_prop_lines`, and the stat-column mapping is shared rather
    than copied.
  - `get_finished_weeks(db, season)`: the weeks whose regular-season games are
    all completed.
  - `get_frozen_coverage(db, season)`: per week, how many of 27a's latest
    pre-kickoff full-game lines on completed games have any frozen row for
    their provider prop. It is per week because weeks before 27i are wholly
    unfrozen by construction, and a season total would hide real gaps behind
    them.

  *Done when:*
  - recorded-SQL tests in `test_nfl_repository.py` pass: latest frozen row per
    provider prop, `fetched_at < start_utc`, the full-week condition, and the
    coverage join
  - a local run prints counts only: week 3 frozen rows found, 0 settled,
    because week 3 stats load Tuesday
- [x] **Step 3 - Report** - create `app/backtest/nfl_ranking_check.py`:
  - a pure `report(...)` that prints:
    - the model and P(over) versions graded
    - frozen rows graded, and exclusions by reason
    - coverage
    - the pick funnel
    - one row per slice: picks, weeks, hits, hit rate +/- SE, break-even,
      verdict, and "accruing: n of 200 picks, w of 4 weeks" until the sample
      is fixed
  - `_main` wires the repository reads to core, in the same shape as
    `nfl_prizepicks_lines.py`

  *Done when:*
  - a formatting test on fixed results passes, covering one `insufficient`
    slice and one `adopt` slice
  - a local run prints all four slices as `insufficient` with 0 settled picks
- [x] **Step 4 - Weekly Summary** - add "Report forward ranking check" to
  `nfl-ingest.yml`, after the game-line CLV report, with the same `tee` +
  `$GITHUB_STEP_SUMMARY` block. *Done when:* the YAML parses and the step
  mirrors the existing report steps apart from the command and heading.

## Files / areas

- New: `api/app/core/nfl_ranking_check.py`, `api/app/backtest/nfl_ranking_check.py`,
  `api/tests/test_nfl_ranking_check.py`
- Edit: `api/app/repositories/nfl.py`, `api/tests/test_nfl_repository.py`,
  `.github/workflows/nfl-ingest.yml`
- Reuse:
  - `core/nfl_ranking_rule.py` (`FrozenCall`, `to_pick`, `one_pick_per_bet`,
    `slice_verdict`, `SliceResult`, `BREAK_EVEN_BY_ODDS_TYPE`, `MIN_PICKS`,
    `MIN_WEEKS`)
  - `core/nfl_line_grading.py` (`GradeableLine`, `settle_line`,
    `STAT_COLUMN_BY_MARKET`)
  - `NFL_PROJECTION_MODEL_VERSION` (`core/nfl_projection.py`) and
    `OVER_PROBABILITY_VERSION` (`services/nfl/slate.py`)

## Data / contracts

- No schema change. `nfl_prop_predictions`, `nfl_prop_lines`, stats, snaps
  and games are read only.
- **Load-bearing for 27h:** the slice verdicts this report prints are the only
  gate 27h reads. A slice is usable only at `adopt`, under the model and
  P(over) versions named in the report header.
- `FrozenLine` (core-internal): `line: GradeableLine`,
  `p_over: float | None`, `p_under: float | None`, `model_version: str`,
  `over_probability_version: str | None`.

## Testing

- The test gate is on. Every function in `core/nfl_ranking_check.py` gets
  focused tests with fixed data. The repository reads get recorded-SQL tests,
  and the report formatter gets one test.
- Integration evidence: the Step 2 and Step 3 local runs, which show week 3
  frozen and unsettled.
- Final gate: `.venv\Scripts\python.exe -m pytest` from `api/`. No web change.

## Notes for the AI

- **Do not touch `nfl_ranking_rule.py`.** It is the pre-registration. Import it.
- **First real output is Tuesday 2026-09-29,** when `nfl-ingest.yml` loads week
  3 stats. Until then everything reads `insufficient` with 0 settled picks.
- **Expect rejects.** On week 2 (27i notes), goblin overs went over 64%
  (break-even 75.8%), demon overs 25% (41.3%), and standard model calls hit
  47.9% (57.7%).
- **The sample will be slow.** Week 3 froze P(over) for 250 standard, 685
  goblin and 1,129 demon rows across all segments. Only full-game rows in the
  two shown markets carry P(over), and a pick needs break-even plus 3 points,
  so 200 picks per slice may take many weeks, and some slices may never get
  there.
- **Versions only move forward,** so the latest frozen row of a provider prop
  is always under the newest version it was frozen with. After a version bump,
  older-version rows show up as `wrong_version`, and the new version starts a
  fresh sample.
- The multiple-testing risk is already accepted in 27i (four slices at 2 SE).
  Do not loosen it.
- Standards:
  - `from __future__ import annotations`, `X | None`, no `Any`
  - repositories own SQL
  - `core/` stays pure
  - no em dashes

## Outcome

Shipped as a read-only report; no ranking changed. 27h stays blocked until a
slice reads `adopt`.

First run, 2026-09-26 (`python -m app.backtest.nfl_ranking_check`):

```
frozen rows on completed games 0; excluded: none
coverage, 27a full-game lines with a frozen row: wk 1 0/317, wk 2 0/5380, wk 3 0/324
funnel: calls 0, with P(over) 0, picks 0, one per bet 0
standard over / standard under / goblin over / demon over: accruing, 0 of 200 picks, 0 of 4 weeks
```

- Weeks 1-2 predate freezing, so they are wholly unfrozen by construction.
- Week 3's only completed game (Thursday ATL @ GB) kicked off before the first
  freeze, so it was correctly skipped.
- The first settled week is week 3, after the 2026-09-29 `nfl-ingest.yml` stats
  load. Its coverage line is the check that the Sunday and Monday freezes ran
  on GitHub (pushed 2026-09-26).

**Decided here:** overview open question 24. 27j grades each provider prop's
latest frozen pre-kickoff row at the line it was frozen on, instead of 27i's
"row on the line 27a grades".

**Follow-up:** 27h's build-plan line still names 27a's forward sample as its
gate (overview open question 21). Reword it before `/feature 27h`.
