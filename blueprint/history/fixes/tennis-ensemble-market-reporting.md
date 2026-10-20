# Fix: Report tennis ensemble versus market without requiring ML

**Type:** Fix
**Fixes:** F-07 (P3)
**Status:** Completed locally 2026-10-19. Both steps approved; independent audit closed F-07 with no new findings.
**Branch:** `fix/tennis-ensemble-market-reporting`

## The problem

The prediction grading service and CLI require every member of
`MARKET_COMPONENTS` for their market loss comparison. Challenger and WTA 125
predictions intentionally have no ML probability, so a selected
`ensemble-v3+lgbm-none` version can have settled, market-priced predictions
while all four score groups report zero matches. Missing ELO can cause the
same exclusion even when the ensemble correctly serves the market alone.

The current calibration also uses the all-four subset. Its coverage must be
labelled accurately; neither it nor a market-paired table validates the
market-free fallback.

## The fix

- Add an explicitly labelled ensemble-versus-market comparison to the existing
  prediction endpoint and CLI report. Require only stored ensemble and market
  probabilities, on the same rows for both columns. Report log loss, Brier,
  paired ensemble-minus-market log-loss difference, one standard error and
  the existing loss signal, with an independent sample count per group.
- Keep the current `groups`, calibration, ELO/ML comparisons, counts and CLV
  contracts intact. Add `ensemble_market_groups` (`ensembleMarketGroups` in
  JSON) using the existing group-score shape, with market and ensemble rows
  only. ELO/ML retain their existing all-four sample counts; never attach
  the new pair's count to those comparisons.
- Keep ATP, WTA, ATP+WTA and CHALLENGER grouping and exact model-version
  isolation. WTA 125 remains in CHALLENGER. Missing or gated ELO and missing
  ML must not prevent scoring a stored ensemble-market pair. Do not infer or
  recompute serving gates from reporting inputs.
- Show the new comparison on `/tennis/model` beside the existing all-four
  comparison. Label each sample requirement and empty state explicitly.
  Keep the existing ATP+WTA headline and calibration tied to the all-four
  sample and label that scope. Explain that market-free fallback rows are
  excluded from market comparisons. Adding pair-only calibration or new
  component-specific ELO/ML samples is outside this fix.
- Preserve predictions, coefficients, versions, moneyline-off behavior, signal
  thresholds and the 26d adoption rule. Use stored forward grading only;
  no refit, retraining, historical reconstruction or holdout rerun.

## Build steps

- [x] **1. Add the paired report with synthetic regression coverage.** Update
  `api/app/services/tennis/track_record.py`,
  `api/app/backtest/tennis_predictions.py`, `api/app/schemas/tennis.py` and
  their focused tests. Reuse the existing pure scoring functions.
  **Done when:** a completed Challenger row with `ml_prob=None` appears in
  the new pair with correct losses and count while the all-four group stays
  empty. Missing ELO and market-only ensemble cases also qualify; missing
  ensemble or market does not. Other versions and incomplete scores remain
  excluded. Empty and one-row samples behave correctly, including an absent
  standard error for one row. CLI and API agree on fixture counts and losses,
  and existing all-four/calibration/CLV regressions still pass.

- [x] **2. Display and explain the two samples.** Update the typed web response
  and the tennis model page's table, headline scope and empty-state copy.
  Reuse the current table styling and server-provided signals. Add tests for
  any new pure display derivation.
  **Done when:** selecting a no-ML version shows its ensemble-market comparison
  and sample count even when the all-four table is empty. Labels distinguish
  both samples, the ATP+WTA headline and calibration state their all-four
  scope, and no market-free validation claim appears. Version switching,
  loading/error states and narrow-screen tables work. Browser evidence and
  the full Verify gate pass. Update the local employer interview guide if
  its reporting-coverage claims need correction, using verified behavior.

## Verify

- Exercise fixed synthetic rows in `test_track_record_service.py` and
  `test_tennis_prediction_report.py` covering the eligibility matrix above,
  different outcomes, group boundaries and mixed versions. Check additive
  camel-case serialization with the existing route fixture as appropriate.
