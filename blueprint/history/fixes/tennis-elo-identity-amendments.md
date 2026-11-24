# Current Feature

**Feature:** Append-only identity amendments so a reviewed WTA alias no longer restarts the tennis ELO shadow experiment
**Type:** Fix
**Branch:** `fix/tennis-elo-identity-amendments`
**Status:** Completed 2026-11-06 as a dormant change (Steps 2 to 4). Spec
approved by the owner 2026-11-06 with the dormant-then-switch timing. Step 1's
data half and Step 5 (the v4 switch) are deferred by the owner's choice; Step 5
becomes its own fix at the next forced restart and needs separate yeses for
the Neon migration and activation.

## The problem

TennisMyLife's `wta_ongoing_tourneys.csv` has renumbered WTA players twice in
16 days:

| Date | Players | Shape | Record |
|---|---|---|---|
| 2026-10-28 | Ibragimova, Kostovic, Sun (+ Pedone spelling) | Ongoing file re-emitted annual matches under new IDs; Guangzhou 2026-10-26 only under new IDs | `blueprint/history/fixes/tennis-elo-wta-identities.md` |
| 2026-11-06 | Rajeshwaran Revathi `266722 -> 266652` | New 2026 Chennai matches only, under a new ID; no duplicate copy anywhere | `blueprint/history/fixes/tennis-elo-wta-revathi.md` |

Each time the cost was the same chain:

1. `map_players` finds a conflict and the daily candidate refresh blocks the
   whole day (`BLOCKED, 0 inserted`). That day has no snapshot and cannot be
   backfilled.
2. The reviewed alias row changes the registry bytes, so `identity_sha256`
   (`load_identity_registry`, hashed from both CSVs and `IDENTITY_VERSION`)
   no longer matches `tennis_elo_experiment.json`.
3. `ExperimentConfig.check_runtime` stops accrual, and the README plus the
   41b identity amendment forbid re-pinning a running experiment. So the
   experiment closes with no verdict and a new version opens: constants,
   migration (`0051`, `0052`), activation, push before 11:00 UTC.

v1 closed with 52 pairs; v2 closed with none; v3 activated
2026-11-06T19:56:33Z. The 41b sample needs 300 pairs and 14 kickoff days per
group, and v1 accrued about 7 WTA pairs a day before the season winds down.
WTA cannot mature before 2027, and every new ongoing event can renumber
someone. **Under the current procedure the experiment is likely to keep
restarting and never reach a verdict.** That is the real defect.

## Options considered

### A. Deduplicate renumbered ongoing-file copies before identity mapping

Treat two rows with the same `namespace`, `family`, `tourney_id`, `round`,
`match_num`, date, score and names, differing only in player IDs, as one match
and infer `new -> old`.

Rejected as the fix:

- **It does not cover the cases that happen.** Revathi had no duplicate copy:
  the new ID appeared only on new matches. Guangzhou 2026-10-26 was also only
  under new IDs. Both would still conflict and block.
- **It is an unreviewed identity merge.** Inferred aliases come from whatever
  bytes the provider serves that day. Pinning the inference code does not pin
  the identities, so the identity input would drift daily without review.
  That is the "silent" change the 41b rule forbids, and it bypasses the
  registry's evidence standard (birth date, country, never same event).
- Open question for Step 1: in today's code a same-`source_key` copy with
  different IDs raises `Conflicting ELO match copies` (a contract error), yet
  the 10-28 run reported identity conflicts. Step 1 confirms which path the
  real rows hit. The answer does not change the recommendation.

Worth keeping only as a **review aid** (a dry-run line suggesting a candidate
alias with its evidence), which is a separate follow-up, not part of this fix.

### B. Pin an identity contract instead of the raw registry digest (recommended)

Freeze the registry as it stands at activation (the **base**), pin its digest
exactly as now, and allow only **append-only, verified amendments** in a
separate file, under rules declared before activation and checked by code.
Anything else still stops accrual.

