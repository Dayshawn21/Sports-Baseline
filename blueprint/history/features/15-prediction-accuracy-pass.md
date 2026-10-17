# Feature: Prediction accuracy pass

**From build-plan:** feature 15
**Status:** complete

## Goal

Improve the tennis prediction stack so the app serves a safer calibrated model
from features that were knowable before the match, records prediction inputs for
future evaluation, and refuses to serve thin or unverifiable model bundles.

This is a retroactive spec for the already-built `fix/math-audit-stage-1` branch.
The branch is being classified as build-plan item 15 so it can be validated,
audited, archived, and merged through the Blueprint loop before NFL work starts.

## In scope

- Remove the legacy XGBoost fallback path and dependency.
- Serve the v6 LightGBM bundles when their metadata proves they are safe.
- Track and require model metadata needed for training-row guards and missing
  value encoding.
- Preserve prediction feature snapshots so live predictions can be evaluated
  after results settle.
- Train v6 on as-of-date features and keep market price out of the model feature
  vector.
- Ensure serving uses the same feature names and missing-value convention as
  training.
- Improve tennis math correctness around Kelly sizing, best-of-five format,
  qualifying format, and total-games projections.
- Add retry handling for retryable ingest database conflicts.

## Out of scope

- Declaring `pytest` in `api/requirements.txt`; build-plan item 13 remains open.
- Removing one-off scripts; build-plan item 14 remains open.
- Props market or book expansion; build-plan item 16 remains open.
- Multi-sport API, schema, service, or UI work.
- NFL data-source selection or ingest.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff; the user reviews and understands it.
4. The user approves, then chooses whether to commit a checkpoint or continue.
5. `/complete` makes the one feature-level commit and merge.

This spec was written after the branch work already existed, so the build steps
below are checked off to reflect the committed branch state.

## Build steps

- [x] **Step 1 - Remove unsafe fallback model paths** - remove the legacy XGBoost
  fallback, remove the runtime dependency, and serve only verified LightGBM
  bundles. *Done when:* the registry has no XGBoost prediction path, imports do
  not require `xgboost`, and tests cover the registry guard behavior.
- [x] **Step 2 - Make model bundle metadata load-bearing** - track model metadata,
  read training-row counts, reject bundles without readable metadata, reject
  undertrained bundles, and apply the declared missing-value convention at
  serving time. *Done when:* metadata files are no longer ignored, unsafe bundles
  are skipped, and model registry tests cover missing, corrupt, and undertrained
  metadata.
- [x] **Step 3 - Align training and serving features** - build v6 training data
  from as-of-date history, drop market price from the model features, preserve
  the trained feature contract, and mirror it during prediction. *Done when:*
  training tests prove future-looking rolling snapshots do not leak into the
  model, and serving tests prove the vector matches the trained feature list.
- [x] **Step 4 - Persist prediction evidence** - save the feature snapshot used
  for each prediction so settled results can later validate calibration honestly.
  *Done when:* prediction ingest stores the snapshot and repository tests cover
  JSONB writes for weights and snapshots.
- [x] **Step 5 - Correct tennis math and format handling** - fix Kelly sizing and
  EV gates, recognize best-of-five and qualifying formats correctly, model total
  games as a set-count mixture, and keep bankroll and best-pick outputs aligned.
  *Done when:* focused tests cover Kelly, best-of-five, qualifying format, total
  games, odds, and ensemble behavior.
- [x] **Step 6 - Harden ingest writes** - retry transient database conflicts
  during ingest writes without hiding non-retryable errors. *Done when:* retry
  tests cover retryable SQLSTATEs, non-retryable SQLSTATEs, and eventual success.

## Files / areas

- `api/app/ml/`, `api/train_model.py`, and `api/models/` for v6 training,
  metadata, feature contracts, and model serving.
- `api/app/services/tennis/`, `api/app/core/`, and `api/app/ingest/` for
  prediction, bankroll, props math, format handling, and ingest behavior.
- `api/app/db/retry.py` for retryable database conflicts.
- `api/tests/` for the focused regression tests that cover the branch behavior.
- `.gitignore` and `api/requirements.txt` for model artifact and dependency
  bookkeeping.

## Data / contracts

- `predictions.feature_snapshot` remains a JSONB snapshot of the exact feature
  inputs used for a prediction.
- Model metadata files named `api/models/lgbm_tennis_<version>_<tour>_meta.json`
  are load-bearing for bundle eligibility.
- LightGBM feature files remain the serving contract; prediction vectors must be
  ordered from those files, not from ad-hoc dictionary order.
- No database schema change is introduced by this feature.

## Testing

- `cd api && .venv\Scripts\python.exe -m pytest` passed, 475 tests.
- `cd web && npm run build` passed.
- `cd web && npm run test` passed, 31 tests.
- Focused branch audit found no P0/P1 findings.

## Notes for the AI

- Keep `.claude/settings.json` out of the Feature 15 commit; it is unrelated
  local tool state.
- Leave build-plan item 13 open. `pytest` still runs only from the local
  `api/.venv`.
- Leave the parked props-link fix out of this closeout. It is preserved in git
  stash entry `propsfix` and can be resumed after Feature 15 lands.
- Preserve the branch's intent: v6 is preferred because it avoids lookahead and
  has a verifiable serving contract, not because retrospective comparison can
  honestly prove it beats v4.
