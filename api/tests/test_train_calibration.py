"""Final test labels affect reports, never the fitted candidate bundle."""

import json
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

import train_model as trainer
from app.ml.registry import MIN_TRAINING_ROWS, ModelRegistry


class StubBooster:
    def __init__(self, train: lgb.Dataset, early_stop: lgb.Dataset,
                 params: dict[str, object]) -> None:
        self.state = {
            "train_labels": train.label.tolist(),
            "early_stop_labels": early_stop.label.tolist(),
            "params": params,
        }

    def predict(self, features: np.ndarray) -> np.ndarray:
        return np.where(features[:, 0] > 0, 0.9, 0.1)

    def feature_importance(self, importance_type: str) -> np.ndarray:
        return np.array([1])

    def save_model(self, path: str) -> None:
        Path(path).write_text(json.dumps(self.state))


def _frame(reverse_test: bool = False) -> pd.DataFrame:
    offsets = [base + day for base in (0, 150, 300, 600) for day in range(4)]
    labels = [0, 0, 1, 1] * 4
    if reverse_test:
        labels[-4:] = [1, 1, 0, 0]
    return pd.DataFrame({
        "match_date": pd.Timestamp("2030-01-01") + pd.to_timedelta(offsets, unit="D"),
        "tour": ["ATP"] * 16,
        "label": labels,
        "d_elo": [-2.0, -1.0, 1.0, 2.0] * 4,
    })


@pytest.fixture
def synthetic_trainer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(trainer, "MIN_TRAINING_ROWS", 16)

    def train(params: dict[str, object], data: lgb.Dataset, num_boost_round: int,
              valid_sets: list[lgb.Dataset], callbacks: list[object]) -> StubBooster:
        return StubBooster(data, valid_sets[0], params)

    def walk_forward(df: pd.DataFrame, features: list[str],
                     params: dict[str, object]) -> list[dict[str, float]]:
        return [{"accuracy": 0.5, "log_loss": 0.7, "brier": 0.25, "auc": 0.5}]

    monkeypatch.setattr(trainer.lgb, "train", train)
    monkeypatch.setattr(trainer, "_walk_forward_cv", walk_forward)


@pytest.mark.parametrize("use_optuna", [False, True])
def test_test_labels_cannot_select_saved_artifacts(
    synthetic_trainer: None, monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path, use_optuna: bool,
) -> None:
    tuning_labels = []

    def tune(x_train: np.ndarray, y_train: np.ndarray, x_val: np.ndarray,
             y_val: np.ndarray, features: list[str], trials: int) -> dict[str, object]:
        tuning_labels.append((y_train.copy(), y_val.copy()))
        return {"objective": "binary", "learning_rate": 0.05, "n_estimators": 10}

    monkeypatch.setattr(trainer, "_optuna_tune", tune)
    # The tuner is stubbed even when Optuna is absent locally.
    monkeypatch.setattr(trainer, "optuna", object())
    bundles = []
    for reverse in (False, True):
        directory = tmp_path / str(reverse)
        directory.mkdir()
        monkeypatch.setattr(trainer, "MODELS_DIR", directory)
        meta = trainer.train_tour(_frame(reverse), "ATP", ["d_elo"], use_optuna)
        stem = directory / f"lgbm_tennis_{trainer.MODEL_VERSION}_atp"
        calibration = joblib.load(f"{stem}_calibration.joblib")
        saved_meta = json.loads(Path(f"{stem}_meta.json").read_text())
        assert saved_meta == meta
        assert meta["calibration"] == "sigmoid"
        assert meta["calibration_policy"] == "always_sigmoid_validation_v1"
        assert meta["calibration_fit_partition"] == "val"
        bundles.append((Path(f"{stem}.txt").read_bytes(), calibration, meta))

    first_model, first_cal, first_meta = bundles[0]
    second_model, second_cal, second_meta = bundles[1]
    assert first_model == second_model
    np.testing.assert_array_equal(first_cal.coef_, second_cal.coef_)
    np.testing.assert_array_equal(first_cal.intercept_, second_cal.intercept_)
    np.testing.assert_array_equal(first_cal.classes_, second_cal.classes_)
    # Validation stays unmirrored, and the saved fit uses only its four labels.
    expected = LogisticRegression().fit(np.array([[0.1], [0.1], [0.9], [0.9]]),
                                        np.array([0, 0, 1, 1]))
    np.testing.assert_array_equal(first_cal.coef_, expected.coef_)
    np.testing.assert_array_equal(first_cal.intercept_, expected.intercept_)
    assert first_meta["metrics"]["test"] != second_meta["metrics"]["test"]
    for meta, calibrated_wins in ((first_meta, False), (second_meta, True)):
        losses = meta["metrics"]
        assert (losses["test_calibrated"]["log_loss"] < losses["test"]["log_loss"]) == calibrated_wins
    if use_optuna:
        assert len(tuning_labels) == 2
        for first, second in zip(tuning_labels[0], tuning_labels[1]):
            np.testing.assert_array_equal(first, second)


