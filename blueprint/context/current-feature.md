# Feature: Freeze goblin and demon rungs for the volume receptions model

**From build-plan:** feature 49e (NFL market-anchored prop model)
**Status:** not started (spec drafted 2026-11-03, awaiting review)
**Proposed branch:** `feature/nfl-volume-rung-freeze`
**Dependencies:** completed 49a, 49b, 49c and 49d

## Goal

Give the goblin over and demon over slices a forward sample. 49c froze the
`nfl-volume-v1` receptions companion on standard full-game lines only, so 49d
reports those two slices as not frozen. This feature extends the same
companion and the same frozen row to goblin and demon receptions rungs, under
the same model and probability versions, and widens 49d's record so each rung
payout is settled and judged on its own sample.

No refit, no new rule, no new version. `nfl-volume-v1`'s constants, the frozen
anchor `a = -0.0136`, `b = 0.4341`, and 49b's adoption rule are imported
unchanged. Nothing here enables a pick, a rank or a color.

## Design reference

None needed. The displayed companion stays on standard rows (Decision 2), so
the only visible change is the model page's two rung slices moving from "Not
frozen" to progress.

## What the data says (read 2026-11-03, projections and lines only)

Receptions rungs for RB, WR and TE in weeks 3, 5 and 8 (latest line per
provider prop, REG, full game), with the frozen blend applied to each rung's
projection. No outcome was read; these are counts of lines against each
payout's pick threshold.

| Payout | Rungs a week | Clear the pick margin | Bets after one pick per bet |
|---|---|---|---|
| Standard | about 115 | 7 to 8 | 7 to 8 |
| Goblin | about 290 | 0 to 1 | 0 to 1 |
| Demon | about 625 | 112 to 127 | 91 to 102 |

- **Demon over** can reach 200 picks in about 2 to 3 weeks, and the rule's
  4-week minimum then decides the date. It is the only slice that can finish
  this season.
- **Goblin over** will stay empty. Break-even is 75.8%, the blend compresses
  probabilities toward 50%, and almost nothing clears the margin. It still
  freezes (Decision 1), so the slice is defined and the empty result is on
  record.
