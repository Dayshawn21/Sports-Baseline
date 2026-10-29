# Current Feature

## Close tennis ELO shadow v1 and start v2 after the identity fix

**Type:** Fix
**Branch:** `fix/tennis-elo-experiment-v2`

## The problem

The scheduled job `Freeze Candidate Tennis ELO Shadow` (in
`tennis-predictions.yml`) has failed on 2026-10-28 and 2026-10-29 with:

`ValueError: Pinned ELO experiment inputs changed; accrual stopped for review`

`ExperimentConfig.check_runtime` (`api/app/services/tennis/elo_comparison.py`)
compares `tennis_elo_experiment.json` with the runtime. The fix `e4fe60b7`
(WTA identity conflicts) added three aliases to `tennis_elo_identities.csv`
and one override to `tennis_elo_local_overrides.csv`. That changed the
registry digest, so `identity_sha256` no longer matches the pin. The guard is
working as designed. No v1 pairs have been frozen since 2026-10-27.

**Why not just re-pin v1:**

- 41b's pre-registered rule: "A change stops accrual for review; never pool
  versions or silently restart the experiment."
- `api/app/ingest/data/README.md`: after activation, a registry change "needs
  a new normalization version and a separate experiment review", and the pin
  file is never updated to match a changed runtime.
- In code, a new pin changes the config hash and
  `check_experiment_continuity` rejects it, because stored v1 pairs and
  attempts carry the old hash.

**Why not revert the CSV rows:** without them, the daily candidate ELO
refresh stops on four identity conflicts again. The freeze needs a complete
candidate snapshot for the current day, so it would still fail.

## The fix

Close `tennis-elo-source-v1` as **stopped with no verdict** and open
`tennis-elo-source-v2` under the same pre-registered rule, with fresh pins and
a fresh activation. v1 rows stay in the database unchanged. v1 and v2 are never
pooled.

| Pin | v1 | v2 |
|---|---|---|
| Experiment | `tennis-elo-source-v1` | `tennis-elo-source-v2` |
| Identity normalization | `tennis-elo-identities-v1` | `tennis-elo-identities-v2` (registry as of `e4fe60b7`) |
| Coefficients, gates, incumbent versions | as pinned | unchanged; re-pinned from the runtime |
| Rule (sample, margin, SE, coverage) | 41b table | identical; only the `experiment` field changes `RULE_SHA256` |
| Spec approval date (`SPEC_APPROVED_ON`) | 2026-10-20 | date the owner approves this spec |
| Activation | 2026-10-21T02:25:51Z | `null` until a separately reviewed timestamp |
| Sample | accrued through 2026-10-27 | starts at zero on the first full UTC day after activation |

**Must not break:**

- Stored v1 comparison and freeze-cycle rows: no updates, deletes or rescoring.
- The pre-registered rule values in `tennis_elo_report.py`, and holdout
  discipline: v1 outcomes are not viewed before v2 is pinned.
- Production ELO, the ensemble, served predictions, and the
  `Daily Prediction Persistence` job.
- Candidate ELO snapshot history. A new identity version applies to new days only.

## Decisions to review

1. **Close v1 without a verdict.** v1 had about a week of accrual against a
   300-pair, 14-day floor, so it could never mature. Its counts are recorded
   (Step 1). Its losses are never viewed.
2. **Same rule for v2.** Changing any rule value after seeing data is not
   allowed. Only the experiment name and its dates change.
3. **The job stays red until Step 2 lands.** With v2 pinned and
   `activated_at: null`, the freeze reports "Freeze skipped: experiment
   inactive" and succeeds. It accrues only after activation (Step 4).

## Build steps

- [x] **Step 1 - Record v1's final state (read-only).** Run
  `python -m app.backtest.tennis_elo --count` (counts only, no `--score`)
  and capture pairs per group, distinct kickoff days, coverage attempts, and
  the last frozen cycle. Confirm that the stored hashes are all the v1 config
  hash. Add the counts to this spec's evidence.
  *Done when:* the counts are recorded and the owner approves closing v1
  with no verdict.

