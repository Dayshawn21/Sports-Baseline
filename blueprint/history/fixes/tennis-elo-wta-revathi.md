# Current Feature

**Feature:** Candidate tennis ELO blocked by a renumbered WTA player (Rajeshwaran Revathi); close shadow v2, start v3
**Type:** Fix
**Branch:** `fix/tennis-elo-wta-revathi`

## The problem

The `Daily Candidate Tennis ELO` job in `tennis-box-scores.yml` has failed on
the last three scheduled runs (2026-11-04, 11-05, 11-06; latest run
42264390493, last success 41691147820 on 11-03). The step
`python -m app.ingest.tennis_elo --write` exits 1 by design:

```
Tracked candidates: 1566; unmapped provider players: 1128; ambiguous provider players: 2; identity conflicts: 1
BLOCKED identity: local 2679 has multiple provider IDs: [('WTA', '266652'), ('WTA', '266722')]
BLOCKED, 0 inserted
```

The last success reported `ambiguous provider players: 0; identity
conflicts: 0`. No ELO code or registry CSV changed between the runs; only the
downloaded TennisMyLife data did.

Provider rows (all WTA files 2021-2026 plus `wta_ongoing_tourneys.csv`,
downloaded 2026-11-06):

| ID | File | Rows |
|---|---|---|
| `266652` | `2025_wta.csv` | Chennai 2025-10-27, R32 loss to Bhamidipaty; IND; age 16.375 |
| `266722` | `wta_ongoing_tourneys.csv` | Chennai 2026-11-03, R32 win over Kawa, R16 win over Falkowska, QF loss to Montgomery; IND; no age |

Exact name "Maaya Rajeshwaran Revathi" on both, same country, never in the same
event, and neither ID appears in any other year or for any other name. The
2026 Chennai event entered the ongoing file during the 11-03 week, which
matches the first failure on 11-04. This is the same ongoing-file renumbering
recorded in `blueprint/history/fixes/tennis-elo-wta-identities.md`.

Nothing is written while blocked, and served ELO is unaffected. Each blocked
UTC day leaves no candidate snapshot and cannot be backfilled.

## The fix

Part A is one reviewed data row. Part B closes the shadow experiment the row
would otherwise break (audit finding F-41).

**Part A - alias row**

- `api/app/ingest/data/tennis_elo_identities.csv`: add
  `WTA,266722,266652,verified,<evidence>`. `266652` is canonical because it is
  the older ID, matching the 10-28 fix.

**Part B - close `tennis-elo-source-v2`, open `tennis-elo-source-v3`**

`tennis_elo_experiment.json` pins the registry digest, and v2 has been active
since 2026-10-29T20:00:36Z. The alias changes the digest, so
`ExperimentConfig.check_runtime` would raise `Pinned ELO experiment inputs
changed; accrual stopped for review`. The `--scheduled` freeze in
`tennis-predictions.yml` would then go red and v2 would stop. The data README
and the 41b rule forbid re-pinning a running experiment. So, as in
`blueprint/history/fixes/tennis-elo-experiment-v2.md` (`dc22c98a`):

| Pin | v2 | v3 |
|---|---|---|
| Experiment | `tennis-elo-source-v2` | `tennis-elo-source-v3` |
| Identity normalization | `tennis-elo-identities-v2` | `tennis-elo-identities-v3` (registry with the Revathi alias) |
| Coefficients, gates, incumbent versions | as pinned | unchanged; re-pinned from the runtime |
| Rule (sample, margin, SE, coverage) | 41b table | identical; only `experiment` changes `RULE_SHA256` |
| `SPEC_APPROVED_ON` | 2026-10-29 | date the owner approves this spec |
| Activation | 2026-10-29T20:00:36Z | `null` until a separately reviewed timestamp |

v2 closes as stopped, no verdict. Its rows stay unchanged and are never
pooled with v3 or scored.

Must not break:

- Stored v1 and v2 comparison and freeze-cycle rows: no updates, deletes or
  rescoring. v2 outcomes and losses are not viewed.
- Registry rules in `app/core/tennis_elo.py`: no alias chains, no duplicates,
  no canonical ID that is itself an alias.
- Production ELO (`player_elo`), the ensemble, and any stored candidate or
  comparison row. Linking adds this player from today on; it does not rescore
  or backfill.

Changing the CSV changes the workflow cache key, so the next run downloads
fresh originals. That is intended.

## Build steps

- [x] **Step 1 - Alias row** - add the verified row with the evidence above.
  *Done when:* `pytest tests/test_tennis_elo_identities.py` passes, and the
  registry loads with 64 aliases. A local dry run (`python -m
  app.ingest.tennis_elo`, read-only) reporting `identity conflicts: 0` is
  run only if a database connection is available and the owner approves it.

