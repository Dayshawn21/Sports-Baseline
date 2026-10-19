# Keep tennis prop snapshots strictly pre-match

**Type:** Fix
**Fixes:** `nfl-finished-week-stats/F-06` (P1, temporarily accepted on
2026-10-18; repaired and re-reviewed here as `tennis-prop-snapshot-eligibility/F-21`).
**Branch:** `fix/tennis-prop-snapshot-eligibility`

## The problem

`skip_reason` in `api/app/services/tennis/prop_snapshots.py` checks the
displayed start and stored PrizePicks live flags, but ignores the linked
`Prop.match_status`. A known-live match with a future prop start and an old
non-live payload can therefore be frozen as a pre-match prediction.

`get_today_props` in `api/app/repositories/props.py` coalesces provider and
match starts into one value, losing their separate timing provenance. The
grading loader in `api/app/repositories/prop_snapshots.py` only checks
`snapshot_at < s.start_time`. A wrong provider start can pass that check.
Also, the database default for `snapshot_at` is transaction-start `now()`;
the snapshot job opens its transaction before loading and enriching inputs,
so that timestamp need not represent when the projection was actually frozen.

The archived audit reproduced the eligibility defect. It did not establish
how many historical snapshots, if any, were affected.

## The fix

Keep this an eligibility and provenance repair, with no projection change.

- Expose the raw provider start and resolved linked-match start separately
  on `Prop`, using optional fields appended to preserve existing callers.
  Match ID, status and linked start must all come from the same resolved
  match, including a relink. Keep the board's existing display start intact.
- Reject known-live, completed and cancelled matches, invalid links and
  provider live flags. Require an available start and freeze strictly before
  every available provider and linked-match start. Equality is already started.
  Missing one start may use the other; missing both remains ineligible. This
  conservative policy can skip delayed matches whose old scheduled time has
  passed, even when they have not actually started.
- Freeze the projection at an explicit timezone-aware timestamp taken after
  enrichment, using the same clock for eligibility and persisted
  `snapshot_at`. Do not rely on the transaction-start default. Prevent a batch
  that crosses a start boundary from inserting a supposedly pre-start row,
  using a statement-time guard in the repository. Keep skip/insert/duplicate
  counts honest if the repository rejects rows at that boundary.
- Preserve immutable capture provenance in the existing `projection_inputs`
  JSONB: an eligibility-policy marker, available raw provider and resolved
  match starts as ISO timestamps, and the observed linked-match status.
  Missing values remain explicitly distinguishable from observed values.
  Copy the page's inputs before adding provenance; never mutate its `PropLine`.
  Use the existing `snapshot_at` column explicitly; no schema migration is
  needed for this approach.
- For newly marked snapshots, grading must enforce pre-start eligibility
  against their captured starts and, when available, the linked match's current
  start. A later correction to an earlier start can conservatively exclude a
  new row; a delay must not make a row invalid at capture become eligible.
  Keep legacy unmarked rows on their existing grading path until the separate
  historical integrity review below. Do not manufacture provenance for them.

**Must not change:** `_enrich`, page recommendations, probabilities, EV,
tiers, distributions, payout assumptions, `PROJECTION_VERSION = "props-v2"`,
or the fixed tier adoption rule. A capture-policy marker is separate from the
projection version. Keep insert-once `(prop_id, projection_version)` behavior;
never update or delete existing snapshot rows. Keep SQL in repositories and
the pure eligibility policy independently testable.

**Out of scope:** reading historical outcomes, fitting or backtesting,
recalculating a fixed verdict, backfilling provenance, database writes or
running the production snapshot job during verification. A separate read-only
evidence-integrity review must quantify potentially affected legacy rows and
document any proposed sample correction before changing their grading. Until
then, preserve existing reported verdicts and state that legacy integrity is
unresolved. F-11, Rec Targets and other findings remain separate work.

## Build steps

1. [x] **Gate capture on resolved match status and both starts.** Add source
   timing fields to the repository result and pure eligibility checks. Carry
   the archived F-06 into the live ledger with a new available ID and its
   original provenance when implementation begins.

   **Done when:** deterministic tests reproduce the original live-match case
   and reject it with a future provider start and non-live payload. Cover
   completed/cancelled status, invalid link, both provider flags, either start
   at or before the clock, both future, each missing start, both missing and
   relinking with different original and resolved match times. Existing board
   and enrichment behavior remains unchanged.

