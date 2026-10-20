# Fix: Keep NFL slate prop lines before kickoff

**Type:** Fix
**Fixes:** nfl-prop-kickoff-cutoff/F-13
**Completed:** 2026-10-19
**Branch:** `fix/nfl-prop-kickoff-cutoff`

## The problem

`api/app/repositories/nfl.py::_LATEST_LINES_CTE` selects each provider prop's
latest snapshot without checking the linked game's kickoff. It feeds both
`get_slate_lines` and `get_unmatched_slate_lines`.

- A snapshot fetched at or after kickoff can replace the pre-game line on
  the slate and its consuming pages.
- The 27a line-grading loader builds edges from slate line IDs, while
  `get_gradeable_prop_lines` selects the last pre-kickoff ID. A later
  snapshot can make that graded call lose its matching edge.
- The audit recorded zero affected modelled snapshots in its 2026 read on
  2026-10-18. This is a latent data-selection defect, not evidence of a
  changed model result.

## The fix

Join `sport_games` inside `_LATEST_LINES_CTE` by `l.game_id`, with an explicit
`g.sport = 'nfl'` constraint. Before `DISTINCT ON` selects the latest row,
apply the existing NBA rule:

```sql
(g.start_utc IS NULL OR l.fetched_at < g.start_utc)
```

Known kickoff times exclude snapshots fetched exactly at kickoff or later.
Unknown kickoff times retain their current serving behavior. Preserve the
provider/prop grouping, `fetched_at DESC, id DESC` tie-break, existing market
filter, and downstream season/week/regular-season restrictions. A prop with
only post-kickoff snapshots is omitted; an earlier eligible snapshot remains
available when a newer one is ineligible. Unmatched-player lines linked to a
game follow the same cutoff.

Keep this a repository guard with regression coverage. No ingest, schema,
projection, probability, model-version, ranking-rule, frozen-row or holdout
changes are needed. Existing stored report snapshots acquire the corrected
selection on their normal refresh; this fix does not run an ingest or remote
refresh.

## Build steps

- [x] **1. Guard latest NFL slate prop selection and cover both consumers.**
  Update the shared CTE and add recorded-SQL regressions in
  `api/tests/test_nfl_repository.py` for `get_slate_lines` and
  `get_unmatched_slate_lines`. Inspect the CTE portion of each emitted query
  so an unrelated outer join or cutoff cannot satisfy the assertions.
  **Done when:** both queries join an NFL game and apply the strict cutoff
  with the NULL-start exception inside latest-line selection, while keeping
  the existing market filter and deterministic ordering. Regressions fail
  against the old CTE and pass with the guard; existing NFL repository and
  track-record service tests still pass. Mark nfl-prop-kickoff-cutoff/F-13 `fixed` with the repair
  evidence when this step lands; closure awaits `/audit` re-review.

## Verify

- From `api/`, run `.venv\Scripts\python.exe -m pytest tests/test_nfl_repository.py tests/test_nfl_track_record_service.py`.
- Confirm the SQL regressions pin `<` rather than `<=`, preserve the NULL-start
  exception, and place the predicate before latest-snapshot selection in both
  consumer queries. Use synthetic sessions, with no live database or provider
  calls and no historical holdout reads.
- Run the documented final Verify gate from the repo root with the API venv
  active: `npm --prefix web run verify && cd api && python -m pytest`.
- No new forward-validation claim follows from this data guard. No browser
  check is required for the unchanged response shape and UI.

## Implementation evidence

- Branch: `fix/nfl-prop-kickoff-cutoff`.
- Added the NFL game join and kickoff predicate inside `_LATEST_LINES_CTE`.
  Recorded-SQL regressions inspect this CTE in both consumers and preserve
  the market filter, provider grouping, strict cutoff, NULL-start exception,
  and timestamp/ID ordering.
- Red/green: both new cases failed on the original CTE; the focused repository
  and track-record service run then passed all 96 tests with the guard.