- Run focused grading and track-record tests, plus relevant web utility tests.
  Inspect `/tennis/model` with controlled no-ML, all-four and empty responses;
  verify both tables and version switching without paid provider calls.
- Run the documented gate with the API venv:
  `npm --prefix web run verify && cd api && python -m pytest`.
  On this PowerShell host, use `npm.cmd` and the API venv executable in
  separate halves if needed.
- Review the diff for unchanged scoring/adoption rules and no model artifacts,
  schema migration, historical dataset or holdout execution. Mark F-07
  `fixed` only when its repair lands; `/audit` re-reviews before closure.

## Implementation evidence (2026-10-19)

- Step 1 adds independent ensemble-market groups to the API and CLI without
  changing all-four eligibility, calibration or CLV. Six API source/test files
  changed. No web source, live data, model artifact or adoption rule changed.
- Focused fixture checks: `.venv\Scripts\python.exe -B -m pytest -q
  -p no:cacheprovider tests/test_tennis_prediction_report.py
  tests/test_track_record_service.py tests/test_track_record_routes.py
  tests/test_tennis_grading.py tests/test_track_record_core.py` from `api/`:
  **70 passed**. Cases include no ML, absent ELO, a stored market-only ensemble
  with a conflicting ELO input, missing pair members, incomplete results,
  version isolation, grouping, singleton uncertainty and CLI/API agreement.
- Full Verify ran in the documented Windows halves: `npm.cmd --prefix web
  run verify` from the root (**630 web tests, typecheck and build passed**),
  then `.venv\Scripts\python.exe -m pytest` from `api/`
  (**3,021 passed**). The web command needed approved execution outside the
  sandbox after esbuild parent-directory access failed. Existing chunk-size
  and Starlette/AnyIO deprecation warnings remain.
- `git diff --check` passed. The user approved step 1 and continuation to
  step 2. F-07 remains open until the reviewed repair is complete. No commit made.
- Step 2 adds the typed paired groups and a separate table on the model page,
  labels the original table/headline/calibration sample, and formats paired
  uncertainty without treating a singleton's missing SE as zero. The version
  menu now matches its control width and is constrained to the available width.
  Existing styling, signals, query keys and version filtering remain in use.
- Final web gate: `npm.cmd --prefix web run verify`, **632 tests passed**,
  typecheck and production build passed. The unchanged API passed its full
  `.venv\Scripts\python.exe -m pytest` gate, **3,021 tests**, during step 2.
  Existing build-size and dependency deprecation warnings remain.
- `/check` ran the real Vite app with Playwright and responses serialized from
  the actual grading service using fixed synthetic rows. No database, provider
  request, historical dataset or holdout was used. Pointer-driven version
  switching showed two no-ML Challenger pairs (market loss 0.7136, ensemble
  loss 0.7403, difference +0.0267 +/- 0.1068) with an empty all-four table.
  The full version showed four pooled pairs versus three all-four matches,
  with calibration and headline retaining the latter count. The empty version
  displayed the distinct empty states. Delayed loading and deliberate 503s
  showed the expected states; Retry restored both tables. Successful fixture
  checks recorded no page errors or failed requests; injected 503 responses
  were expected. The first route fixture also matched Vite source URLs; that
  harness error was corrected before the reported checks. A keyboard-switch
  attempt did not select the desired option; it is not claimed as verified.
- At a 390px viewport, both populated tables overflow only their horizontal
  scroll containers; the document stays within the viewport. Screenshot
  evidence is local and ignored under `.playwright-mcp/f07/`:
  `no-ml-desktop.png`, `no-ml-mobile.png`, `all-four-desktop.png`,
  `all-four-mobile.png`, `empty-mobile.png`, `loading-desktop.png` and
  `error-desktop.png`. Screenshots were visually inspected. The existing
  version-menu exit animation delayed some automated screenshots; the
  final narrow-screen overflow checks passed after menu interaction settled.
- Updated the local, ignored employer interview guide to describe the coverage
  repair as implemented, locally verified and approved, with independent audit
  pending and no deployment claim. The user approved step 2; both steps are
  checked and F-07 is fixed pending independent audit. No commit, merge, push,
  deploy or ledger closure occurred.

