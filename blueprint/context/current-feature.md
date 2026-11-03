# Feature: Forward verdict for the NFL volume receptions model

**From build-plan:** feature 49d (NFL market-anchored prop model)
**Status:** not started (spec drafted 2026-11-03, awaiting review)
**Proposed branch:** `feature/nfl-volume-forward-verdict`
**Dependencies:** completed 49a, 49b and 49c

## Goal

Settle the frozen `nfl-volume-v1` receptions predictions under their own
identity (model `nfl-volume-v1`, P(over) `nfl-volume-anchor-v1`) and show their
coverage, settled-call funnel, pick progress and log-loss progress beside v4
and Rec Targets on `/nfl/model`, the ranking CLI and the weekly workflow. Each
slice gets the one-time verdict 49b registered, once its sample is fixed.

This feature applies a rule; it does not write one. Every threshold is 49b's
(27i's pick rule plus the log-loss clause), imported, never copied or tuned.
Nothing here enables a pick, a rank or a color.

## Design reference

Extend the existing `/nfl/model` page, `NflRankingSlices` and
`web/src/pages/nfl-model.css`, with the same gray reference styling 39d used
for Rec Targets. A reporting addition, not a redesign; no `prototypes/`
directory is needed.

## Timing and what this feature can and cannot show

| Fact | Value (checked 2026-11-03) |
|---|---|
| First freeze run after 49c reached `master` | Thu 2026-11-05 20:00 UTC (`nfl-prop-lines.yml`) |
| Week 9 first kickoff | 2026-11-06 01:15 UTC |
| Week 9 counts as finished | after the Tuesday stats load, Tue 2026-11-10 15:00 UTC (every game completed and stats loaded) |
| Earliest 4-week sample | weeks 9-12, so about 2026-12-08 |
| Regular season ends | week 18 |

- **Real frozen rows do not exist yet.** The first volume rows are written
  Thursday. Steps 1 and 2 can be built on fixtures now; the real-data check in
  Step 7 waits for them.
- **Week 9 may be only partly frozen** (the Thursday game before the Thursday
  run, the rest after). Coverage shows exactly that; nothing is back-filled.

## The sample-size problem, stated up front

49b's pick rule needs **200 picks in a slice** across at least 4 weeks, and
49b fixed it unchanged. Receptions has about 100 standard full-game lines a
week. On 49b's own fit data (in-sample, so optimistic) 57 of 698 lines cleared
the pick margin, 8.2%, which is about 7 picks a week split across over and
under. Over weeks 9-18 that is roughly 70 picks in total, so each of the
standard over and standard under slices reaches perhaps 25 to 50, **well short
of 200 this season.** Expect `insufficient` all of 2026 for both pick slices.

What this feature does about it, without touching the rule:

- Reports **pick progress** ("n of 200 picks, weeks k of 4") per slice, so the
  shortfall is visible, never read as a failure.
- Reports **clause 2 (log loss) on its own,** on every standard line, where the
  sample is about 100 a week and an answer is reachable this season. It is
  progress, not a verdict: the verdict still needs both clauses.
- Says plainly that a changed threshold would be a new version and a new
  sample (49b), and that doing it after week 9 outcomes exist is not allowed.
  If the owner wants a lower pick count, it has to be decided **before the
  first week 9 outcome is read (the Tuesday 2026-11-10 stats load)** and
  registered as a new version, not edited here. This spec keeps 49b's rule.

## Scope

49c froze **standard full-game receptions only**. The four 27j slices are
standard over, standard under, goblin over and demon over. Only the first two
have frozen predictions, so:

- **Standard over and standard under** are evaluated.
- **Goblin over and demon over** are reported as **not frozen** (not
  `insufficient`, which would imply a sample is accruing). Freezing those
  rungs is a separate change to 49c's eligibility and is not part of this
  feature; Decision 1 below.

## In scope

- **A pure verdict** composing 49b's two clauses (pick rule and log loss)
  from imported constants, with tests, committed as a checkpoint before any
  week 9 outcome is read.
- **A read-only volume frozen-line loader and coverage query,** separate from
  v4's and Rec Targets', settling `receptions` against the weekly stat and
  carrying each frozen row's raw `q_vol` from its feature snapshot.
- **A third report identity** through the shared ranking machinery, selected
  independently before any latest-row selection or coverage counting.
- **The log-loss block** per standard slice: blend, raw volume and constant 0.5
  log loss, paired differences with SEs clustered by game, weeks won.
- **API, CLI, workflow and web** exposure of the third record, with the same
  isolation as 39d.
- Parity proof for v4 and Rec Targets, a running-app check, the employer guide.

## Out of scope

- Changing any 49b constant, the 27i rule, 49a's `nfl-volume-v1` constants or
  the frozen anchor `a`, `b`. No new rule, no threshold tuning.
- Freezing goblin or demon rungs, projecting any other market, or adding any
  second candidate.
- Replaying or reconstructing weeks before the first frozen row; grading a
  current projection as a frozen forecast.
- 27h: ranking, picking or coloring lines by this model. Adoption is only a
  recorded verdict here; turning it into a ranking needs its own item.
- Changes to v4's or Rec Targets' loaders, versions, samples or verdicts.
- Migrations, new tables, snapshot formats, ingest or freeze changes,
  production data writes, remote workflow dispatch, deployment or push.

## Decisions fixed here (change them at review, not mid-build)

1. **Goblin and demon slices read "not frozen,"** and this feature stays
   standard-only. Extending the freeze to those rungs is a new plan item (I
   would propose it as 49e after review); it would start its own sample.
2. **Keep 49b's rule unchanged,** accept `insufficient` for the pick slices
   this season, and show the shortfall honestly. A lower threshold is a new
   version and must be registered before the 2026-11-10 stats load.
3. **Log-loss progress is shown separately** from the verdict, with its own
   weeks-won count, so the one clause with power this season is visible.
4. **`adopt` requires both clauses** on the fixed verdict sample, exactly as
   49b wrote it. A decided slice's verdict is final for `nfl-volume-anchor-v1`.

## Build loop

Build one step at a time, never the whole feature at once.

1. Explain the step, then implement only that step on the feature branch.
2. Show the diff and prove the done-when with evidence.
3. Run the documented Verify gate; get the owner's review before moving on.
4. After approval, tick the step and offer an optional checkpoint.
   `/complete` owns the work-level commit and merge.

## Build steps

- [x] **Step 1 - The verdict (pure).** Add `app/core/nfl_volume_verdict.py`.
  It imports 49b's constants (`ANCHOR_PICK_RULE`, `LOG_LOSS_*`,
  `NFL_VOLUME_ANCHOR_VERSION`) and 27i's `verdict_sample`, `one_pick_per_bet`
  and break-evens. It adds no constant of its own. It provides
  `log_loss_clause(rows, sample_weeks)` and `slice_verdict(picks, rows)`:
  `adopt` only if 27i's rule is `adopt` **and** the blend's mean log loss
  beats both the raw `q_vol` and a constant 0.5, each by more than 2 SE of
  the paired difference clustered by game, and in at least 3 of the 4 sample
  weeks; `insufficient` while the pick sample is not fixed; otherwise
  `reject`. Rows carry the blended over and under, the raw `q_vol`, the push
  flag, game id and week; pushes are excluded from log loss.
  *Done when:* unit tests prove each clause fails on its own and the pick rule
  failing alone also blocks `adopt`; a verdict never reads `adopt` before the
  sample is fixed; later weeks never change a fixed verdict; ties and pushes
  are excluded; SEs are clustered by game; an empty sample is ordinary
  (`insufficient`, n=0); and no constant in the module differs from 49b's.