- Web gate: `npm --prefix web run verify` passed typechecking, 632 tests, and
  the production build. Vite reported its bundle-size warning. The initial
  sandbox attempt could not load the Vite config; the approved rerun passed.
- The combined gate selected a global Python without pytest despite the PATH
  override. Ran its API half explicitly from `api/` with
  `.venv\Scripts\python.exe -m pytest`: 3,023 passed, one dependency deprecation
  warning. All configured Verify checks passed across these invocations.
- `git diff --check` passed. No live database, provider or holdout reads ran.
- User approved the implementation step in chat on 2026-10-19. Step 1 is
  complete and nfl-prop-kickoff-cutoff/F-13 was closed by `/audit nfl-prop-kickoff-cutoff/F-13` after re-review.
  The pre-existing `project-overview.md` edit is outside this fix and is
  excluded from the work commit.

## Completion verification

- The exact Verify command, `npm --prefix web run verify && cd api && python -m pytest`,
  passed as one combined run after activating `api/.venv` with `activate.bat`.
  Web: 632 tests, typecheck and production build passed. API: 3,023 tests passed.
  Nonblocking warnings: Vite bundle size and a dependency deprecation.
- Final invariants review: clean. Explicit NFL sport filters and the existing
  modelled-market filter are preserved. No projection, probability, version,
  ranking rule, UI signal, schema or production report path changed.
- The build plan needs no change for this ad-hoc fix. No interview-guide claim
  changes for this small guard; the local guide is unchanged.
- How to try: from `api/`, run `.venv\Scripts\python.exe -m pytest tests/test_nfl_repository.py -k latest_snapshot_before_kickoff -q`.
  Both linked and unmatched consumer cases pass. The SQL excludes fetches at
  or after a known kickoff while keeping unknown-start serving behavior.
  Existing stored reports reflect the change on their next normal refresh.

## Findings

### nfl-prop-kickoff-cutoff/F-13 [P3] closed - The slate's line query has no pre-kickoff cutoff, unlike NBA's

**File:** api/app/repositories/nfl.py:1159; api/app/services/nfl/track_record.py:66; api/app/ingest/prizepicks_props.py:85
**Found:** 2026-10-18 by /audit (scope: NFL prediction system and consumers; lenses: leakage, correctness)
**Why it matters:** `_LATEST_LINES_CTE` takes each provider prop's newest
snapshot regardless of kickoff, and the PrizePicks ingest stores whatever the
board returns with no start check. NBA's equivalent reads
`(g.start_utc IS NULL OR l.fetched_at < g.start_utc)` (`nba.py:409`, `:452`,
tested). Two latent effects: a started game's page would show a post-kickoff
line beside a pre-game projection, and 27a would silently drop the call,
because its edges are keyed by the latest snapshot id while
`get_gradeable_prop_lines` grades the last pre-kickoff id. Freezing is safe
(it only freezes unstarted games). Read-only count: 0 post-kickoff modelled
snapshots among about 96,000 in 2026, so there is no current effect.
**Suggested fix:** Join the game in the CTE and apply NBA's cutoff, with a
recorded-SQL test. Output is identical on today's data. No model change.
**Resolution:** Fixed on `fix/nfl-prop-kickoff-cutoff`; implementation approved
in chat on 2026-10-19. `_LATEST_LINES_CTE` now joins the NFL game and applies
`(g.start_utc IS NULL OR l.fetched_at < g.start_utc)` before latest-snapshot
selection, preserving the existing market filter and timestamp/ID ordering.
Recorded-SQL regressions for linked and unmatched slate lines both failed on
the original query and passed with the guard. Focused tests: 96 passed. Web
Verify: typecheck, 632 tests, and production build passed; the API half ran
explicitly with the venv: 3,023 passed. No model, ingest, database or holdout
changes. Closed by `/audit nfl-prop-kickoff-cutoff/F-13` on 2026-10-19 after fresh review of the
repository change, both query consumers, grading/freezing/cache callers,
regressions and relevant schema constraints across all four audit lenses.
The strict cutoff precedes DISTINCT selection and preserves NULL-start
serving, market/provider filters and deterministic ordering. The additional
join cannot multiply rows because it uses the game's primary key; both
consumers already required a linked NFL game. No new defect found in the
repair. Audit verification: 122 targeted tests passed; in-memory mutations
confirmed both consumer regressions reject five weakened-query variants
(10 failures as expected), then pass with the original query restored.

