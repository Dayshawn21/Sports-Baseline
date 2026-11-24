# Feature: Serve and freeze the NFL volume receptions model

**From build-plan:** feature 49c (NFL market-anchored prop model)
**Status:** complete (2026-11-03)
**Proposed branch:** `feature/nfl-volume-serve-freeze`
**Dependencies:** completed 49a (`nfl-volume-v1`) and 49b (`nfl-volume-anchor-v1`)

## Goal

Show `nfl-volume-v1`'s receptions projection and its anchored P(over) beside
v4 on the existing NFL slate, prop board, game and player flows, gray, and
freeze it before kickoff after each line snapshot, so 27j can grade it as its
own sample (49d reads that sample). Nothing about v4's rows, probabilities or
forward sample changes.

The model is **receptions only** (RB, WR, TE). The six markets 49a rejected
are never projected, served or frozen. The P(over) comes from 49b's frozen
blend (`a = -0.0136`, `b = 0.4341`), version `nfl-volume-anchor-v1`. It is
gray and never a pick or a rank until 49d reads `adopt` for its own slice.

## Design reference

A data addition to existing tables, rows and the evidence drawer; no mockup or
theme port. No `prototypes/` directory is needed. Reuse the gray reference
styling that 39c gave Rec Targets.

## Timing and what this feature can and cannot cover

- Today is 2026-11-03. Week 9 kicks off Thursday 2026-11-05 8:15 PM ET. Six
  reviewed steps cannot land before that, so **week 9 stays a replay**, as 49b
  disclosed. The earliest realistic first frozen week is **week 10**; the
  verdict sample for 49d starts there.
- Replayed weeks 9 and earlier can still be graded by 49d from stored lines,
  but they are labelled replay, never frozen.
- The freeze is only as good as the pipeline: slate input rows must exist at
  the line snapshot. The workflow order (ingest, freeze, slate snapshot) is
  checked in Step 6.

## The hazard this spec exists to handle

**Receptions is already a v4 market.** Unlike Rec Targets in 39c, a second
frozen row for the same PrizePicks line would sit beside v4's. Three places
would then mix the two models unless they are pinned first:

1. `get_frozen_gradeable_lines` takes the newest frozen row per provider prop
   (`ORDER BY ... p.generated_at DESC`), filtered by market only. A later
   `nfl-volume-v1` row would **replace v4's row** in 27j's sample.
2. `get_frozen_coverage` and the pending-week readers count frozen rows the
   same way.
3. The web keys rows by `lineId`. Two slate lines with one line id would
   collide.

So the volume model is served as a **companion on the v4 receptions row**
(Decision 1 below), not as a second slate line, and the v4 frozen readers are
pinned to v4's versions before any volume row exists.

## In scope

- **Pin v4's frozen readers** to exclude the volume model version (Step 1),
  before any volume row can exist.
- **A live volume loader** (repository): each linked, standard, full-game
  receptions line for RB/WR/TE in the requested REG week, strictly before
  kickoff, with the player's prior-season and current-season history and the
  game's expected team total and margin.
- **A pure assembler** that runs `project_player` with
  `NFL_VOLUME_V1_PARAMETERS` and `anchored_probability` with
  `NFL_VOLUME_ANCHOR_PARAMETERS`, returning one companion object per line.
- **A nullable `volume` object on the v4 receptions slate line** and a second
  frozen row per line from it, under `nfl-volume-v1` /
  `nfl-volume-anchor-v1`.
- **Gray display** of the volume reference in the existing prop board, game and
  player flows and the evidence drawer.
- Verification: v4 payload and sample parity, idempotent freezing with test
  doubles, a dry run, and operation notes.

## Out of scope

- The six rejected markets, and any change to `nfl-volume-v1` or
  `nfl-volume-anchor-v1` constants, grids, rules or verdicts. No refit.
- 49d: settling, ranking or reporting the volume sample, 27j's report,
  `/nfl/model` slices, and any `adopt` or `reject` verdict.
- Changing v4's markets, coefficients, `nfl-pover-v1`, its fit tables, 27i's
  ranking rule, Rec Targets, or any historical frozen row.
- Goblin and demon rungs: only standard full-game lines are projected and
  frozen (the anchor was fitted on standard lines only). Their slices belong
  to 49d's reading of stored lines.
- New providers, workflows, schedules, routes, tables or migrations.
- Deploy, push, remote workflow runs or production database writes during
  verification.
