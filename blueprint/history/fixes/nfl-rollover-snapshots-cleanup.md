# Fix: NFL rollover snapshot freshness and unused import cleanup

**Type:** Fix
**Fixes:** nfl-rollover-snapshots-cleanup/F-14, nfl-rollover-snapshots-cleanup/F-20
**Completed:** 2026-10-20
**Branch:** `fix/nfl-rollover-snapshots-cleanup`

## The problem

- **nfl-rollover-snapshots-cleanup/F-14:** `api/app/ingest/nfl_slate_snapshot.py::parse_weeks` makes
  `--weeks current` refresh only the previous and current week. At rollover,
  the next week's stored slate can still be the older `--weeks all` backfill
  until the next scheduled refresh runs. Production serves this stored copy.
- **nfl-rollover-snapshots-cleanup/F-20:** `api/app/services/tennis/bankroll_builder.py` imports `field`
  from `dataclasses` without using it.

## The fix

- Have `--weeks current` select the previous, current and next week, bounded
  inclusively to regular-season weeks 1 through 18. Refreshing the upcoming
  week before rollover removes reliance on its old backfill copy. Keep the
  previous week for final scores and preserve current-season selection,
  explicit week lists, `all`, missing-week errors and snapshot keys.
- Update the ingest module's explanation and the corresponding snapshot
  description in `AGENTS.md` to match. Existing workflows already call this
  command, so their schedules do not need changes. Keep each week's build and
  write sequential, preserving the hosted API's stored-report memory boundary.
- Remove only `field` from the bankroll builder's import. No new test is
  needed for removing an unused import; run existing bankroll regression tests.
- Do not add a computed-time response field, alter model output or versions,
  rerun holdouts, change the build plan, refresh production data, or deploy.
  The freshness guard applies on the next normal snapshot job after deployment;
  it does not guarantee a fresh copy when scheduled jobs fail or are delayed.

## Build steps

- [x] **1. Refresh the upcoming slate week and remove the unused import.**
  Update `parse_weeks`, its existing tests, its module documentation and
  `AGENTS.md`; remove the unused bankroll import in the same small reviewable
  diff, as requested. **Done when:** `current` produces `[5, 6, 7]` for week 6,
  `[1, 2]` for week 1, and `[17, 18]` for week 18; the existing explicit-list,
  `all` and invalid-input behavior remains covered and passing; `field` is no
  longer imported; focused tests and the full Verify gate pass. After step
  approval, mark both findings `fixed` with evidence; `/audit` re-reviews them
  before closure.

## Verify

- From `api/`: `.venv\Scripts\python.exe -m pytest tests/test_nfl_slate_snapshot.py tests/test_nfl_slate_cache.py tests/test_bankroll_builder_set_picks.py tests/test_bankroll_strict_criteria.py`.
- Confirm the week-selection regressions fail before the change and pass after
  it. Use synthetic fixtures; do not call the ingest CLI against the database.
- From the repo root with the API venv activated, run the exact Verify command:
  `npm --prefix web run verify && cd api && python -m pytest`.
- Inspect the small source/doc diff and run `git diff --check`. The existing
  `project-overview.md` edit is outside this fix and must remain untouched.

## Implementation evidence

- Branch: `fix/nfl-rollover-snapshots-cleanup`. User approved the spec in chat.
- `parse_weeks("current", ...)` now includes the next week within the same
  1-18 bounds. Existing sequential build/write behavior is unchanged.
  Updated module documentation and the matching `AGENTS.md` description.
- Removed the unused `field` import from the bankroll builder. `CLAUDE.md`
  imports `AGENTS.md`, so no duplicate adapter documentation needs changing.
- Red/green: the updated week-6 and week-1 expectations failed on the original
  code. After the repair, the focused command above passed all 27 tests,
  including week-18 bounds, unchanged argument modes and bankroll behavior.
- The exact Verify command passed in one run after `activate.bat` activated
  the API venv: 632 web tests, typecheck, production build, and 3,024 API tests.
  Only Vite's bundle-size warning and a dependency deprecation were reported.
- `git diff --check` passed. No ingest, provider calls, live database access,
  production refresh, deployment or holdout reads ran. This small fix does
  not change any interview-guide claim, so the local guide was not edited.
- User approved the implementation step in chat on 2026-10-20. Step 1 is
  complete; nfl-rollover-snapshots-cleanup/F-14 and nfl-rollover-snapshots-cleanup/F-20 were closed by `/audit current` after re-review.
  The pre-existing overview edit is excluded from this fix and its work commit.

