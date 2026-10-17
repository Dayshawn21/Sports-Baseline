"""
ModelRegistry — loads all ML model artifacts once at app startup.

Usage (in FastAPI lifespan):
    registry = ModelRegistry(Path("models"))
    app.state.registry = registry

Usage (in service):
    prob = request.app.state.registry.predict("ATP", features)
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Optional

import joblib
import lightgbm as lgb
import numpy as np

logger = logging.getLogger(__name__)

# v5 was trained on ~220 ATP / ~270 WTA rows (three weeks of ingest) and scored 0.56
# walk-forward AUC against v4's 0.76. Reject any bundle that thin so a bad training run
# cannot silently take over serving again.
MIN_TRAINING_ROWS = 5000

# v6 is served in preference to v4. It is not measurably more accurate: on held-out
# matches the two cannot be separated honestly, because v4's rolling-stat features are
# stored as a current snapshot and so already reflect the result of any past match used
# to score it. Retrospective comparison flatters v4 for the same reason its training
# flattered it.
#
# v6 is preferred on grounds that can be checked rather than measured: it is fit only on
# features knowable before the match, and its serving vector is verified identical to its
# training vector. predictions.feature_snapshot now records every prediction, so live
# results will settle the comparison properly.
_SUPPORTED_VERSIONS = ("v6", "v5", "v4")
_MODEL_TOURS = frozenset({"ATP", "WTA"})


class ModelRegistry:
    # Predictions run in worker threads (37e), so calls on a booster never overlap.
    _predict_lock = threading.Lock()

    def __init__(self, models_dir: Path) -> None:
        self._dir = models_dir
        self._lgbm_versions: dict[str, str] = {}
        self._missing_fills: dict[str, float] = {}
        self._load_lgbm_atp()
        self._load_lgbm_wta()
        logger.info("ModelRegistry loaded: ATP=%s  WTA=%s",
                    self.atp_features is not None,
                    self.wta_features is not None)

    def _meta(self, meta_path: Path) -> dict:
        if not meta_path.exists():
            return {}
        try:
            return json.loads(meta_path.read_text())
        except (OSError, ValueError):
            logger.warning("Unreadable model metadata at %s", meta_path)
            return {}

    @staticmethod
    def _training_rows(meta: dict) -> Optional[int]:
        """Row count a bundle reports training on, or None when it does not say."""
        rows = meta.get("rows")
        if isinstance(rows, dict) and isinstance(rows.get("total"), (int, float)):
            return int(rows["total"])
        return None

    @staticmethod
    def _has_crlf(model_path: Path) -> bool:
        """Whether a model file carries CRLF endings, which LightGBM cannot read.

        LightGBM parses the file as parallel byte-offset chunks, so CRLF shifts every
        chunk boundary mid-token and the loader aborts the process instead of raising.
        No try/except can catch that, so the check has to happen before the load.
        A core.autocrlf checkout is what introduces them; .gitattributes marks these
        artifacts binary to stop it recurring.
        """
        with model_path.open("rb") as fh:
            return b"\r\n" in fh.read(65536)

    @staticmethod
    def _missing_fill(meta: dict) -> float:
        """The value a bundle used for absent features while training.

        Inference has to encode "missing" the same way the model was taught to read it.
        Bundles with no declaration predate the switch and were trained with zero-fill.
        """
        return float("nan") if meta.get("missing_value_fill") == "nan" else 0.0

    def _load_lgbm_bundle(self, tour: str) -> tuple[Optional[lgb.Booster], object, Optional[list[str]]]:
        tour_lower = tour.lower()
        for version in _SUPPORTED_VERSIONS:
            model_path = self._dir / f"lgbm_tennis_{version}_{tour_lower}.txt"
            calib_path = self._dir / f"lgbm_tennis_{version}_{tour_lower}_calibration.joblib"
            feat_path = self._dir / f"lgbm_tennis_{version}_{tour_lower}_features.txt"
            meta_path = self._dir / f"lgbm_tennis_{version}_{tour_lower}_meta.json"
            if not model_path.exists():
                continue

            meta = self._meta(meta_path)
            rows = self._training_rows(meta)
            if rows is None:
                # Without metadata the row floor cannot be applied and the fill
                # convention is unknown, so the bundle cannot be shown to be safe. This
                # is not hypothetical: meta.json was gitignored, and a checkout without
                # it served the 217-row v5 bundle because nothing could rule it out.
                logger.warning(
                    "Skipping %s %s: no readable metadata at %s, cannot verify it",
                    tour.upper(), version, meta_path.name,
                )
                continue
            if rows < MIN_TRAINING_ROWS:
                logger.warning(
                    "Skipping %s %s: trained on %d rows, below the %d minimum",
                    tour.upper(), version, rows, MIN_TRAINING_ROWS,
                )
                continue

            if self._has_crlf(model_path):
                logger.warning(
                    "Skipping %s %s: %s has CRLF line endings, which abort the LightGBM "
                    "loader. Check .gitattributes and re-checkout the file.",
                    tour.upper(), version, model_path.name,
                )
                continue

            model = lgb.Booster(model_file=str(model_path))
            calibration = joblib.load(calib_path) if calib_path.exists() else None
            features = [l.strip() for l in feat_path.read_text().splitlines() if l.strip()] if feat_path.exists() else None
            self._lgbm_versions[tour.upper()] = version
            self._missing_fills[tour.upper()] = self._missing_fill(meta)
            logger.info("Loaded %s LightGBM model from %s", tour.upper(), model_path)
            return model, calibration, features

        logger.warning("%s model not found in supported versions", tour.upper())
        return None, None, None

    # ── LightGBM ATP ──────────────────────────────────────────────────────────

    def _load_lgbm_atp(self) -> None:
        self.atp_model: Optional[lgb.Booster] = None
        self.atp_calibration = None
        self.atp_features: Optional[list[str]] = None
        self.atp_model, self.atp_calibration, self.atp_features = self._load_lgbm_bundle("ATP")

    # ── LightGBM WTA ──────────────────────────────────────────────────────────

    def _load_lgbm_wta(self) -> None:
        self.wta_model: Optional[lgb.Booster] = None
        self.wta_calibration = None
        self.wta_features: Optional[list[str]] = None
        self.wta_model, self.wta_calibration, self.wta_features = self._load_lgbm_bundle("WTA")

    # ── Prediction ────────────────────────────────────────────────────────────

    @staticmethod
    def serves_tour(tour: Optional[str]) -> bool:
        """Whether a bundle exists for this tour. v6 trained on ATP and WTA only, so a
        Challenger match scored by either model is outside anything it has seen."""
        return (tour or "").upper() in _MODEL_TOURS

    def get_lgbm_version(self, tour: str) -> Optional[str]:
        if not self.serves_tour(tour):
            return None
        return self._lgbm_versions.get(tour.upper())

    def predict_lgbm(self, tour: str, feature_vector: dict) -> Optional[float]:
        """
        Run LightGBM prediction for ATP or WTA.

        Args:
            tour: 'ATP' or 'WTA'
            feature_vector: dict mapping feature name → value (gaps filled by caller)

        Returns:
            Calibrated probability p1 wins, or None if model unavailable.
        """
        if not self.serves_tour(tour):
            return None
        is_atp = tour.upper() == "ATP"
        model = self.atp_model if is_atp else self.wta_model
        calib = self.atp_calibration if is_atp else self.wta_calibration
        features = self.atp_features if is_atp else self.wta_features

        if model is None or features is None:
            return None

        fill = self._missing_fills.get(tour.upper(), 0.0)
        row = np.array([[feature_vector.get(f, fill) for f in features]], dtype=np.float32)
        # One row gains nothing from threads, and on the hosted half-CPU instance
        # LightGBM's default thread per visible core stalled the slate for seconds (37e).
        with self._predict_lock:
            raw_prob = float(model.predict(row, num_threads=1)[0])

        if calib is not None:
            try:
                raw_prob = float(calib.predict_proba([[raw_prob]])[0][1])
            except Exception:
                pass

        return float(np.clip(raw_prob, 0.01, 0.99))