- Any pick badge, recommendation rank, green signal or best-pick use of the
  volume numbers.

## Decisions fixed here (change them at review, not mid-build)

1. **Companion, not a second line.** `NflSlateLineSchema` gains an optional,
   nullable `volume` field on the v4 receptions row only. No new endpoint,
   no mandatory field, and old stored slate snapshots (which lack the field)
   stay readable.
2. **Projection value is the mean,** like v4, so the pages compare like with
   like. The median and the push probability are in the object and in the
   frozen feature snapshot. The gap shown is `mean - line`, gray, worded as a
   reference gap.
3. **Served P(over) is the anchored value** (`anchored_probability`), with its
   version `nfl-volume-anchor-v1`; the frozen row stores `p_over`, `p_under`
   and the model/P(over) versions. The raw `q_vol` is kept in the feature
   snapshot for 49d's log-loss clause.
4. **First frozen week is 10 at the earliest by default, week 9 if this is
   pushed in time** (see Step 6 Results: the first freeze run is Thursday
   2026-11-05 20:00 UTC); nothing is back-filled into frozen predictions.

## Build loop

Build one step at a time, never the whole feature at once.

1. Explain the step, then implement only that step.
2. Show the diff, explain it and prove the done-when.
3. Run the documented Verify gate; get the owner's review before moving on.
4. After approval, tick the step and offer an optional checkpoint.
   `/complete` owns the work-level commit and merge.

## Build steps

- [x] **Step 1 - Pin v4's frozen readers (server).** Restrict the frozen
  gradeable loader, coverage and pending-week readers in
  `repositories/nfl.py` so a row under `nfl-volume-v1` can never be selected,
  counted or displace v4's row. Apply the restriction **before** the
  newest-row selection. Express it as an exclusion of the new volume model
  version (`nfl-volume-v1`), so every historical v4 row, whatever its
  version, is still read exactly as today.
  *Done when:* recorded-SQL tests show the model-version predicate inside the
  `DISTINCT ON` CTE of each reader; a synthetic fixture with a v4 row and a
  later `nfl-volume-v1` row on one line returns the v4 row; existing frozen
  readers return identical output on fixtures without volume rows; no volume
  row is needed to run the test.

- [x] **Step 2 - Live volume inputs (repository, dormant).** Add
  `repositories/nfl_volume_serving.py` with a typed serving input per line:
  line, player, position, team, opponent, home side, game start, the game's
  `spread_line` and `total_line`, and the player's completed REG history for
  the current and previous season with team pass and rush attempts per game.
  Select the latest eligible linked standard full-game receptions line per
  provider prop for the REG season and week, strictly before kickoff when
  kickoff is known, with deterministic timestamp and id ties. History is
  batch-loaded for the lines' player ids, strictly before `(season, week)`,
  and bounded below by `max(season - 1, VOLUME_FIRST_HISTORY_SEASON)`.
  Keep it unused by the slate.
  *Done when:* recorded-SQL tests prove `sport = 'nfl'` on every shared-table
  alias, REG and completed filters on history, no current or future-week
  stats, the named floor, one query per table (no per-player queries),
  position restricted to RB/WR/TE, market `receptions`, odds type
  `standard`, segment `full_game`; null stats stay null; a future scheduled
  game loads without outcome stats.

- [x] **Step 3 - Assemble the companion and its freeze contract (pure).** Add
  `services/nfl/volume.py` with `volume_reference(row)` returning the
  companion or `None`. It calls `project_player` and `anchored_probability`
  through `require_anchorable("receptions", "nfl-volume-v1")`; a projection
  refusal (`NO_HISTORY`, `NO_OPPORTUNITIES`, `NO_FIT`), a missing game line or
  a non-finite value yields `None` with a reason flag, never a zero or 0.5.
  The companion carries: projection (mean), median, line, gap, `q_vol`,
  anchored `p_over`, `p_under`, `p_push`, the model version, the P(over)
  version, quality flags and the history-length evidence. Extend
  `prediction_row` to emit a second row from it.
  *Done when:* fixed-input tests show exact parity with `project_player` and
  `anchored_probability`; the over, under and push probabilities sum to 1;
  rookies, no-history and missing-line cases return `None` with a reason; a
  QB or a non-receptions market is refused; a valid zero projection is kept;
  frozen serialization carries both versions and the raw `q_vol` and does
  not fabricate v4 adjustments.

