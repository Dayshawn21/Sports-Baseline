"""Serving must encode missing inputs the way training did, and only score tours a
bundle was trained on."""
import math
from datetime import date
from types import SimpleNamespace

import numpy as np

from app.ml.feature_contract import NO_DEFAULT_FEATURES
from app.ml.registry import ModelRegistry
from app.services.tennis.feature_builder import build_features


def _match(p1_rank: int | None, p2_rank: int | None) -> SimpleNamespace:
    return SimpleNamespace(
        id=1, tour="ATP", surface="Hard", tournament="Test Open", round="R32",
        best_of=3, match_date=date(2026, 9, 25), p1_id=1, p2_id=2,
        p1_rank=p1_rank, p2_rank=p2_rank,
    )


def _player(birth_date: date | None) -> SimpleNamespace:
    return SimpleNamespace(birth_date=birth_date)


def _features(match: SimpleNamespace, p1: SimpleNamespace, p2: SimpleNamespace) -> dict:
    feat, _ = build_features(
        match=match, p1=p1, p2=p2, p1_elo=None, p2_elo=None,
        p1_stats=None, p2_stats=None, p1_surf_stats=None, p2_surf_stats=None,
        h2h_p1_wins=0, h2h_p2_wins=0, h2h_surf_p1_wins=0, h2h_surf_p2_wins=0,
    )
    return feat


class TestMissingInputsStayMissing:
    def test_unknown_rank_and_age_are_absent_not_zero(self):
        feat = _features(_match(None, 20), _player(None), _player(date(2000, 1, 1)))
        assert "d_rank_log" not in feat
        assert "d_age" not in feat

    def test_missing_elo_is_absent_not_zero(self):
        feat = _features(_match(10, 20), _player(None), _player(None))
        assert "d_elo" not in feat
        assert "d_surface_elo" not in feat

    def test_known_inputs_are_still_computed(self):
        feat = _features(_match(10, 20), _player(date(2000, 1, 1)), _player(date(2000, 1, 1)))
        assert feat["d_rank_log"] == math.log(20) - math.log(10)
        assert feat["d_age"] == 0.0

    def test_contract_names_the_features_training_leaves_unknown(self):
        assert {"d_rank_log", "d_age", "d_elo", "d_surface_elo"} <= NO_DEFAULT_FEATURES


class _Booster:
    """Echoes the served row so a test can see exactly what the model received."""

    def __init__(self) -> None:
        self.rows: list[np.ndarray] = []
        self.num_threads: list[int] = []

    def predict(self, row: np.ndarray, num_threads: int) -> list[float]:
        self.rows.append(row)
        self.num_threads.append(num_threads)
        return [0.6]


def _registry(booster: _Booster) -> ModelRegistry:
    r = ModelRegistry.__new__(ModelRegistry)
    r.atp_model = r.wta_model = booster
    r.atp_calibration = r.wta_calibration = None
    r.atp_features = r.wta_features = ["d_rank_log", "round_ordinal"]
    r._lgbm_versions = {"ATP": "v6", "WTA": "v6"}
    r._missing_fills = {"ATP": float("nan"), "WTA": float("nan")}
    return r


class TestTourRouting:
    def test_challenger_gets_no_ml_probability(self):
        booster = _Booster()
        r = _registry(booster)
        assert r.predict_lgbm("CHALLENGER", {"round_ordinal": 1.0}) is None
        assert booster.rows == []

    def test_challenger_has_no_model_version(self):
        assert _registry(_Booster()).get_lgbm_version("CHALLENGER") is None

    def test_atp_and_wta_are_served(self):
        r = _registry(_Booster())
        assert r.predict_lgbm("ATP", {"round_ordinal": 1.0}) == 0.6
        assert r.predict_lgbm("wta", {"round_ordinal": 1.0}) == 0.6
        assert r.get_lgbm_version("ATP") == "v6"

    def test_an_absent_feature_reaches_the_model_as_nan(self):
        booster = _Booster()
        _registry(booster).predict_lgbm("ATP", {"round_ordinal": 1.0})
        assert math.isnan(booster.rows[0][0][0])

    def test_a_single_row_predicts_on_one_thread(self):
        booster = _Booster()
        _registry(booster).predict_lgbm("ATP", {"round_ordinal": 1.0})
        assert booster.num_threads == [1]