- **Why demon fills.** The blend is fitted on standard lines only. Applied to
  hard demon lines it pulls probabilities toward 50%, which looks like value
  against a 41.3% break-even. Demon overs have gone over about 24% of the
  time (27g's read of all 2026 demon lines), so a quick and final `reject`
  is the likely outcome. That is an expectation, not a result. It is a valid
  pre-registered test of the extrapolation 49b wrote into its rule ("applied
  unchanged to goblin and demon rungs").

## Timing

| Fact | Value |
|---|---|
| Freeze runs (`nfl-prop-lines.yml`) | Thu 20:00, Sat 23:00, Sun 15:00, Mon 20:00 UTC |
| Last run before week 9's Sunday games | Sat 2026-11-07 23:00 UTC (and Sun 15:00) |
| Week 9 finished, first outcomes | Tue 2026-11-10 15:00 UTC stats load |
| Earliest 4-week rung sample | weeks 9-12, finishing about Tue 2026-12-01 |

- If this lands on `master` before **Saturday 2026-11-07 23:00 UTC**, the
  week 9 Sunday and Monday games freeze their rungs; the Thursday game
  (frozen standard-only on 2026-11-05) does not. Week 9 is then a partial first
  week for the rung slices. Later, the sample starts at week 10 (earliest
  finish about 2026-12-08).
- Nothing is back-filled. A rung line that was not frozen before kickoff is
  never reconstructed.
- **Freeze path first.** Steps 1 to 4 are everything the freeze needs; Steps 5
  to 7 only change reporting. Decision 8 lets the owner merge and push Steps
  1 to 4 early to catch the deadline.

## Scope

- **In:** the serving loader and eligibility for goblin and demon receptions
  lines (RB, WR, TE, full game, REG weeks 1-18); the companion on those v4
  slate lines and a frozen row per rung; 49d's frozen loader, coverage,
  per-payout log-loss rows and slice states for the new rows; copy that stops
  saying "not frozen" once a payout has frozen rows; a neutral display guard.
- **Out:** any refit, threshold, constant or version change; other markets;
  alternate segments; ranking, picking or coloring by this model (27h);
  freezing before kickoff windows that do not exist today; back-fill;
  migrations; workflow, schedule or provider changes; deploy.

## Decisions fixed here (change them at review, not mid-build)

1. **Freeze both goblin and demon,** although goblin will likely stay empty.
   The cost is about 290 rungs a week, and it keeps all four 27j slices
   defined with an honest result.
2. **Display stays standard-only.** Rung companions are in the slate payload
   and in frozen rows, but the web shows the gray volume reference only on
   standard rows, so the player page, game page and board look as they do now.
3. **Coverage counts all three payouts,** labelled as such. Its denominator
   grows from about 115 to about 1,000 eligible props a week; the earlier
   standard-only numbers are not restated.
4. **49b's rule is unchanged,** and a fast `reject` on demon is a legitimate,
   final result for `nfl-volume-anchor-v1`. Choosing to avoid it would mean
   not freezing demon, which this spec does not do.
5. **The verdict module changes only its two shape tuples.**
   `EVALUATED_SLICES` becomes all four slices and `NOT_FROZEN_SLICES` goes
   away; a slice reads "not frozen" from data (no frozen row for its payout),
   not from a constant. No threshold, clause or verdict logic changes. This
   edits a pre-registered file (`b869a492`), so Step 1 is committed as a
   checkpoint with the owner's yes before any rung outcome exists, and a test
   proves the logic is unchanged.
6. **The log-loss clause is judged per payout,** as 49b wrote it ("every line
   of the slice's payout"): standard rows for the standard slices, goblin rows
   for goblin over, demon rows for demon over. Rungs of one player-game are
   correlated, so the existing game clustering applies unchanged.
7. **A partial first week is allowed.** 27i's sample takes whole weeks that
   hold picks; a week with only some games frozen still counts as the first
   period for a rung slice, and coverage shows exactly how much was frozen.
8. **Early merge is allowed.** If the Saturday 2026-11-07 23:00 UTC deadline is
   in reach after Step 4, merge Steps 1 to 4 `--ff-only` and push, then finish
   Steps 5 to 7 on the same item. The owner decides at that point.

## Build loop

Build one step at a time, never the whole feature at once.

1. Explain the step, then implement only that step on the feature branch.
2. Show the diff and prove the done-when with evidence.
3. Run the documented Verify gate; get the owner's review before moving on.
4. After approval, tick the step and offer an optional checkpoint.
   `/complete` owns the work-level commit and merge.

## Build steps

- [ ] **Step 1 - Verdict shape tuples (pure, pre-registered file).** In
  `app/core/nfl_volume_verdict.py`, set `EVALUATED_SLICES` to all four 27j
  slices and remove `NOT_FROZEN_SLICES`, updating the module docstring. Touch
  no threshold, clause, constant or function body.
  *Done when:* tests prove all four slices are evaluated, the slice set equals
  27j's `SLICES`, every verdict test from 49d still passes unchanged, and the
  module still has no numeric literal assigned at module level. A diff against
  `b869a492` shows only the tuples and the docstring changed. Commit as a
  checkpoint with the owner's yes before any rung outcome exists (the first
  rung outcomes arrive with the Tuesday 2026-11-10 stats load), and record the
  hash here. It merges `--ff-only` if later work cites it.

- [ ] **Step 2 - Serve rungs (repository and assembler).** Widen
  `repositories/nfl_volume_serving.py` so the latest line per provider prop is
  selected for standard, goblin and demon (a named tuple of odds types bound as
  a parameter, never an unbounded filter), and let
  `services/nfl/volume.py::_require_eligible` accept those three payouts. Keep
  every other predicate: NFL, REG weeks 1-18, full game, RB/WR/TE, linked
  player and game, strictly before kickoff.
  *Done when:* recorded-SQL tests prove the odds-type parameter, that
  `sport = 'nfl'` still filters every shared alias, that other payouts and
  segments stay excluded, and one row per provider prop; assembler tests prove
  goblin and demon rungs project through `project_player` and
  `anchored_probability` exactly as standard lines do, that the same player-game
  gives distinct references per rung line, and that a market or payout outside
  the three still raises.

- [ ] **Step 3 - Publish and freeze rungs (server).** `build_slate` already
  attaches a companion by line id and the freezer already emits a volume row
  for any line that has one, so this step proves it works for rungs and fixes
  anything that does not. No change to v4 assembly, ordering or counts.
  *Done when:* a mixed fixture with standard, goblin and demon receptions lines
  returns the v4 slate byte-for-byte equal with `volume` removed, and a
  companion on every eligible rung; the freezer yields a v4 row and a volume
  row for each, under distinct conflict keys, with a rerun repeating them;
  started and unknown-start games freeze neither; a slate with no rungs is
  unchanged. A read-only real-data check of the current week shows the rung
  companion count and the `nfl_prop_predictions --dry-run` row count rising by
  about the rung total, with v4 lines byte-identical.

- [ ] **Step 4 - Keep the display standard-only (web).** In `nflVolume.ts`,
  `volumeReferenceModel` and `volumeTableText` return nothing for a line whose
  `oddsType` is not `standard`.
  *Done when:* helper tests prove goblin and demon rows with a companion show
  nothing and standard rows are unchanged, and a browser check of a game page
  and the player page matches their pre-change appearance. This is the last
  step the freeze needs.

- [ ] **Step 5 - Settle rungs in the volume record (repository and service).**
  In `repositories/nfl_volume_ranking.py`, widen the eligible-line predicate to
  the three payouts, binding the same identity (model `nfl-volume-v1`, P(over)
  `nfl-volume-anchor-v1`) before the newest-row pick and in coverage. In
  `services/nfl/volume_ranking.py`, build the log-loss rows per payout, pass
  each slice its own payout's rows, and derive each slice's state from data: a
  payout with no frozen row reads `not_frozen`, otherwise `evaluated`.
  *Done when:* recorded-SQL tests prove the identity filters, strict
  timestamps, ties, and that v4 and Rec Targets rows cannot displace or cover a
  volume rung row; service tests prove the per-payout rows, that the demon slice
  can adopt or reject on its own sample while standard stays accruing, that
  goblin with no picks reads accruing (not a failure), that a payout with no
  frozen row reads not frozen, that one pick per bet still collapses rungs, and
  that v4 and Rec Targets records are unchanged on fixed inputs.

- [ ] **Step 6 - Report and show the rung slices (API, CLI, web copy).** Make
  the API, the ranking CLI and the model page use the data-derived states: the
  "Not frozen" tag appears only for a payout with no frozen row, the not-frozen
  sentence is built from the slices actually in that state, and coverage is
  labelled as covering standard, goblin and demon props. No endpoint or field
  is added.
  *Done when:* API tests show goblin and demon slices evaluated once their rows
  exist and `not_frozen` before; CLI tests show the volume report listing only
  genuinely unfrozen payouts and the new coverage label; helper tests cover the
  copy for zero, partial and full rung freezing; browser checks of the model
  page on desktop and phone show the updated section with no overflow.

- [ ] **Step 7 - Parity, real data and documentation.** Run full Verify and
  `/check`. On clean `master` and this branch, the default v4 report and the
  `nfl-targets-v1` report from the ranking CLI are byte-identical. With real
  frozen rung rows (after the first freeze run that includes this code), read
  the volume record read-only and record counts per payout; if none exist,
  record that and use labelled fixtures. Check database size against the plan
  limit and record the added rows a week. Update the local employer guide.
  *Done when:* the spec records exact results, parity, real or fixture
  evidence, the demon expectation against what happened, and operating notes;
  no row is inserted to manufacture evidence.

## Files / areas

| Area | Files |
|---|---|
| Verdict shape | `api/app/core/nfl_volume_verdict.py` (two tuples), its test |
| Serving | `api/app/repositories/nfl_volume_serving.py`, `api/app/services/nfl/volume.py` and their tests |
| Slate and freeze | `api/app/services/nfl/slate.py`, `prop_predictions.py` (proof and fixes only), `test_nfl_volume_slate.py` |
| Settlement | `api/app/repositories/nfl_volume_ranking.py`, `api/app/services/nfl/volume_ranking.py` and their tests |
| Reporting | `api/app/routers/nfl.py` (no change expected), `api/app/backtest/nfl_ranking_check.py`, `web/src/utils/nflVolumeRecord.ts`, `web/src/components/nfl/model/NflVolumeRecord.tsx` and tests |
| Display guard | `web/src/utils/nflVolume.ts` and test |
| Documentation | this spec's Results; the local employer guide (untracked, never staged) |

## Data / contracts

| Contract | Required behavior |
|---|---|
| Identity | unchanged: model `nfl-volume-v1`, P(over) `nfl-volume-anchor-v1`, anchor `a`, `b` frozen |
| Eligibility | RB, WR, TE; REG weeks 1-18; market `receptions`; full game; odds type in (`standard`, `goblin`, `demon`); linked player and game |
| Frozen key | existing `(prop_line_id, model_version, over_probability_version)`, insert-only; a rung is a different prop line, so it is a different key |
| Frozen payload | unchanged shape, including `q_vol`; `odds_type` already stored in the feature snapshot |
| Rule | 49b's constants by import; log loss judged on the slice's own payout rows; `adopt` needs both clauses |
| Slice state | `evaluated` once any frozen row exists for the payout, else `not_frozen`; four canonical slices kept |
| Coverage | all three payouts, labelled; the standard-only history is not restated |
| Sample | begins at the first rung freeze; no back-fill; a partial first week counts |
| v4 and Rec Targets | readers, versions, samples and verdicts unchanged; v4's frozen readers already exclude `nfl-volume-v1` (49c) |

## Testing

The test gate is on. Every step with logic ships focused pytest or Vitest tests
with fixed timestamps and recorded SQL; no provider call, no shared database
mutation, no new runner. Mixed fixtures include the same player-game with
standard, goblin and demon lines, rungs under v4, Rec Targets and volume
identities, newer unfrozen lines, ties, equal and post-kickoff rows, a payout
with no frozen rows, pushes and an unfinished week. The final gate is
`npm --prefix web run verify && cd api && python -m pytest` from the root with
the API venv first on PATH. Manual path: open a game page, the player page and
`/#/nfl/model` and compare against their current look.

## Notes for the AI

- Do not implement during `/feature`. The model, anchor and rule do not change;
  a changed value is a new version and a new sample.
- Receptions is a v4 market and rungs are v4 lines too. Select the volume model
  and probability version before any newest-row selection, as 49c and 49d do.
- The slate already attaches companions by line id; do not add a second code
  path for rungs. Widen the loader and prove the rest.
- Step 1 edits a pre-registered file. Keep the diff to the two tuples and the
  docstring, and get the owner's yes before committing it.
- The 2025 holdout is not read; its count stays at 9.
- Merge `--ff-only` if a pre-registration hash is cited (Step 1).
- No em dashes in new content (the writing hook flags real characters, so avoid
  unicode escapes that expand to them). Comment the why only.
- Windows: run Python from the API venv in the main checkout; the worktree has
  no `api/app/.env`, so pass the DB URL through the environment, never print it.

## Results

(Filled in as steps complete.)