## Completion verification (2026-10-19)

- Final safety pass: both steps are approved on the fix branch; F-07 is closed
  by independent audit. No open/fixed P0 or P1 finding remains.
- Full Verify passed in this session using the documented Windows halves:
  `npm.cmd --prefix web run verify` (typecheck, 632 web tests and production
  build) and, from `api/`, `.venv\Scripts\python.exe -m pytest`
  (3,021 API tests). Source has not changed since those passing gates.
  Existing chunk-size and dependency deprecation warnings are nonblocking.
- Independent audit reran 91 focused API tests and 18 web utility tests and
  compared the original report with the repair on 1,000 synthetic rows.
  Old report fields/sections matched exactly; independent pair metrics agreed.
- Invariants review: clean for the changed paths. Exact version and tour
  separation, pure scoring, repository-owned SQL and server-provided signal
  rules hold. No sport/provider/NBA query, generated fit, model output,
  adoption threshold, holdout use or production configuration changed.
  The pair adds bounded grouped output over existing cached data, with no new
  database/provider request or model load. Production memory was not profiled.
- Existing browser evidence proves version switching, sample separation,
  empty/loading/error/retry behavior and horizontal scroll at 390px.
  Evidence is synthetic and local; no hosted deployment was checked.
- Updated the ignored local employer guide to record independent audit closure.
  It stays untracked and is excluded from staging.
- The pre-existing overview refresh is outside this fix and is preserved
  outside the work commit. No build-plan item changes for a fix.
- Archived F-07 and the carried-forward closed F-15 audit entry below, preserving
  F-15's earlier 39c repair and re-review provenance. Unresolved entries remain
  in the live ledger with their IDs. This completion adds no NFL product work.
- How to try: start the API and web using the documented dev commands, open
  `http://localhost:3001/#/tennis/model`, and select `ensemble-v3+lgbm-none`.
  Eligible Challenger pairs should appear even if All four components is empty.
  The headline/calibration retain their labelled ATP+WTA all-four sample.
  Counts depend on stored results; market-free rows remain excluded.

## Findings

### tennis-ensemble-market-reporting/F-07 [P3] closed - Prediction grading has no loss comparison for the served no-ML path

**File:** api/app/services/tennis/track_record.py:147; api/app/services/tennis/track_record.py:165; api/app/backtest/tennis_predictions.py:31
**Found:** 2026-10-18 by /audit (scope: tennis prediction system; lenses: correctness, calibration coverage, tests)
**Why it matters:** Loss tables and calibration require every member of
`MARKET_COMPONENTS`, including ML, even though current Challenger predictions
intentionally have no ML and market-anchored v3 assigns ML zero weight. The
existing endpoint, read on 2026-10-18, returned 455 completed
`ensemble-v3+lgbm-none` predictions with 212 market prices, but all four score
groups had n=0 and no component rows. Challenger CLV still reports 135 eligible
nonzero gaps, confirming this is not simply an empty version. Separately,
market-free fallback rows cannot appear in the market-paired table by design;
the endpoint should not be described as validating that fallback.
**Suggested fix:** Add an explicitly labelled ensemble-versus-market paired
comparison requiring only those two probabilities. Keep the original all-four
comparison and its common-row contract intact, with separate counts for any
ELO/ML comparisons. Test a Challenger row with ML=None, plus missing/gated ELO
and market-free rows. This is reporting coverage, not a model change; tests
and existing forward grading suffice. Do not pool model versions or change the
26d adoption rule. Downgraded P2 to P3 on 2026-10-18 review: a reporting
coverage gap, not a correctness risk to served output.
**Resolution:** Fixed locally on `fix/tennis-ensemble-market-reporting`;
both implementation steps approved by the user on 2026-10-19. The API and
CLI now expose ensemble-market pairs with independent group counts, losses
and paired uncertainty, requiring no ELO or ML. The model page displays the
new table and labels the preserved all-four table, headline and calibration.
Synthetic regressions cover missing/gated components, market-free exclusion,
version isolation, singleton uncertainty and CLI/API agreement. Full Verify:
3,021 API tests, 632 web tests, typecheck and build passed. Browser fixture
checks cover no-ML, populated/empty versions, loading/error/retry and 390px
scroll containment. No model, adoption rule or holdout changed; no deployment
claim. Re-reviewed by `/audit F-07` on 2026-10-19: the original coverage gap
is repaired, the old comparison contracts are preserved, and no new finding
was identified in the affected paths. F-07 is closed. Other findings were
not re-reviewed by this pass.