## Audit evidence, 2026-10-19

**Result:** No new findings across quality, security, performance or tests
within the selected scope. nfl-prop-kickoff-cutoff/F-13 moved from `fixed` to `closed`. Other ledger
entries retain their prior statuses; F-14 and F-20 remain open and nonblocking.
No repair order is needed for this change. Audit cleared this fix for completion.

**Scope and comparison:** Focused review of the active nfl-prop-kickoff-cutoff/F-13 fix and nearby
callers on `fix/nfl-prop-kickoff-cutoff`. Local base branch: `master`.
Merge base and HEAD: `aa38595db3bd8d1d9b730f9a2799fb557e7e4b13`.
The merge-base-to-HEAD committed range is empty, with no staged changes or
untracked source files. Reviewed the unstaged product diff and active spec.
The pre-existing `project-overview.md` edit is outside this repair's scope.

**Reviewed set:**

- `api/app/repositories/nfl.py`: latest-line CTE, linked and unmatched slate
  readers, downstream game joins and pre-kickoff grading reader.
- `api/tests/test_nfl_repository.py`: recording-session isolation, new
  parametrized regression and existing market, ordering and grading guards.
- `api/app/services/nfl/{slate,track_record,prop_source,slate_cache}.py`:
  shared reader use, edge-ID pairing, freezing and stored snapshot serving.
- `api/app/ingest/prizepicks_props.py`: raw line persistence boundary;
  `api/app/repositories/nba.py`: established cutoff comparison.
- Shared-table migrations `0039`, `0040`, `0041`: game primary-key and
  prop-line foreign-key continuity and existing index declarations.
- Tests for the track-record service, slate cache, prop freezing and NBA
  repository; project instructions, standards, overview and active fix spec.

**Lens conclusions:** Repository ownership and the existing query pattern
are preserved. The added game alias is NFL-scoped, with static SQL and no new
client input or authorization surface. The join is batched against a unique
game ID, with no additional round trips or Python-side materialization.
No measured query-plan or latency claim follows from this static review.
The regressions inspect the inner CTE, so an outer join or cutoff cannot
satisfy them; they pin strict `<`, NULL handling, market scope, grouping and
timestamp/ID ordering. No skipped, focused-only or placeholder tests found
in the two directly relevant NFL repository and track-record test files.

**Commands and evidence:**

- From `api/`: `.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/test_nfl_repository.py tests/test_nfl_track_record_service.py tests/test_nfl_slate_cache.py tests/test_nfl_prop_predictions.py tests/test_nba_repository.py`:
  **122 passed**, one dependency deprecation warning, no skips or xfails.
- In-memory only: invoked the new regression for each consumer after removing
  the cutoff, changing `<` to `<=`, removing the NULL-start exception, removing
  the game's sport guard, and reversing the ID tie-break. All **10/10** weakened
  cases were rejected; restoring the query passed **2/2** consumer cases.
- `git diff --check`: passed. Inspected existing implementation evidence of
  632 web tests, typecheck/build and 3,023 API tests; did not rerun broad gates.

**Limits and exclusions:** No live Postgres execution or EXPLAIN, production
snapshot refresh, browser flow, provider call, vulnerability scan, profiling,
holdout read or model validation. No lint command is configured. Dependencies,
build output, caches and unrelated app features were excluded. The SQL tests
record emitted queries rather than execute PostgreSQL. This review edits only
the ledger; no source, spec, workflow, dependency or git state was changed.