- [ ] **Step 2 - Pre-registration checkpoint.** With the owner's yes in chat,
  commit Step 1 before any volume outcome is joined to a prediction. Record
  its hash here. Target: before Tuesday 2026-11-10 15:00 UTC. It merges
  `--ff-only` if later work cites it.
  *Done when:* the commit exists, precedes all later steps, and its hash is
  recorded in this file.

- [ ] **Step 3 - Load volume frozen rows and coverage (repository).** Add
  batched read-only queries in a sibling of `nfl_targets_ranking.py`. Require
  NFL, REG weeks 1-18, completed games, linked RB/WR/TE, full-game standard
  receptions lines and a known kickoff. Restrict frozen rows to model
  `nfl-volume-v1` **and** P(over) version `nfl-volume-anchor-v1` before
  selecting each provider prop's latest eligible frozen prediction (line
  fetch time desc, line id desc, generated time desc, prediction id desc),
  with line `fetched_at` and prediction `generated_at` strictly before
  kickoff. Join the weekly `receptions`, player-row presence, snaps and
  game-stats presence for settlement, and read `q_vol` from the feature
  snapshot. Coverage: denominator is each eligible prop's latest pre-kickoff
  line; numerator is a prop with at least one frozen row of this exact
  identity. v4's and Rec Targets' readers stay unchanged.
  *Done when:* recorded-SQL and row-mapping tests prove sport, market, model
  and version isolation, strict timestamps, deterministic ties, that another
  model's row cannot displace or cover a volume row, that a later unfrozen
  line does not discard an earlier frozen prediction, and that a missing or
  non-numeric `q_vol` fails closed to an exclusion, never a value.

