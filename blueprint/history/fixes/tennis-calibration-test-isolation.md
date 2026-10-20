# Fix: Isolate tennis calibration from final test outcomes

**Type:** Fix
**Fixes:** F-08 (P2)
**Status:** Completed 2026-10-19. Step 1 is implemented, verified and approved;
independent audit closed F-08 with no new findings.
**Branch:** `fix/tennis-calibration-test-isolation`

## The problem

`api/train_model.py::train_tour` fits sigmoid calibration on validation
predictions, then compares calibrated and raw log loss on `y_test` to decide
whether to save the calibrator. Final test outcomes therefore select the
artifact that `ModelRegistry` would serve. Test evaluation also sits inside
the calibration exception handler, so a reporting failure can discard a
successfully fitted calibrator.

This is a training evaluation defect. It does not establish future-result
leakage in ordinary live requests or change the historical v6 verdict.

## The fix

- Pre-register the next trainer's policy here: always retain sigmoid
  calibration fitted on the existing validation partition. Do not compare
  raw and calibrated test metrics to choose an artifact. Calibration fitting
  failure stops the run before bundle writes, rather than silently selecting
  a raw model. This policy makes no claim that calibration improves accuracy.
- Separate calibration fitting from test evaluation. The fitting helper takes
  validation predictions and labels only. Final test metrics are descriptive
  reports after the calibration policy is fixed; reporting failures must not
  select another serving artifact.
- Write future bundles under a new training version, with metadata recording
  the fixed policy and validation fitting source. Preserve current v6 and
  older artifacts, and leave registry version support unchanged so the new
  candidate is not automatically served.
- Preserve features, time partitions, Optuna, ensemble weights, moneyline-off
  behavior, and all 26c/26d decisions. No training, export, historical scoring,
  artifact-metrics review, database access or holdout rerun is part of this
  fix. The already-read 2023-2025 holdout is not fresh evidence. Adoption of
  any newly trained bundle requires a separately specified forward validation
  rule fixed before reading its outcomes.

## Build steps

- [x] **1. Isolate calibration policy and prove artifact independence.** Update
  `api/train_model.py`, add focused synthetic tests in `api/tests/`, and document
  the future training policy alongside the trainer's existing documentation.
  Use stubbed model training and temporary artifact directories for orchestration
  tests; do not load real training datasets or existing model metrics.
  **Done when:** changing only final test labels changes descriptive metrics
  but leaves the selected base model, calibration parameters, calibration
  presence and policy metadata identical, including cases where raw versus
  calibrated loss rankings reverse. Calibration fitting failure writes no
  bundle. Test-report failure cannot trigger raw-model fallback. The candidate
  version cannot overwrite current artifacts and is not enabled in the live
  registry. The relevant tests and full Verify pass. Update the local employer
  guide if its evaluation explanation needs changing, describing this as a
  verified trainer repair with no retraining or serving adoption.

## Verify

- Run focused calibration-policy and orchestration regressions, plus existing
  training-feature, mirroring and registry-guard tests, entirely on fixtures.
- Run the documented full Verify gate using the API venv:
  `npm --prefix web run verify && cd api && python -m pytest`.
  On this PowerShell host, use `npm.cmd` and run the halves separately if needed.
- Review the diff to confirm no model bundle, historical dataset, registry
  serving-version allowlist, ensemble rule or validation verdict changed.
- Mark F-08 `fixed` only after the implementation and verification succeed;
  an independent `/audit` must re-review it before closure.

## Implementation evidence (2026-10-19)

- `api/train_model.py` now fits validation-only sigmoid calibration before test
  evaluation and always saves it. Fit and reporting exceptions propagate before
  bundle writes. Future output uses v7 and records the fixed policy in metadata;
  the live registry's supported versions remain unchanged.
- `api/tests/test_train_calibration.py`: seven synthetic cases cover both tuning
  paths, reversed test loss rankings with identical model/calibration artifacts,
  fitting failure, raw/calibrated/bin report failures, preservation of existing
  bundles and refusal to load v7 in the registry. LightGBM training, tuning and
  walk-forward scoring are stubbed; sigmoid fits use tiny synthetic fixtures.
- Focused command from `api/`:
  `.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/test_train_calibration.py tests/test_train_features.py tests/test_train_mirroring.py tests/test_registry_guards.py`
  passed all 39 tests.
- Full Verify ran as the documented PowerShell-compatible halves:
  `npm.cmd --prefix web run verify` (630 tests, TypeScript and production build
  passed) and, from `api/`, `.venv\Scripts\python.exe -m pytest` (3,012 passed).
  The first web attempt hit esbuild sandbox filesystem restrictions; the
  approved rerun outside the sandbox passed. Existing dependency deprecation
  and bundle-size warnings remain nonblocking.
- Updated the ignored local employer guide to explain the evaluation repair,
  its synthetic proof, and the separate future adoption requirement.
- No real training/export, historical scoring, database operation, model-bundle
  modification or serving change was performed. The pre-existing edit to
  `project-overview.md` was left intact. Nothing was committed.
- To try the fix safely, rerun the focused command above; do not run the training
  CLI as a smoke test. The user approved Step 1 on 2026-10-19; the step is checked
  off. Independent audit closed F-08 on 2026-10-19 with no new findings.

## Completion verification (2026-10-19)