## Completion verification

- The exact Verify command, `npm --prefix web run verify && cd api && python -m pytest`,
  passed in this session with the API venv activated: 632 web tests,
  typecheck, production build and 3,024 API tests. No product changes followed
  that run. Nonblocking warnings were Vite bundle size and a dependency
  deprecation. Audit reran the focused suite: 27 passed.
- Audit also confirmed four mocked CLI cases, correct week/season keys,
  sequential writes and dry-run behavior without live database calls.
- Final invariants review: clean. The added week is built sequentially by the
  existing batch command. No heavy report moved to the production request
  path; model inputs, rules, versions and signal colors are unchanged.
- `CLAUDE.md` imports the updated `AGENTS.md` operations documentation.
  No skill or workflow adapter behavior changed. This ad-hoc fix does not
  alter the build plan or any interview-guide claim.
- How to try: from `api/`, run `.venv\Scripts\python.exe -m pytest tests/test_nfl_slate_snapshot.py -k TestParseWeeks -q`.
  The cases confirm week 6 selects 5/6/7, week 1 selects 1/2 and week 18
  selects 17/18, with explicit-list, all and missing-week behavior retained.
- No production refresh or deploy ran. The new selection applies when the
  updated snapshot job next runs normally; it does not guarantee freshness
  through failed or delayed jobs.

## Findings

### nfl-rollover-snapshots-cleanup/F-20 [P3] closed - Bankroll builder retains an unused dataclasses import

**File:** api/app/services/tennis/bankroll_builder.py:10
**Found:** 2026-10-18 by /audit (scope: imports in the two F-19 modules; lens: quality). Present before this fix.
**Why it matters:** `field` is imported from `dataclasses` but has no name load in the module, contrary to the no-unused-import convention. No runtime behavior is affected.
**Suggested fix:** Remove `field` from the import during a future cleanup.
**Resolution:** Fixed on `fix/nfl-rollover-snapshots-cleanup`; implementation
approved in chat on 2026-10-20. Removed only the unused `field` import;
`dataclass` remains. Existing bankroll regressions passed within the 27-test
focused run. Full Verify passed: 632 web tests, typecheck/build and 3,024 API
tests. Closed by `/audit current` on 2026-10-20: reviewed the complete import
change and relevant bankroll tests; an AST check confirms `dataclass` is
retained and neither a `field` import nor a `field` name usage remains.
No new defect found in the repair. F-19 remains independently closed.

### nfl-rollover-snapshots-cleanup/F-14 [P3] closed - Future-week slate snapshots from the 37d backfill are served at each week rollover, and the payload has no build time

**File:** api/app/ingest/nfl_slate_snapshot.py:29; api/app/repositories/nfl.py:943; api/app/services/nfl/slate_cache.py:102
**Found:** 2026-10-18 by /audit (scope: NFL report snapshots; lens: data quality)
**Why it matters:** `report_snapshots` holds 2026 weeks 7 to 18 built
2026-10-16 20:08 to 20:09 UTC (`--weeks all` backfill). `--weeks current`
writes only the current week and the one before. The current week rolls 12
hours after the last kickoff (Tuesday about 12:15 UTC), and the first refresh
after that is `nfl-weather.yml` at 14:00 UTC (subject to the same cron
delays). In between, production serves a copy several days old for the new
week. `NflSlateResponse` carries no computed time, so neither the page nor a
reader can tell. No wrong-week or cross-season serving was found: the key is
`(nfl_slate_week_<N>, season)` and the request names both.
**Suggested fix:** Have `current` also write the next week, or stop
backfilling future weeks; optionally expose the snapshot's `computed_at`.
Tests on `parse_weeks`. Display freshness only, no model change.
**Resolution:** Fixed on `fix/nfl-rollover-snapshots-cleanup`; implementation
approved in chat on 2026-10-20. `--weeks current` now refreshes the previous,
current and next week, bounded to weeks 1-18. Updated module documentation
and `AGENTS.md`. Week-6 and week-1 regressions failed on the original code;
all 27 focused tests passed after the repair, including the new week-18
boundary and existing argument-mode/cache/bankroll tests. Full Verify passed:
632 web tests, typecheck/build and 3,024 API tests. No production snapshot
refresh or deploy ran; the guard takes effect with the next normal snapshot
job after deployment. No response timestamp or model change. Closed by
`/audit current` on 2026-10-20 after fresh review of week selection, the CLI
build/write loop, current-week selection, snapshot keys, production serving,
workflow callers and tests. All 27 focused tests passed again. Four in-memory
mocked CLI cases confirmed correct week/season keys and sequential writes
for weeks 1, 6 and 18, and no writes in dry-run mode. No new defect found in
the repair; refreshing the upcoming week addresses rollover backfill age
without changing the hosted API's stored-report boundary.