**Audit evidence (2026-10-19):**

- Scope: the current F-07 repair, all 14 changed API/web source and test files,
  the active spec, and adjacent consumers. Reviewed quality, security,
  performance and tests. Branch `fix/tennis-ensemble-market-reporting`;
  base `master`, merge base and HEAD both
  `979bff34fd165f05a7a7a3d50f56a8d8605b323d`. The committed range
  `979bff3..HEAD` is empty; repair code is unstaged. No staged or untracked
  source was present. No fetch or pull occurred. Existing overview and other
  working-tree edits were preserved.
- Read the complete repair diff and relevant service/CLI functions, response
  schemas and TypeScript types, prediction repository mapping/pre-start SQL,
  prediction route, raw-row cache and its loader, core grading and signal
  helpers, web API/hook, model page/table/headline/calibration, CSS and tests.
  Checked repository-owned SQL, pure core math, typed boundaries, exact version
  isolation, tour grouping, unchanged holdout/adoption rules, server-controlled
  signals, deterministic tests and bounded grouped output.
- No new database or provider call, mutation, authorization surface or unsafe
  rendering was introduced. The new pair uses the same loaded rows and existing
  scalar scoring helpers; response groups are bounded. The old all-four
  eligibility and calibration remain independent of the new pair counts.
  Cached raw rows and TanStack Query keys remain shared across page consumers.
  This is static performance review, not production profiling.
- From `api/`, `.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider`
  with `tests/test_tennis_prediction_report.py`,
  `tests/test_track_record_service.py`, `tests/test_track_record_routes.py`,
  `tests/test_tennis_grading.py`, `tests/test_track_record_core.py`,
  `tests/test_graded_predictions.py` and `tests/test_tennis_prediction_cache.py`:
  **91 passed**, one existing Starlette/AnyIO deprecation warning.
- From the root, `npm.cmd --prefix web run test --
  src/utils/trackRecord.test.ts`: **18 passed**. Approved execution outside
  the sandbox was used for Vite/esbuild parent-directory access. No skipped,
  focused, xfailed or placeholder tests were found in the reviewed test set.
- An in-memory check loaded the base commit's service and CLI with `git show`
  and compared them with the repair on 1,000 fixed-seed synthetic rows across
  three exact model versions and all four groups. Every original API field and
  CLI section matched exactly. Independently calculated pair eligibility,
  log losses, Brier scores, paired differences and sample standard errors
  matched all 12 version/group comparisons. No new file or live data was used.
- Inspected existing implementation browser evidence, including
  `.playwright-mcp/f07/no-ml-desktop.png` and `all-four-mobile.png`, plus the
  recorded version-switch/loading/error/retry and 390px scroll-containment
  checks. The paired no-ML sample is visible while all-four/calibration remain
  empty; the populated version shows independently counted samples. No fresh
  browser run or keyboard-selection pass is claimed in this audit.
- `git diff --check` passed. The previously passing full Verify evidence
  (3,021 API tests, 632 web tests, typecheck and build) was inspected, not
  rerun. No lint or performance command is configured. No network-backed
  secret/dependency scan or production profiling was run. Excluded dependency,
  build and cache trees, historical datasets, holdout execution, unrelated
  product work and live database/provider/deployment checks. Only this ledger
  was edited by the audit. No further F-07 repair is required.

### tennis-ensemble-market-reporting/F-15 [P3] closed - Frozen-row grading loader does not apply MODELLED_MARKET_FILTER