2. [x] **Persist honest capture time and immutable provenance.** Pass the
   source context and freeze clock through the snapshot job, serializer and
   batch insert; add the statement-time guard and accurate counts. Apply the
   conservative grading checks to marked rows only.

   **Done when:** tests prove explicit `snapshot_at`, round-tripped provenance,
   unchanged page inputs and projection fields, insertion across a start
   boundary being refused, and repeated runs never overwriting a stored row.
   Delayed/corrected-start fixtures cover both directions of correction and
   the legacy compatibility path. Repository tests verify the actual emitted
   query and payload; job counts distinguish boundary rejection from an
   existing snapshot. Full Verify passes. Record that historical prevalence
   and legacy sample corrections remain outside this completion.

## Verify

- Focused tests: `test_prop_snapshots.py`, `test_prop_snapshot_repository.py`,
  `test_prop_snapshot_report.py`, and relevant prop repository/relink tests.
  Add focused job-policy coverage for the freeze clock and returned counts.
  Use fixed UTC clocks, synthetic rows and mocked database sessions; no test
  needs production data.
- Final gate from the repo root with the API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`.
- Review the job-to-repository path with a synthetic live match and mismatched
  starts: no snapshot can be inserted; a scheduled future control retains the
  board's projection and stores its actual capture timestamp and provenance.
- Run `/audit` to re-review F-06's carried finding before `/complete`, plus
  the standard invariants review. No new claim about historical calibration
  or edge follows from passing these checks.
- Manual try path: inspect the synthetic job output and serialized snapshot
  in the focused tests. A public props page may still show reference rows for
  started matches; this repair changes snapshot eligibility, not that page.

## Notes

- Base: `master` at `8a4bc4a`, already pushed. Implementation is on
  `fix/tennis-prop-snapshot-eligibility`.
- Step 1 was reviewed and approved with "Continue" on 2026-10-18.
  Focused snapshot/source/enrichment tests: 90 passed. Full Verify command
  passed: 611 web tests, 2,637 API tests and the production build, with one
  existing Starlette/AnyIO deprecation warning. Used the password-free CI
  database URL; no tests connect. Local ignored evidence:
  `output/snapshot-step1-verify.log` and `output/snapshot-step1.diff`.
  F-06 is carried as live F-21; step 1 alone does not resolve the full finding.
- Step 2 was reviewed and approved with "continue" on 2026-10-18.
  Focused snapshot and mocked-job tests passed (70). The final Verify command
  passed: 611 web tests, 2,654 API tests and the production build, with the
  existing Starlette/AnyIO deprecation warning. Local ignored evidence:
  `output/snapshot-step2-verify.log` and the step-2-only
  `output/snapshot-step2.diff`. The full suite was run after the final test
  adjustments. PostgreSQL predicates were inspected through emitted-query
  tests, not executed against a database; the job test mocks database I/O.
  No production job, historical outcome read or database write was run.
  F-21 was re-reviewed and closed by `/audit` on 2026-10-18 (current scope,
  all four lenses). No new findings. Invariants review: clean. Actual insert
  and player-filtered grading statements compile with the PostgreSQL dialect
  and the expected bindings. The review and its limitations are recorded in
  `blueprint/context/findings.md`. Both approved steps are ready for `/complete`.
- Preserve the existing item-39 edits in `blueprint/build-plan.md`,
  `blueprint/context/project-overview.md` and `blueprint/reference/39a/`.
- Update the local ignored employer interview guide when the implemented
  repair has verification evidence; distinguish future capture protection
  from any unperformed historical integrity review.

## Completion, 2026-10-18

Both build steps were approved, the full Verify passed, and the current-fix
all-lens audit closed F-21 with no new findings. Invariants review was clean.
No application or test code changed after the final passing Verify. The exact
command was `npm --prefix web run verify && cd api && python -m pytest`, with
the API venv on PATH and the password-free CI database URL: 611 web tests,
2,654 API tests and the production build passed. One existing Starlette/AnyIO
deprecation warning remains. The mocked job and emitted-query tests, plus
PostgreSQL dialect compilation, are the behavioral evidence for this change;
no database execution or production job was performed.

No migration is needed. The snapshot writer explicitly fills the existing
`snapshot_at` column, and provenance uses existing JSONB. `props-v2`, projection
math and the fixed grading rule are unchanged. Legacy eligibility stays on its
existing path until a separate read-only evidence-integrity review quantifies
potentially affected rows and proposes any correction explicitly. Historical
sample cleanliness and deployment have not been verified by this work.

The local ignored employer interview guide was updated to describe the repair
and these limits, and was not staged. Item-39 planning and reference edits were
preserved outside the fix. The original accepted finding has a repair pointer
to this archive. All other unresolved findings remain in the live ledger.

## How to try it

From `api/`, run:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_prop_snapshot_ingest.py tests/test_prop_snapshots.py -q
```