### C. Keep the restart procedure

Correct and already proven, but per the arithmetic above it likely prevents
any verdict. Remains the fallback if the owner rejects B's argument below.

## The fix (Option B)

### Files

- `tennis_elo_identities.csv`, `tennis_elo_local_overrides.csv`: the base.
  Frozen for the life of the experiment. `identity_sha256` keeps its current
  meaning and computation (base bytes + `IDENTITY_VERSION`).
- New `api/app/ingest/data/tennis_elo_identity_amendments.csv`, LF via the
  existing `.gitattributes` glob (`tennis_elo_*.csv`):
  `namespace,kind,provider_id,target,effective_from,evidence`
  - `kind=alias`: `provider_id` is a raw ID, `target` its canonical ID.
  - `kind=override`: `provider_id` is a canonical ID, `target` a local
    `players.id`.
  - No `status` column: only verified rows are committed here.
- `tennis_elo_experiment.json` gains one pin,
  `"identity_contract": "tennis-elo-identity-contract-v1"`. It enters
  `pins()` and therefore `config.sha256`. The amendments file itself is not
  pinned.

### Contract v1 (pure, `app/core/tennis_elo.py`)

An amendment is admitted only if all hold; otherwise the runtime raises the
same `Pinned ELO experiment inputs changed; accrual stopped for review`:

1. Base digest equals the pin (today's check, unchanged).
2. An alias's raw ID is not a base alias, base canonical, or base override
   key. **No base mapping can change or be removed.**
3. An alias's target is not an alias anywhere (no chains); same namespace;
   no duplicate keys across base and amendments.
4. An override's key is not already overridden, and its local ID is not the
   target of any other override.
5. `effective_from` is strictly after the activation UTC day, and rows are in
   non-decreasing `effective_from` order (append-only by position).
6. The merged registry for a day keeps every `parse_identity_registry` rule
   (enforced directly by `check_amendments`), and normalization creates no
   self-match (enforced at replay by `normalize_identities`).
7. The base has no `proposed` rows (added in Step 2). A proposed row has no
   effect, so the parsed base keeps no record of its raw ID and the contract
   could not tell whether an amendment re-decides it.

The **effective registry for UTC day D** is base plus amendments with
`effective_from <= D`. Snapshot day D always replays with exactly that set.

### Durable append-only proof

The Actions cache is disposable, so the proof lives in the database:

- The daily manifest records `amendments_sha256` and `amendment_count` for
  its effective set.
- Each frozen pair payload and each coverage attempt records the same two
  values (jsonb fields; no column change needed, to confirm in Step 2).
- Continuity check (beside `check_experiment_continuity`): for every stored
  `(count k, digest h)` of this experiment, the first k rows of today's file
  must hash to h. An edited, reordered or deleted amendment stops accrual.
- `validated_candidates` rejects a snapshot whose manifest amendments digest
  differs from the effective set for its day (`invalid_daily_snapshot`, a
  one-day coverage miss, not an experiment stop). Committing a row dated
  today after the 11:00 refresh therefore costs that day only. The README
  procedure says: `effective_from` is always a future UTC day.

### Pre-registration (rule changes, applied only at the version switch)

`RULE` in `tennis_elo_report.py` gains:

- `"identity": "frozen_base_plus_append_only_verified_amendments_next_utc_day"`
- Context only (never decisive, consistent with the Context row): G1 and G2
  also reported excluding pairs where either player's canonical key is
  touched by an amendment, with the count.

No other rule value changes. The verdict, floors, margin, SE and coverage
gate are untouched.

## Argument against the 41b pre-registration rule

The rule: *"A change stops accrual for review; never pool versions or
silently restart the experiment."* The 41b identity amendment adds: registry
changes after activation require a separate version/experiment review.

**Why B is not a silent re-pin:**

- What is pinned is declared before activation: the base bytes, the contract
  version, and the admission rules. An amendment that satisfies the contract
  is a pre-declared, permitted input, not a change to a pinned input. The
  amendment's existence is not silent either: it is a reviewed commit with
  evidence, its digest is stored on every pair, and the append-only proof is
  in the database.
- Anything outside the contract (editing or deleting any row, changing a
  canonical, a proposed row, a judgment-based exception like Ilagan, a rule or
  coefficient change) still stops accrual exactly as today.

**Why B is not pooling versions:**

- All pairs of one experiment share one config hash and one contract. Pairs
  differ only in the effective registry for their day, which is already true
  of the provider bytes themselves: the experiment replays a different
  download every day under one version. Identity amendments become the same
  kind of daily input variation, bounded and recorded.
- The pre-registered sensitivity line lets the verdict be read with and
  without amended players, decided before any outcome is seen.

**Where B does weaken the rule, honestly stated:**

- It gives the owner a discretionary lever during the experiment: whether
  and when to add an alias. Mitigations, all already in force or added here:
  outcomes and losses are never viewed before the once-only `--score`; an
  amendment needs the README's mechanical four-point evidence standard with
  no exceptions; it can only add, never alter; and in practice it is forced,
  because without it the refresh blocks every day.
- So the owner must accept, explicitly and once, that for **v4 onward** the
  identity pin means "base plus contract", not "registry bytes".

**What must not happen:**

- B is never applied to v3. v3 was activated under the bytes pin; switching
  its meaning in flight would be the silent re-pin the rule forbids. B takes
  effect only in a new experiment version, opened under the existing
  close-and-restart procedure. That restart is the last one caused by a
  verified alias.
- v1, v2, v3 rows are never pooled with v4, rescored, or edited.

## Timing (owner decision)

| Choice | Cost | Recommendation |
|---|---|---|
| **Dormant then switch:** build and merge B so it is inert while the experiment JSON lacks `identity_contract` (v3 behavior and `config.sha256` byte-identical). When the next renumbering forces v3 closed, open v4 with the contract | No extra restart; v3 keeps accruing until the next alias | **Recommended** |
| Switch now: close v3 as soon as B lands | Loses whatever v3 accrued since 2026-11-07; one avoidable restart | Only if the owner wants certainty before WTA's 2027 season |

The `RULE` edits and the experiment rename change `RULE_SHA256`, so they land
only in the switch commit, never in the dormant merge.

## Must not break

- v3 while dormant: `check_runtime`, `config.sha256`, `RULE_SHA256`, report
  pins and the scheduled freeze behave byte-for-byte as now.
- Stored v1/v2/v3 comparison, freeze-cycle and snapshot rows: no updates,
  deletes, rescoring or pooling.
- Production ELO (`player_elo`), the ensemble, served predictions.
- Registry rules: no chains, no duplicates, canonical never an alias, one
  local player per override, never across ATP/WTA.
- The fail-closed refresh: any conflict not covered by an effective amendment
  still blocks the day (per-player quarantine is out of scope, see Notes).

## Build steps

- [ ] **Step 1 - Evidence (read-only).** *(Code half done; the 10-28 data
  check is deferred, needing a download yes. It does not change the design.)* Confirm, from the runner's Actions
  cache or a fresh download (the download needs the owner's yes), which code
  path the 10-28 re-emitted copies hit (contract error vs identity conflict),
  and record it here. Confirm pair payload and attempt jsonb can carry two
  new fields without a schema change.
  *Done when:* both answers are in Evidence.

- [x] **Step 2 - Contract in core (dormant).** Pure parse/validate/merge of
  amendments and the effective-registry-for-day function in
  `app/core/tennis_elo.py`; prefix-digest helper. Empty amendments file
  committed.
  *Done when:* the core tests below pass and nothing reads the file yet.

- [x] **Step 3a - Wire the refresh (dormant).** `load_identity_registry`
  also loads the amendments; a pure `resolve_identity` picks the effective
  set for the day from the experiment JSON's `identity_contract` and
  activation; the refresh replays and maps with it, and its manifest records
  the amendment count and digest only when the contract is pinned (dormant
  manifests stay byte-identical).
  *Done when:* tests pass, a dormant run's manifest is unchanged, and a
  non-empty amendments file without the pin stops the refresh.

- [x] **Step 3b - Wire the freeze (dormant).** `ExperimentConfig` accepts an
  optional `identity_contract` pin; `validated_candidates` checks the
  manifest's amendment fields; pairs and attempts store the two fields only
  when pinned; the append-only continuity check runs only when pinned.
  While the experiment JSON has no `identity_contract`, a **non-empty**
  amendments file is an error in both the refresh and the freeze. Otherwise
  the refresh could apply an amendment to v3's ratings while v3's pin still
  passes, which is exactly the silent change the rule forbids.
  *Done when:* tests pass, and a test proves the committed v3 JSON yields the
  same `config.sha256` and `RULE_SHA256` as before this branch.

- [x] **Step 4 - Docs.** README: "Shadow experiment pins" and "Changing this
  registry" describe the amendment procedure (future `effective_from`,
  evidence standard, no exceptions, what still restarts).
  *Done when:* reviewed.

- [ ] **Step 5 - Deferred to its own fix.** *Switch to v4 (separate approval, at the next forced
  restart or now per the timing decision).** Close v3 per the established
  procedure (read-only counts, no verdict); `EXPERIMENT`
  `tennis-elo-source-v4`, `IDENTITY_VERSION` v4 with the new alias folded into
  the **base**, `SPEC_APPROVED_ON`, `RULE` additions, migration `0053`
  (constraint admits v4; downgrade refuses with v4 rows), JSON with
  `identity_contract`, Neon upgrade (separate yes), activation (separate yes).
  *Done when:* the same done-when as the v3 fix, plus the next alias goes in
  as an amendment with no pin error.

## Test plan

Core (`tests/test_tennis_elo_identities.py`, pure, fixed dates):

- Accepts a valid alias append and a valid override append; the effective
  registry for day D includes only rows with `effective_from <= D`.
- Rejects, each with the stop error: raw ID already a base alias or base
  canonical; a row that would change a base mapping; chain (target is an
  alias); cross-namespace; duplicate; override key already overridden;
  override local ID already targeted; `effective_from` on or before the
  activation day; out-of-order `effective_from`; a `status` column; a merge
  that creates a self-match.
- Prefix digest: append passes; edit, reorder or delete of any of the first
  k rows fails.

Comparison and ingest (`tests/test_tennis_elo_comparison*.py`):

- Contract pinned, base unchanged, amendment appended: `check_runtime` and
  continuity pass.
- Base CSV edited: stops exactly as today.
- `identity_contract` value mismatch: stops.
- JSON without `identity_contract`: an empty amendments file leaves v3
  behavior unchanged, and a non-empty one stops both the refresh and the
  freeze; v3 `config.sha256` and `RULE_SHA256` equal the committed values.
- Snapshot manifest amendments digest differs from the effective set:
  `invalid_daily_snapshot`.
- Extend `test_committed_experiment_pins_match_the_runtime_the_scheduled_freeze_checks`
  to load the amendments file through the contract.
- Existing LF test covers the new CSV through the same glob.

Report (`tests/test_tennis_elo_report*.py`, at Step 5):

- Sensitivity line excludes touched pairs and reports the count; the verdict
  is identical with or without it.

## Evidence

### Step 1 - jsonb fields (2026-11-06, read-only code review)

- `tennis_elo_comparisons.payload` and `tennis_elo_freeze_cycles.attempts` are
  `JSONB` with only `jsonb_typeof` checks (`0047_tennis_elo_comparisons.py`),
  so two new keys need **no migration**.
- Writers serialize the whole dataclass (`_json(asdict(pair))`, attempts
  likewise) into the payload and into `plan_sha256`
  (`repositories/tennis_elo_comparison.py`). Readers rebuild with
  `FrozenComparison(**record)` and `CoverageAttempt(**item)`
  (`repositories/tennis_elo_report.py`), so older rows without the keys
  decode only if the new fields have defaults.
- **Refinement for Step 3:** adding plain dataclass fields would put
  `amendment_count: 0` and `amendments_sha256: null` into every v3 row
  written after the dormant merge. v3 rows would then have two payload
  shapes inside one experiment, which breaks "v3 byte-for-byte as now". So
  the two keys are written **only when the contract is pinned** and are
  absent otherwise. Defaults keep v1-v3 rows decoding unchanged. Step 3 adds
  a test that a dormant-mode pair and attempt serialize to exactly today's
  keys.

### Step 3a - refresh wiring (2026-11-06)

- The Actions cache key in `tennis-box-scores.yml` and
  `tennis-predictions.yml` hashes `core/tennis_elo.py` and
  `ingest/tennis_elo.py`, so the dormant merge changes the key. A push
  between the 11:00 UTC refresh and the 13:30 UTC freeze would make that
  day's freeze miss the cache and record coverage misses. **Push outside
  that window.**
- The key does not hash the amendments file. Under the contract, an
  amendment appended mid-day already fails closed (the manifest's digest
  no longer matches, a one-day coverage miss). Adding the file to both keys
  is a Step 3b workflow edit for review.

### Step 3b - freeze wiring (2026-11-06)

- `test_committed_v3_hashes_are_unchanged_while_the_identity_contract_is_dormant`
  pins v3's `config.sha256` `475d99ec...0696` (equal to the activation
  record) and `RULE_SHA256` `35af2782...d5c4`, both captured before this
  step. Unpinned pairs and attempts serialize to exactly today's keys.