**File:** api/app/repositories/nfl.py:2266
**Found:** 2026-10-18 by /audit (scope: NFL frozen predictions; lens: correctness)
**Why it matters:** The 34a rule says every reader that projects, grades or
freezes lines applies `MODELLED_MARKET_FILTER`. `get_frozen_gradeable_lines`
grades but relies on the freeze having written modelled lines only (true
today: rows come from `build_slate`, whose CTE filters). A line-only row
written by any other path would reach 27j, where `STAT_COLUMN_BY_MARKET`
has no column and it would settle as `void_dnp` rather than fail loudly.
**Suggested fix:** Add the filter to the `frozen` CTE and a recorded-SQL test,
matching `get_gradeable_prop_lines` and `get_frozen_coverage`. Output is
identical today.
**Resolution:** Fixed by 39c Step 1, approved 2026-10-19. The frozen CTE now
applies `V4_MARKET_FILTER`, the explicit nine-market subset of the modelled
universe, before latest-row selection. Recorded-SQL and mixed-market predicate
tests cover the guard in `test_nfl_v4_markets.py`. Implementation's Full Verify
passed (612 web tests, production build, 2,836 API tests).

Closed by independent `/audit F-15` re-review on 2026-10-19. Reviewed the repaired
query and adjacent market definitions, settlement, coverage and ranking consumers
fresh across quality, security, performance and tests. The nine-market v4
allowlist matches `STAT_COLUMN_BY_MARKET` and is applied inside the frozen CTE
before latest-row selection. All `sport_*` aliases in these queries retain their
NFL filters, season is bound, both timestamps precede known kickoff, and ties
remain deterministic. Rec Targets is selected and settled by separate readers.
The repair adds no query or per-row database call. No new findings in this scope;
no further F-15 repair is needed. Other ledger findings were not re-reviewed.

Audit evidence:

- Scope: F-15's committed repair in `4b79aa0`, reviewed on `master` at
  `979bff3`, plus adjacent grading/reporting paths. No active spec or feature
  branch comparison applies. The pre-existing overview edit was preserved.
- Reviewed `api/app/repositories/nfl.py` market predicates, gradeable/frozen
  readers, mapping and coverage; `app/nfl/markets.py`,
  `app/core/nfl_line_grading.py`, `app/core/prop_ranking_check.py`,
  `app/services/prop_ranking.py`, NFL `prop_source.py`, `track_record.py` and
  `targets_ranking.py`, and `app/repositories/nfl_targets_ranking.py`.
  Checked the project standards, market/sport and version boundaries, pre-start
  grading, repository-owned SQL, pure settlement and deterministic test fixtures.
- From `api/`, `.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider`
  over `test_nfl_v4_markets.py`, `test_nfl_repository.py`,
  `test_nfl_prop_source.py`, `test_prop_ranking_loader.py`,
  `test_prop_ranking_check.py`, `test_prop_ranking_rule.py`,
  `test_nfl_track_record_service.py`, `test_nfl_targets_ranking_repository.py`,
  `test_nfl_targets_ranking_service.py`, `test_nfl_targets_grading.py`,
  `test_nfl_line_grading.py` and `test_sport_props_pipeline.py`: **247 passed**.
  No skipped, focused, xfailed or placeholder tests found in this set.
- An additional in-memory SQLite execution retained the production frozen
  query's predicates, joins, ordering and row mapping, replacing PostgreSQL
  `DISTINCT ON` with equivalent `ROW_NUMBER` selection. All nine v4 markets
  settled; eight line-only markets and targets were excluded. A newer targets
  row sharing a provider prop id could not displace its valid v4 row. Removing
  only the repaired guard admitted 17 rows and displaced that valid row, proving
  the check detects the original defect. No new test or source file was written.
- `git diff --check` passed with the existing overview line-ending warning.
  Excluded historical datasets, holdout execution, real grading/backtest CLIs,
  database/provider access, dependency/build/cache trees, unrelated source and
  browser QA. Runtime evidence is synthetic only; PostgreSQL execution plans,
  production memory and live-data prevalence were not measured. No full Verify,
  build or network-backed security scan was run for this targeted review; no
  local lint or performance command is configured. Only this ledger was edited.