def test_calibration_fit_failure_writes_no_bundle(
    synthetic_trainer: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(trainer, "MODELS_DIR", tmp_path)
    frame = _frame()
    frame.loc[8:11, "label"] = 1
    with pytest.raises(ValueError, match="at least 2 classes"):
        trainer.train_tour(frame, "ATP", ["d_elo"], use_optuna=False)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("failing_report", ["raw_test", "calibrated_test", "bins"])
def test_test_report_failure_aborts_without_raw_fallback(
    synthetic_trainer: None, monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path, failing_report: str,
) -> None:
    monkeypatch.setattr(trainer, "MODELS_DIR", tmp_path)
    evaluate = trainer._eval_metrics
    calls = 0

    def fail_report(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
        nonlocal calls
        calls += 1
        if calls == (2 if failing_report == "raw_test" else 3):
            raise RuntimeError("synthetic report failure")
        return evaluate(y_true, y_prob)

    def fail_bins(y_true: np.ndarray, y_prob: np.ndarray) -> list[dict[str, float]]:
        raise RuntimeError("synthetic report failure")

    if failing_report == "bins":
        monkeypatch.setattr(trainer, "_calibration_report", fail_bins)
    else:
        monkeypatch.setattr(trainer, "_eval_metrics", fail_report)
    with pytest.raises(RuntimeError, match="synthetic report failure"):
        trainer.train_tour(_frame(), "ATP", ["d_elo"], use_optuna=False)
    assert list(tmp_path.iterdir()) == []


def test_candidate_preserves_serving_bundles_and_is_not_loaded(
    synthetic_trainer: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(trainer, "MODELS_DIR", tmp_path)
    assert trainer.MODEL_VERSION == "v7"
    preserved = {}
    for version in ("v4", "v5", "v6"):
        for tour in ("atp", "wta"):
            for suffix in (".txt", "_features.txt", "_meta.json", "_calibration.joblib"):
                path = tmp_path / f"lgbm_tennis_{version}_{tour}{suffix}"
                preserved[path] = b"existing serving artifact"
                path.write_bytes(preserved[path])
    trainer.train_tour(_frame(), "ATP", ["d_elo"], use_optuna=False)
    for path, original in preserved.items():
        assert path.read_bytes() == original

    # Only a candidate bundle is present here, with enough rows to pass the row guard.
    isolated = tmp_path / "candidate_only"
    isolated.mkdir()
    for path in tmp_path.glob("lgbm_tennis_v7_*"):
        (isolated / path.name).write_bytes(path.read_bytes())
    meta_path = isolated / "lgbm_tennis_v7_atp_meta.json"
    meta = json.loads(meta_path.read_text())
    meta["rows"]["total"] = MIN_TRAINING_ROWS
    meta_path.write_text(json.dumps(meta))

    def unexpected_load(*args: object, **kwargs: object) -> None:
        pytest.fail("The live registry must not load the v7 candidate")

    monkeypatch.setattr(lgb, "Booster", unexpected_load)
    registry = ModelRegistry(isolated)
    assert registry.atp_model is None
    assert registry.wta_model is None
    assert registry._lgbm_versions == {}