- [x] **Step 2 - Pin v2 (code, tests, migration file).**
  - Define `EXPERIMENT = "tennis-elo-source-v2"` in one place
    (`app/core/tennis_elo_report.py`) and import it in
    `app/repositories/tennis_elo_comparison.py` instead of duplicating the
    string. Code that reads `EXPERIMENT` (the backtest report dir, the
    continuity check) then follows.
  - Bump `IDENTITY_VERSION` to `tennis-elo-identities-v2` in `app/core/tennis_elo.py`.
  - Set `SPEC_APPROVED_ON` to this spec's approval date.
  - New Alembic migration (next free number at implement time; check the
    other worktrees too) that replaces `ck_elo_cycle_experiment` with
    `experiment_version IN ('tennis-elo-source-v1', 'tennis-elo-source-v2')`.
    Downgrade restores the v1-only check and refuses if any v2 rows exist.
  - Rewrite `tennis_elo_experiment.json` for v2, with hashes taken from
    `runtime_pins` and `activated_at: null`.
  - Update the README's "Changing this registry" and "Shadow experiment
    pins" sections with v1's closure and the v2 pins.
  - Update the tests that hardcode v1.
  *Done when:* pytest passes. A local
  `python -m app.ingest.tennis_elo_comparison --dry-run` reports that the
  experiment is inactive and raises no pin error. `git diff` shows no
  change to any rule value other than `experiment`.

- [x] **Step 3 - Apply the migration (owner, shared Neon).** Run one
  `alembic -c <ini> upgrade head` command, after a separate yes.
  *Done when:* the new constraint is in place, and v1 row counts match
  Step 1.

- [x] **Step 4 - Activate v2 (separate approval; post-push run pending).** Merge and push first, so
  the runner has v2. Then record a reviewed `activated_at` timestamp in the
  JSON and commit it. The first eligible day is the next full UTC day after
  both activation and `SPEC_APPROVED_ON`.
  *Done when:* the next scheduled `Tennis Predictions and Shadow Freeze` run
  is green and its log shows the v2 config hash. On the first eligible day,
  v2 pairs or coverage attempts appear.

## Evidence

### Step 1 - v1 final state (2026-10-29, read-only)

`python -m app.backtest.tennis_elo --count` (counts only; outcomes and losses
not inspected), plus read-only SQL by `experiment_version`:

| Group | Frozen | Mature | Mature days | Candidate available |
|---|---|---|---|---|
| ATP | 11 | 11 | 3 | 11/12 |
| WTA | 29 | 25 | 3 | 25/32 |
| ATP_CHALLENGER | 12 | 12 | 4 | 12/14 |

- First eligible UTC day 2026-10-22; mature through 2026-10-25.
- 52 comparison rows (kickoffs 2026-10-22 18:45Z to 2026-10-26 03:00Z) and
  6 freeze cycles (last `cycle_key` 2026-10-27 18:00Z), all
  `tennis-elo-source-v1`.
- Every stored pair and attempt carries one config hash,
  `bdab3a64...e2a5`, which matches the committed v1 pin file.
- Excluded captures none; invalid frozen payloads 0.
- Far below the 300-pair, 14-day floor in every group: v1 closes as
  stopped, no verdict.

### Step 3 - migration applied (2026-10-29)

- `alembic upgrade head`: `0050 -> 0051` on Neon.
- `ck_elo_cycle_experiment` is now
  `experiment_version = ANY (ARRAY['tennis-elo-source-v1', 'tennis-elo-source-v2'])`.
- v1 unchanged: 6 freeze cycles, 52 comparisons (matches Step 1).

### Step 4 - activation recorded (2026-10-29)

- Owner approved activating on the branch before `/complete` (one merge and
  one push instead of two).
- `activated_at` 2026-10-29T20:00:36.089865Z; config hash `dbb08e1f...a6ed`;
  `check_runtime` passes; first eligible UTC day 2026-10-30.
- `--scheduled` today still skips (first full UTC day not begun).
- Pending after push: the 2026-10-30 run is green with the v2 hash. The push
  must land before the 11:00 UTC candidate ELO job on 2026-10-30, so that
  day's snapshot carries the v2 identity digest. Otherwise that day's
  attempts are recorded as missing-snapshot coverage misses.

## Verify

- `npm --prefix web run verify && cd api && python -m pytest`
- `gh run list --workflow "Tennis Predictions and Shadow Freeze" --limit 3`
  shows success after the push (Step 2: inactive skip; Step 4: accrual).
- `python -m app.backtest.tennis_elo --count` shows v2 starting from zero.
  v1 rows are untouched (direct read-only count by `experiment_version`).

## Notes

- If the interview guide exists on this machine, update its 41b passage: the
  forward test restarted as v2 after an identity-registry fix, and v1 was
  closed with no verdict. This is a good example of pre-registration catching
  input drift.
- Future identity fixes will stop v2 the same way. Each one needs this same
  review: close the experiment and open a new version. Batch reviewed alias
  fixes where possible.