- [x] **Step 4 - Publish and freeze (server).** Add the nullable `volume`
  object to the slate schema and fill it in `build_slate` for v4 receptions
  lines; make `freezable_games` emit the companion row beside the v4 row.
  Leave the v4 assembly, ordering, counts and `NflPropSource`'s report
  identity untouched.
  *Done when:* a mixed fixture returns the v4 slate **byte-for-byte equal**
  with `volume` removed; the freezer yields a v4 row and a volume row per
  eligible line under their own versions; started and unknown-start games
  are not frozen; reruns insert nothing new (insert-on-conflict-do-nothing
  with the existing key); a slate with no volume rows is unchanged; legacy
  slate snapshots without the field still validate.

- [x] **Step 5 - Show the volume reference (web).** Add the optional field to
  the TypeScript types and helpers. On receptions rows show a neutral gray
  "Volume model" reference in the drawer and the game and player current-line
  flows (projection, median, line, gap, P(over) and its not-yet-validated
  note), with no OVER or UNDER pick badge, no recommendation rank, no green,
  no use in best picks or the slate digest. An undefined `volume` (old
  snapshot, ineligible row) renders nothing extra. Keys stay `lineId`.
  *Done when:* helper tests cover labels, absent field, zero projection,
  null probability and no pick or rank text; v4 fixtures keep their values
  and presentation; browser checks on `/nfl`, `/nfl/board` (Props),
  `/nfl/game/:id` and `/nfl/player/:id` show the reference only on
  eligible receptions rows and nothing duplicated.

- [x] **Step 6 - Integration, operations and parity.** Run the full Verify gate
  and `/check`. With the same inputs and clock, compare a slate with and
  without the companion: v4 lines, counts and freeze inputs identical.
  Inspect the NFL workflows that write slate inputs: ingest, then
  `python -m app.ingest.nfl_prop_predictions --dry-run`, then the slate
  snapshot, and record the order and the first expected frozen week. Exercise
  insert idempotency with test doubles, never the shared database. Confirm
  the history load stays bounded for the 512 MB host (it runs in the ingest
  and snapshot job, never on a production request). Update the local employer
  guide to say the volume reference is served and frozen gray and not yet
  graded, never claiming deployment or an edge.
  *Done when:* the spec records exact automated results, v4 parity, the
  dry-run counts or the explicit environmental gap, and the first expected
  frozen week; read-only verification writes no frozen rows or snapshots.

## Files / areas

| Area | Files |
|---|---|
| v4 boundary | `api/app/repositories/nfl.py` (frozen loader, coverage, pending weeks) |
| Serving input | `api/app/repositories/nfl_volume_serving.py` (new) |
| Companion | `api/app/services/nfl/volume.py` (new), `slate.py`, `prop_predictions.py`, `api/app/schemas/nfl.py` |
| Pure inputs reused | `nfl_volume_projection.py`, `nfl_volume_anchor.py` (unchanged) |
| Web | `web/src/types/nfl.ts`, the prop board, card and detail helpers and the drawer, with adjacent helper tests |
| Tests | repository and slate tests, freeze tests, v4 parity fixtures, web helper tests |
| Operations | `.github/workflows` NFL ingest chain (inspected, no new job) |
| Documentation | this spec's evidence; the local employer guide (untracked, never staged) |

## Data / contracts

Load-bearing for 49d:

| Contract | Required behavior |
|---|---|
| Versions | model `nfl-volume-v1`, P(over) `nfl-volume-anchor-v1`; v4's `opponent-dvp-tg-blend-usage-snap-v4` / `nfl-pover-v1` untouched |
| Eligibility | RB, WR, TE; REG weeks 1-18; market `receptions`; full game; odds type `standard`; linked player and game |
| Frozen key | existing `(prop_line_id, model_version, over_probability_version)`, insert-only; two rows per eligible line |
| Frozen payload | projection (mean), `p_over`, `p_under` (anchored), edge (gap), flags; feature snapshot adds median, `p_push`, raw `q_vol`, anchor `a`, `b`, history counts |
| Slate shape | optional nullable `volume` on the v4 receptions line; no mandatory field changes |
| v4 sample | the frozen loader, coverage and pending-week readers exclude `nfl-volume-v1` before newest-row selection |
| Replay | weeks before the first frozen week are replay, never frozen |