- [ ] **Step 4 - Build the record (service).** Add a report-only
  `NflVolumeRankingSource` outside `PROP_SOURCES`, route
  `ranking_source("nfl-volume-v1")` to it, and build the third record through
  the shared machinery, adding the log-loss block per standard slice and the
  `not frozen` state for goblin and demon. Add an independent single-flight
  cache entry for the new identity.
  *Done when:* mixed-model fixtures give three separate records; the volume
  record carries `nfl-volume-anchor-v1` (nonnull), n of 200 pick progress,
  weeks, and the log-loss block; unfinished weeks cannot fix a sample; empty
  data is valid; a cached failure never crosses a model or season; on fixed
  inputs and time every v4 and Rec Targets record field equals its
  before-change value.

- [ ] **Step 5 - Expose it (API).** Extend the allowlisted `model_version`
  selector on `GET /nfl/model/ranking` to accept `nfl-volume-v1`, keeping v4
  the default. Add an optional `logLoss` object on the response (null for the
  other models). Keep the router thin and the error handling consistent.
  *Done when:* API evidence shows the default and explicit v4 selectors
  return the same record, `nfl-volume-v1` returns its own identity, the
  nonnull probability version and the log-loss block, an empty sample returns
  200, an unsupported selector returns 422, and a loader failure returns the
  existing generic 503 without touching the other cached reports.
  Serialization unit checks cover the added optional field.

- [ ] **Step 6 - Report it from the CLI and workflow.** Add
  `nfl-volume-v1` to `--model-version` and include it in `all`, in the order
  v4, Rec Targets, volume. Default omission stays v4-only. Change only the
  existing weekly ranking command's `all` output; keep its order, Summary and
  schedule. Invalid selectors fail before database loading; a failed report
  fails the command.
  *Done when:* synthetic CLI checks show unchanged default content, isolated
  counts for all three models, pick progress and log-loss wording, and
  "goblin and demon not frozen"; no workflow is dispatched.

- [ ] **Step 7 - Show it on the model page (web).** Add the selector to the
  typed transport and query keys. Render the volume record as a third
  labelled section with its own states: standard over and under progress
  ("n of 200 picks, k of 4 weeks"), the log-loss block, goblin and demon as
  not frozen, and a gray "no verdict yet" or the final verdict with its
  sample. No green, no pick language; keep the page summary scoped to v4.
  *Done when:* helper tests cover labels, zero picks, the not-frozen rows,
  progress wording and summary scope; existing v4 and Rec Targets fixtures
  keep their values; browser checks show the section on desktop and phone
  with independent loading, error and empty states.