- Both workflow cache keys now also hash
  `tennis_elo_identity_amendments.csv`.
- Verify: web 1,235 passed and built; API 5,916 passed.

### Step 1 - 10-28 code path (pending)

Not run: needs the owner's yes to download TennisMyLife's public CSVs (no
local cache has the 10-28 rows; only the 10-20 and 10-21 downloads exist).
It does not change the design.

## Verify

- `npm --prefix web run verify && cd api && python -m pytest`
- Dormant merge: the next scheduled `Tennis Predictions and Shadow Freeze`
  run stays green with the unchanged v3 config hash.
- After v4: a reviewed alias appended with a future `effective_from` keeps
  the freeze green and the config hash unchanged; that day's snapshot
  manifest shows the new amendment count. No local `--write`, Neon change or
  workflow re-run without the owner's yes.

## Notes

- **Not doing here:** per-player quarantine (snapshot the day minus the
  conflicted players instead of blocking it). It would cut coverage loss
  while an alias waits for review, but it reverses 41b's "an identity
  conflict blocks a partial write" decision and needs its own argument.
  Suggest measuring blocked days under v4 first.
- **Not doing here:** the dedup-based alias suggestion in the dry-run report.
- Interview guide (if present): at Step 5, the 41b passage gains the move
  from pinning registry bytes to pinning an identity contract, and why.
- Open ledger finding F-42 (LF requirement) is unrelated and untouched.

## Outcome (2026-11-06)

- Built on `fix/tennis-elo-identity-amendments`: contract v1 in
  `app/core/tennis_elo.py`, refresh and freeze wiring, an empty
  `tennis_elo_identity_amendments.csv`, both workflow cache keys, and the data
  README procedure. It stays inert while the experiment JSON pins no
  `identity_contract`. v3's `config.sha256` `475d99ec...0696` and
  `RULE_SHA256` `35af2782...d5c4` are pinned unchanged by a test.
- Verify: `npm --prefix web run verify` (1,235 tests, build) and
  `python -m pytest` (5,916 passed), run with CI's dummy `DATABASE_URL`.
- No Neon change, no real `tennis_elo*` run, no workflow re-run.
- Push outside 11:00 to 13:30 UTC: the merge changes the workflow cache key.
- Deferred: the Step 1 data check and the Step 5 switch to v4.
