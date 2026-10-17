# Remove Legacy XGBoost Fallback

**Type:** Fix

## The problem

`ModelRegistry` loads an unused XGBoost fallback and its joblib calibration
artifact at API startup. The calibration artifact embeds pickled
`XGBClassifier` instances from an incompatible environment, so loading it emits
an XGBoost serialization warning. The calibrator also fails under the current
scikit-learn and XGBoost versions, while the active prediction paths use only
the ATP and WTA LightGBM models.

## The fix

Remove the legacy XGBoost runtime path from the model registry and remove the
unused `xgboost` dependency. Preserve the active LightGBM behavior and leave the
ignored local XGBoost artifact files untouched.

## Build steps

- [x] Remove the XGBoost imports, startup loading, registry state, prediction
  method, and dependency declaration.
  - Done when `ModelRegistry` loads only ATP and WTA LightGBM models, runtime
    source and requirements contain no XGBoost references, and existing local
    model artifacts have not been deleted.

## Verify

- From `api/`, initialize `ModelRegistry(Path("models"))` with Python warnings
  treated as errors and confirm startup completes without the reported warning.
- Run `pytest` from `api/`.
- Search `api/app/` and `api/requirements.txt` for `xgboost`, `predict_xgb`, and
  `_load_xgb_fallback`; expect no matches.