- Independent `/audit F-08`: closed F-08; 39 focused regressions passed.
- Full Verify rerun as the documented PowerShell-compatible halves:
  `npm.cmd --prefix web run verify` passed TypeScript, 630 web tests and the
  production build. From `api/`, `.venv\Scripts\python.exe -B -m pytest -q
  -p no:cacheprovider` passed 3,012 tests with one dependency deprecation warning.
  The initial sandbox web attempt failed on esbuild directory access; the
  approved retry outside the sandbox passed. The existing bundle-size warning
  is nonblocking.
- Invariants review: clean. The candidate uses v7, registry support remains
  v6/v5/v4, and no holdout execution, real retraining, artifact replacement,
  serving change or database operation occurred.
- Updated the ignored local employer guide to record independent audit closure.
  It remains untracked and is excluded from staging.
- The pre-existing `project-overview.md` edit is unrelated to this fix and is
  preserved outside the completion commit. No build-plan item changes for a fix.
- How to try safely: from `api/`, run
  `.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
  tests/test_train_calibration.py tests/test_train_features.py
  tests/test_train_mirroring.py tests/test_registry_guards.py` (39 passing cases).
  Do not run the real training CLI as a smoke test. Adoption of a newly trained
  candidate still requires a separately specified forward validation.

## Findings

### tennis-calibration-test-isolation/F-08 [P2] closed - Training chooses whether to serve calibration using test outcomes

**File:** api/train_model.py:646; api/train_model.py:654
**Found:** 2026-10-18 by /audit (scope: tennis prediction training/serving boundary; lenses: evaluation leakage, tests)
**Why it matters:** The calibration curve is fitted on validation predictions,
but whether it is retained is decided by comparing calibrated and raw log loss
on `y_test`. That makes the nominal test set part of model selection. The
registry loads the saved calibration artifact when present. This is a confirmed
evaluation-design defect in the training code, not evidence that future match
results enter an ordinary live request, and not a new assessment of historical
v6 performance. No training, test-data export, artifact metrics review or
historical scoring was run in this audit. Its direct forecast impact is limited
to the ML component and no-market fallback; market-priced v3 gives ML zero weight.
**Suggested fix:** In a future training version, pre-register the calibration
choice or select it using development-only folds; keep final test labels out of
the selection function. A synthetic test should show that altering test labels
cannot change the selected artifact. Any newly trained/calibrated serving
artifact still needs forward validation. Preserve the current artifacts and all
26c/26d decisions; the already-read 2023-2025 holdout is not fresh evidence.
**Resolution:** Repair implemented and verified on
`fix/tennis-calibration-test-isolation`, approved by the user on 2026-10-19.
The future v7 trainer always retains validation-fitted sigmoid
calibration, records the fixed policy, and stops before writes on fitting or
reporting failure. Synthetic regressions reverse final test labels and loss
rankings without changing the saved model or calibration, and verify v7 is not
loaded by the live registry. Focused tests: 39 passed. Full Verify: 630 web tests,
TypeScript and production build, 3,012 API tests passed. Current bundles and
26c/26d decisions are unchanged; no real retraining or holdout scoring occurred.
Closed by independent `/audit F-08` re-review on 2026-10-19. Reviewed the
repair and surrounding training, reporting, serialization and registry code
fresh across quality, security, performance and tests. Validation-only fitting
at `api/train_model.py:635` precedes test evaluation; calibration is retained
unconditionally at lines 717-727. No test-dependent artifact selection or raw
fallback remains in the trainer. Fit/report exceptions propagate before the
first bundle write. The registry's supported versions remain v6/v5/v4, so v7
cannot take over live serving. No new findings in this scope.

Audit evidence:

- Branch: `fix/tennis-calibration-test-isolation`; local base `master`, merge
  base and HEAD `93a09e68e690435e0b3e87ea5601e632c07acc6e`. The committed
  `master..HEAD` range is empty; the repair is unstaged and its new test file
  is untracked. Reviewed those changes, the active spec and adjacent code.
- Reviewed `api/train_model.py` feature/version declarations and training/CLI
  paths; `api/app/ml/registry.py`; `api/tests/test_train_calibration.py`,
  `test_train_features.py`, `test_train_mirroring.py`,
  `test_registry_guards.py` and `conftest.py`; the project instructions,
  standards, overview, active spec and CI verification configuration.
- From `api/`, `.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
  tests/test_train_calibration.py tests/test_train_features.py
  tests/test_train_mirroring.py tests/test_registry_guards.py`: **39 passed**.
  Both tuning paths, reversed test loss rankings, fit/report failure isolation,
  old-bundle preservation and v7 rejection are covered. No skipped, focused,
  xfailed or placeholder tests found in this set. `git diff --check` passed
  with an existing line-ending warning for `project-overview.md`.
- Checked fixed calibration policy, final-test isolation, artifact version
  separation, trusted local serialization, bounded added work, type hints and
  fixture isolation against the spec and standards. No source edits or new
  repair are needed for F-08. Other findings were not re-reviewed.
- Excluded real training/export, stored model metrics and historical datasets,
  holdout scoring, database/provider access, dependency/build/cache trees,
  unrelated source and browser QA. Runtime evidence is synthetic only.
  Full Verify was not rerun in this focused audit; its earlier results above
  are implementation evidence. No lint/performance command is configured;
  gitleaks is not installed locally, so no vulnerability/secret scan ran.
  Forward validation remains a separate requirement before candidate adoption.