- [ ] **Step 8 - Parity, real data and documentation.** Run full Verify and
  `/check`. On the same captured inputs and clock confirm v4 and Rec Targets
  records are unchanged. With real frozen volume rows (after the first freeze
  run), read the three records read-only and record the counts; if none
  exist, record that honestly and use labelled fixtures. Keep the added loads
  bounded for the 512 MB host. Update the local employer guide.
  *Done when:* the spec records exact results, parity, real or fixture
  evidence, and the expected-`insufficient` explanation; no row is inserted.

## Files / areas

| Area | Files |
|---|---|
| Verdict | `api/app/core/nfl_volume_verdict.py` (new) |
| Repository | a sibling of `api/app/repositories/nfl_targets_ranking.py` (new) |
| Service | `api/app/services/nfl/track_record.py`, a report-only volume source, minimal adaptations in `services/prop_ranking.py` |
| API | `api/app/routers/nfl.py`, `api/app/schemas/nfl.py` |
| CLI and schedule | `api/app/backtest/nfl_ranking_check.py`, the ranking step in `.github/workflows/nfl-ingest.yml` |
| Web | `web/src/types/nfl.ts`, `api/nfl.ts`, the model track-record hook, `pages/NflModelPage.tsx`, `components/nfl/model/NflRankingSlices.tsx`, `utils/nflTrackRecord.ts` and helper tests |
| Tests | verdict, repository, record, API, CLI and web helper tests; v4 and Rec Targets regression fixtures |
| Documentation | this spec's Results; the local employer guide (untracked, never staged) |

## Data / contracts

Load-bearing for 27h and any later work:

| Contract | Required behavior |
|---|---|
| Identity | model `nfl-volume-v1`, P(over) `nfl-volume-anchor-v1`; select both before `DISTINCT ON` and coverage counting |
| Rule | 49b's constants by import: pick margin 0.03, 200 picks, 4 weeks, 2 SE; log loss against raw `q_vol` and 0.5, 2 SE, 3 of 4 weeks; `adopt` needs both |
| Slices | standard over and standard under evaluated; goblin over and demon over `not frozen` |
| Settlement | the frozen row's stored line against the weekly `receptions`; push excluded from log loss; no stat row and positive snaps is zero, neither is void, per the existing NFL convention |
| Frozen snapshot keys read | `q_vol`, `p_push`, `anchor_a`, `anchor_b`, `line`; written by 49c, so these names must not change |
| Finished weeks | `get_finished_weeks`: every REG game completed and stats loaded |
| Response | existing camelCase ranking fields; optional `logLoss` (null for other models); canonical four slices kept, two marked `not frozen` |
| Cache | keyed by season, model and probability version; failures isolated |
| Compatibility | no schema change, no writes; defaults, v4 and Rec Targets values unchanged |

## Testing

The test gate is on. Every step with logic ships focused pytest or Vitest
tests with fixed timestamps and recorded SQL; no provider call, no shared
database mutation, no new runner. Mixed fixtures include the same provider id
under v4, Rec Targets and volume identities, newer unfrozen lines, ties,
wrong sport, market, payout and position, equal and post-kickoff rows, missing
`q_vol`, pushes, zero receptions, and an unfinished week. Verify gate from the
root with the API venv first on PATH:
`npm --prefix web run verify && cd api && python -m pytest`. Manual path: run
the API and web, open `/#/nfl/model`, and inspect all three sections.

## Notes for the AI

- Do not implement during `/feature`. The rule is 49b's; this feature must add
  no threshold, and a changed value would be a new version and a new sample.
- Receptions is a v4 market. The volume loader must select the volume model
  and probability version before any newest-row selection, as 49c pinned the
  v4 side.
- Reuse 39d's pattern (report-only source, model selector, separate cache,
  CLI `all`, labelled sections); the new parts are the log-loss clause, the
  nonnull probability version and the `not frozen` slices.
- The 2025 holdout is not read here; its count stays at 9.
- Merge `--ff-only` if a pre-registration hash is cited (Step 2).
- No em dashes in new content. Comment the why only.
- Windows: run Python from the API venv in the main checkout; the worktree has
  no `api/app/.env`, so pass the DB URL through the environment, never print it.

## Results

(Filled in as steps complete.)