## Audit evidence, 2026-10-20

**Result:** No new findings across quality, security, performance or tests in
the current work. Closed nfl-rollover-snapshots-cleanup/F-14 and nfl-rollover-snapshots-cleanup/F-20 after re-review. F-09 and F-12 remain
unverified and unchanged; no open or fixed findings remain. No repair order
is needed for these changes. Audit cleared this fix for completion.

**Scope and base:** `current`, on `fix/nfl-rollover-snapshots-cleanup`, compared
against local `master` without fetching. Merge base and HEAD are both
`bffbf5c8adcc827bc1a912e5e238d1877cf50391`. There are no committed branch
changes, staged changes or untracked source files. Reviewed the unstaged
product, documentation, spec and ledger changes, plus nearby callers.

**Reviewed files and standards:**

- `api/app/ingest/nfl_slate_snapshot.py` and
  `api/tests/test_nfl_slate_snapshot.py`: bounded previous/current/next
  selection; explicit lists, all and missing-week behavior; sequential
  building, writing and per-week commits; dry-run behavior and season guard.
- `api/app/services/tennis/bankroll_builder.py` and its existing
  `test_bankroll_builder_set_picks.py` / `test_bankroll_strict_criteria.py`
  regressions: minimal unused-import removal and retained dataclass use.
- `api/app/repositories/nfl.py::get_current_week`,
  `api/app/repositories/report_snapshots.py`,
  `api/app/services/nfl/slate_cache.py` and `test_nfl_slate_cache.py`:
  current-week rollover, parameterized season/report keys and production
  snapshot serving remain unchanged.
- The four NFL snapshot workflow callers (`nfl-ingest`, `nfl-prop-lines`,
  `nfl-prop-odds`, `nfl-weather`): all use the default `current` mode, so
  the added week reaches existing refresh jobs without schedule changes.
- `AGENTS.md`, `CLAUDE.md`, current spec, project overview diff and relevant
  coding/interaction standards: updated operational description matches the
  code; Claude imports the shared instructions. The pre-existing overview
  refresh was inspected as documentation, including progress against the
  build plan. Its historical model/deployment claims were not independently
  revalidated. It remains outside the fix's completion commit.

**Lens conclusions:** The change reuses the existing parser and bounded
regular-season constant. No new SQL, untrusted interpolation, secrets, routes
or authorization surface are introduced. Snapshot keys and the explicit-season
guard are retained. A normal mid-season run adds one upcoming-week build;
the loop still builds, serializes, writes and releases one week at a time.
No heavy report moves onto the hosted request path. Expected additional batch
runtime is not a measured latency or memory claim. Tests assert useful week
boundaries rather than implementation details; no skipped, focused-only,
xfail or placeholder tests found in the four focused test files.

**Verification:**

- From `api/`: `.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/test_nfl_slate_snapshot.py tests/test_nfl_slate_cache.py tests/test_bankroll_builder_set_picks.py tests/test_bankroll_strict_criteria.py`:
  **27 passed**, one dependency deprecation warning.
- In-memory only: ran `_main` with mocked session, engine, current-week
  lookup, builder, serializer and snapshot writer. **4/4** cases passed:
  week 1 writes 1/2, week 6 writes 5/6/7, week 18 writes 17/18, and dry run
  builds without writing or committing. Verified event order, season/report
  keys and engine disposal; no real database or provider calls.
- AST inspection confirmed that the bankroll module imports only `dataclass`
  from `dataclasses` and has no `field` name usage.
- `git diff --check`: passed. Inspected the implementation's full Verify
  evidence (632 web tests, typecheck/build, 3,024 API tests); broad gates were
  not repeated because no product changes occurred after that passing run.

**Limits:** No production refresh, browser check, live database execution,
benchmark, vulnerability scan or holdout read. No lint command is configured.
Dependencies, build output, caches and unrelated app source were excluded.
No claim of fresh production data follows until normal deployed jobs run;
failed or delayed jobs can still leave an older copy. Only this ledger was
edited by the audit; source, spec and git branch/index state were unchanged.