- [x] **Step 2 - Record v2's final state (read-only).** Run
  `python -m app.backtest.tennis_elo --count` (counts only, no `--score`) and
  read-only counts by `experiment_version`: pairs per group, distinct
  kickoff days, coverage attempts, last frozen cycle, and confirm every v2
  row carries the v2 config hash.
  *Done when:* the counts are in Evidence and the owner approves closing v2
  with no verdict. (Counts recorded 2026-11-06; owner approved closing v2 with no verdict 2026-11-06.)

- [x] **Step 2b - Make the registry bytes the same on Windows and the runner.**
  Step 2 found that v2's `identity_sha256` was hashed from CRLF bytes (see
  Evidence), so v2 never matched the runner. Add
  `api/app/ingest/data/tennis_elo_*.csv text eol=lf` to `.gitattributes`,
  so a Windows checkout reads the same LF bytes as Linux. The blobs and the
  runner digest do not change. Add a test that fails when either registry
  CSV in the working tree contains a carriage return.
  *Done when:* after re-checking out the two CSVs here, the local
  `load_identity_registry().sha256` equals the LF digest the runner logs
  (`8bc7357b...` before the alias), and the new test passes.

- [x] **Step 3 - Pin v3 (code, tests, migration file).**
  - `EXPERIMENT = "tennis-elo-source-v3"` in `app/core/tennis_elo_report.py`.
  - `IDENTITY_VERSION = "tennis-elo-identities-v3"` in `app/core/tennis_elo.py`.
  - `SPEC_APPROVED_ON` in `app/services/tennis/elo_comparison.py` to the
    approval date.
  - Migration `0052` replacing `ck_elo_cycle_experiment` with v1, v2 and v3;
    downgrade refuses if any v3 rows exist, then restores v1 and v2.
    `tests/test_migration_0052.py` mirrors `test_migration_0051.py`.
  - Rewrite `tennis_elo_experiment.json` for v3 from `runtime_pins`, with
    `activated_at: null`.
  - README "Experiment history": close v2, add v3.
  - Update tests that hardcode v2 (comparison test clock moves 8 days with
    `SPEC_APPROVED_ON`, as in the v2 precedent).
  - Add `test_committed_experiment_pins_match_the_runtime_the_scheduled_freeze_checks`,
    so CI fails on any pin the runner would reject (it would have caught v2).
  *Done when:* pytest passes; a local
  `python -m app.ingest.tennis_elo_comparison --dry-run` reports the
  experiment inactive with no pin error (needs the owner's yes); `git diff`
  shows no rule value change other than `experiment`.

- [x] **Step 4 - Apply migration 0052 (owner, shared Neon).** One
  `alembic -c <ini> upgrade head`, after a separate yes.
  *Done when:* the constraint admits v3, and v1 and v2 row counts match
  Step 2.

- [x] **Step 5 - Activate v3 (post-push run pending) (separate approval).** Record a reviewed
  `activated_at` in the JSON. The first eligible day is the next full UTC
  day after activation and `SPEC_APPROVED_ON`. The push must land before
  the next 11:00 UTC candidate refresh so that day's snapshot carries the
  v3 identity digest.
  *Done when:* `check_runtime` passes with the v3 hash and the next
  scheduled `Tennis Predictions and Shadow Freeze` run is green.

## Evidence

### Step 2 - v2 final state (2026-11-06, read-only)

`python -m app.backtest.tennis_elo --count` (counts only; outcomes not
inspected) and read-only SQL by `experiment_version`:

- v2: first eligible UTC day 2026-10-30; frozen 0, mature 0, eligible
  attempts 0 in every group. **No v2 freeze cycle or comparison row exists.**
- v1 unchanged: 6 freeze cycles (last `cycle_key` 2026-10-27 18:00Z), 52
  comparisons (kickoffs 2026-10-22 18:45Z to 2026-10-26 03:00Z).
- `ck_elo_cycle_experiment` admits v1 and v2 (migration `0051`).

Why v2 is empty: `Tennis Predictions and Shadow Freeze` has failed every
scheduled run from 2026-10-28 through 2026-11-05 with `Pinned ELO experiment
inputs changed; accrual stopped for review` (latest 42106286599). Since
2026-10-30 that is not the alias fix but a bad pin:

| Registry bytes | `identity_sha256` |
|---|---|
| Pinned in `tennis_elo_experiment.json` (v2) | `96eed61d...` |
| Main Windows checkout (`w/crlf`) | `96eed61d...` |
| Git blob, what the Linux runner reads (`i/lf`) | `8bc7357b...` (matches the 11-03 runner log) |

The digest hashes the raw CSV bytes, and `core.autocrlf=true` checks the
CSVs out with CRLF on Windows. v2's pins were taken from the Windows
runtime, so the runner never matched. Closing v2 loses no data.

### Step 3 - v3 pins (2026-11-06)

- `identity_sha256` `7b320922...` from LF registry bytes with
  `tennis-elo-identities-v3`; coefficient, gate and model pins unchanged;
  `activated_at: null`.
- `pytest -k "tennis_elo or migration_005"`: 341 passed, plus the new pin
  guard test.
- Full Verify passed (web 1235 tests and build; API 5822).
- Local `tennis_elo_comparison --dry-run` (owner-approved, read-only): no pin
  error; config `91423f43...`; active for accrual False, first eligible day
  pending activation; 28 attempts, 0 storable; `DRY RUN: 0 inserted`. The
  missing daily snapshot is expected while today's refresh is blocked.

### Step 4 - migration applied (2026-11-06, owner-approved)

- Neon moved `0051 -> 0052`; `alembic_version` is `0052`.
- `ck_elo_cycle_experiment` is now
  `experiment_version = ANY (ARRAY['tennis-elo-source-v1', 'tennis-elo-source-v2', 'tennis-elo-source-v3'])`.
- v1 unchanged: 6 freeze cycles, 52 comparisons; v2 still 0 rows (matches
  Step 2).

### Step 5 - activation recorded (2026-11-06, owner-approved)

- `activated_at` 2026-11-06T19:56:33.770792Z; config hash `475d99ec...0696`;
  `check_runtime` passes; first eligible UTC day 2026-11-07.
- Pending after push: the push must land before the 2026-11-07 11:00 UTC
  candidate refresh, or that day's attempts are recorded as missing-snapshot
  coverage misses. Then the next shadow freeze run is green with the v3 hash.

## Verify

- Full Verify command passes:
  `npm --prefix web run verify && cd api && python -m pytest`.
- After merge and an approved push: the next scheduled box-score run, or a
  manual dispatch with `job: tennis-elo`, goes green through "Share original
  daily ELO inputs", and the next `Tennis Predictions and Shadow Freeze` run
  is green with the v3 config hash. A real `--write` happens only in those
  workflows, never locally.

## Notes

- Interview guide (if present on this machine): extend the 41b passage, the
  forward test restarted again as v3 after a second identity fix.
- The WTA ongoing file has now renumbered players twice. Each reviewed alias
  costs an experiment restart; a durable approach is a separate change.

## Findings

### tennis-elo-wta-revathi/F-41 [P1] closed - The Revathi alias changes the registry digest pinned by the active tennis-elo-source-v2 experiment

**File:** api/app/ingest/data/tennis_elo_identities.csv:65; api/app/services/tennis/elo_comparison.py:94
**Found:** 2026-11-06 by /audit (scope: current; lenses: all)
**Why it matters:**
- `tennis_elo_experiment.json` pins `identity_sha256` and v2 is active (`activated_at` 2026-10-29T20:00:36Z). The new alias row changes the registry digest, so `run_comparison` raises `Pinned ELO experiment inputs changed; accrual stopped for review` at `config.check_runtime`.
- After a push, the `tennis_elo_comparison --scheduled` step in `tennis-predictions.yml` would go red instead of the candidate refresh, and v2 would stop accruing. `api/app/ingest/data/README.md` (Experiment history) says the next post-activation registry change closes v2, which needs a reviewed close and a v3 start (the 2026-10-29 precedent `dc22c98a` added migration `0051` and an activation).
- The fix spec's "must not break 41b's pre-registered rule" missed this.
- Not fixing it is not neutral either: while the alias is missing, the candidate refresh stays blocked and v2 records only missing-snapshot attempts each day.
**Suggested fix:** do not push the alias alone. Either pair it with a reviewed v2 close and v3 start (like `dc22c98a`) merged before the same push, or hold the alias and batch it with later alias fixes, accepting more blocked days.
**Resolution:** Fixed and re-reviewed 2026-11-06 (/audit, scope: current) on `fix/tennis-elo-wta-revathi`. The owner chose to close v2 and start v3. Step 2 found v2 had no rows at all: its pin was hashed from a CRLF Windows checkout, so every freeze from 2026-10-30 failed. The repair adds `.gitattributes` `eol=lf` for the registry CSVs, `tennis-elo-identities-v3` / `tennis-elo-source-v3`, `SPEC_APPROVED_ON` 2026-11-06, migration `0052` (applied to Neon; v1 6 cycles / 52 comparisons unchanged, v2 0), v3 pins from LF bytes, and activation 2026-11-06T19:56:33Z. The re-review saw no rule value change beyond `experiment`. `test_committed_experiment_pins_match_the_runtime_the_scheduled_freeze_checks` and the local `--dry-run` both pass `check_runtime`. The new LF requirement adds its own finding (F-42, still open in the ledger); it is not a defect in this repair.