No history is backfilled into frozen predictions. Production keeps serving
stored slate snapshots and returns the established unavailable response when
one is missing; it never builds this slate in the 512 MB request process.

## Testing

The test gate is on. Steps 1 to 5 add logic and ship pytest or Vitest tests in
the same diff; no new runner. Repository tests record SQL with fixed rows and
clocks. Mixed-model tests compare the same inputs with and without volume and
assert v4 is identical. Cover: kickoff equal to now, started and unknown-start
games, missing game line, rookies, duplicate freeze attempts, old snapshots
without `volume`, and zero projections. No test queries a provider or the
shared database. Final gate from the root:
`npm --prefix web run verify && cd api && python -m pytest`. Manual path: run
the API and web, open the slate, Props board, an eligible game and player, and
inspect the gray reference, the drawer note and the
`/nfl/slate?season=<season>&week=<week>` payload.

## Notes for the AI

- Do not implement during `/feature`. Step 1 comes first and stands alone: no
  volume row may exist before the v4 readers are pinned.
- Receptions is a v4 market. Never filter by market alone to separate the two
  models; filter by model version, before newest-row selection.
- `app/core/` stays pure. The new modules import `nfl_volume_projection` and
  `nfl_volume_anchor`; they change neither.
- The six rejected markets must not appear in any loop, enum, flag or table.
- Reuse 39c's pattern (dedicated assembler, mixed-model freeze, neutral
  wording), but note it was a separate market; here the volume numbers are a
  companion, so v4 must remain byte-identical with `volume` removed.
- Merge `--ff-only` if a pre-registration hash is cited later; this feature
  cites none of its own (the rule and constants are 49b's, `33c53e25`).
- No em dashes in new content. Comment the why only.
- Windows: run Python from the API venv in the main checkout; the worktree has
  no `api/app/.env`, so pass the DB URL through the environment, never print it.

## Results

### Step 6 - integration and operation (2026-11-03)

**Automated gate.** Full Verify after Step 5, from this worktree with the
dummy `DATABASE_URL`: web typecheck, 1,125 web tests and build pass; 5,384 API
tests pass. No code changed after that run.

**v4 parity on real data (read-only).** Week 9 built twice from the shared
database with one clock, with and without the volume rows: 2,559 lines each,
32 companions on the first build, and after removing the field the two
payloads are byte-identical.

**Freeze dry run.** `python -m app.ingest.nfl_prop_predictions --dry-run`
(nothing written): week 9, `frozen=2591`, which is the 2,559 existing lines
plus 32 volume rows. Idempotency is covered with test doubles: each line has
two distinct conflict keys and a rerun repeats them, so the existing
`ON CONFLICT ... DO NOTHING` inserts nothing new. No frozen rows or snapshots
were written.

**Pipeline order.** `.github/workflows/nfl-prop-lines.yml` runs the PrizePicks
line snapshot, then `python -m app.ingest.nfl_prop_predictions`, then
`python -m app.ingest.nfl_slate_snapshot`. Its cron entries (months 1, 2, 9-12)
are Thursday 20:00, Saturday 23:00, Sunday 15:00 and Monday 20:00 UTC. The
other NFL workflows only refresh the stored slate. The freeze builds the slate
on a GitHub Actions runner, never in the 512 MB request process.

**First expected frozen week (correction to the timing note above).** The
first freeze run after the code reaches `master` is what starts the sample.
If this is merged and pushed before Thursday 2026-11-05 20:00 UTC, that run
freezes the Thursday-night game of week 9 five hours before kickoff, and the
Saturday and Sunday runs freeze the rest, so **week 9 can be a true freeze**,
not a replay. If it lands later, the first frozen games are the next
pre-kickoff runs. Hosted pages show the companion only after the next slate
snapshot, because stored copies from before this change have no `volume`.

**Cost.** Building the real week 9 slate took 10.9 s with the volume load
against 7.2 s without it (+3.7 s, local, warm connection). The volume history
load is two batched queries over the current and previous season for the
slate's receptions players. This is a timing comparison, not a measured
memory figure; production never builds the slate.

**Other checks.** No production request path imports the new modules except
through `build_slate`, which production reads only from stored snapshots. v4
frozen readers exclude `nfl-volume-v1` (Step 1), so v4's forward sample is
unaffected once volume rows exist. The local employer guide (ignored,
untracked, never staged) now describes the volume reference as served and
frozen gray locally, not deployed and not graded.