These synthetic cases prove that
a known-live match cannot reach insertion, a scheduled future control preserves
the page projection and capture provenance, and insertion rejections do not
inflate the duplicate count. Repository query assertions and their limitations
are recorded above. Do not run the production snapshot job merely to try this
repair, because it writes new predictions.

## Findings

### tennis-prop-snapshot-eligibility/F-21 [P1] closed - Pre-match prop snapshots can admit a match already marked live (carried: nfl-finished-week-stats/F-06)

**File:** api/app/services/tennis/prop_snapshots.py; api/app/repositories/props.py; api/app/repositories/prop_snapshots.py
**Found:** 2026-10-18 by /audit (scope: tennis prediction system; lenses: correctness, data quality, future-data leakage, tests). Archived as `nfl-finished-week-stats/F-06`, accepted temporarily to land the unrelated NFL finished-week repair; carried here for its dedicated repair and re-review.
**Why it matters:** A known-live linked match, future provider start and earlier non-live payload can pass snapshot eligibility. The coalesced start hides the separate source timings; grading checks only the stored start, and a transaction-start default can predate the actual freeze. This confirms an eligibility defect, not historical contamination.
**Suggested fix:** Gate capture on linked-match status and both starts; persist the actual freeze clock and immutable timing provenance; conservatively grade newly marked rows. Preserve legacy samples pending a separate evidence-integrity review.
**Resolution:** Fixed on `fix/tennis-prop-snapshot-eligibility`; both build steps approved on 2026-10-18. Separate source and resolved-match starts, status/link blocks and strict time checks prevent the original live-match case. The job persists the explicit post-enrichment clock and immutable timing/status provenance, rejects rows crossing a start at statement time with separate counts, and applies conservative grading only to marked rows. Full Verify passed (611 web tests, 2,654 API tests, production build); focused snapshot/mocked-job tests passed (70). Awaiting /audit re-review. SQL predicates were checked through emitted-query tests, not database execution. No historical outcomes or production snapshot writes were used; legacy prevalence and any sample correction remain a separate integrity review.
Closed 2026-10-18 by /audit (scope: current; lenses: quality, security, performance, tests). Reviewed all four changed application modules, the three changed and two new test files, and nearby schema, enrichment, grading and player-page consumers. Base and merge base: `master` at `8a4bc4a802b395637b3dccf8b58c62d3a05be3c8`; HEAD is the same commit, so the implementation is the unstaged and untracked delta. No new findings. The original known-live case is blocked independently of provider flags; both starts are carried from the source/resolved match, with a null resolved start never replaced by the old match's start. The source IDs are checked before serialization. The post-enrichment clock explicitly fills `snapshot_at`; the single batch query guards capture and statement times against the display and earliest available captured start, leaves conflicts untouched and accounts for boundary rejects separately. Marked grading checks captured times and the current match start before selecting the latest eligible row; unmarked legacy rows retain the old path. Projection fields, `props-v2`, the tier rule and historical verdicts are unchanged.

Audit signals: inspected the existing passing final Verify log (`output/snapshot-step2-verify.log`: 611 web, 2,654 API, build green), the focused 70-test result and all added assertions. Compiled the actual insert and player-filtered grading statements with SQLAlchemy's PostgreSQL dialect; all compiled bindings match the supplied parameters. AST name-load checks found no unused imports in the three changed snapshot modules. No skipped, xfailed, focused or placeholder tests were found in the reviewed set. `git diff --check` passed. SQL stays in repositories, interpolated aliases/clocks are internal constants, values are bound, and the write job remains one batch statement with no added network round trips. Invariants review: clean. No dependency/security scanner, runtime benchmark, browser pass or database execution was performed. Dependencies, generated output, model/data artifacts and unrelated item-39 planning edits were excluded. Legacy integrity remains unquantified and requires the separate evidence review already recorded in the approved spec; this closure establishes the capture repair, not historical sample cleanliness.
