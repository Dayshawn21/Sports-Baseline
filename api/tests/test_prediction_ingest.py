from datetime import datetime

from app.ingest.predictions import prediction_insert_args
from app.services.tennis.predictor import PredictionOutput


def _prediction() -> PredictionOutput:
    return PredictionOutput(
        match_id=42,
        start_utc=datetime(2026, 8, 26, 18, 0),
        p1_name="Player One",
        p2_name="Player Two",
        tour="ATP",
        surface="Hard",
        tournament="Test Open",
        round="R32",
        p1_win_prob=0.63,
        p2_win_prob=0.37,
        p1_elo_prob=0.60,
        p1_ml_prob=0.65,
        p1_market_prob=0.58,
        ensemble_weights={"elo": 0.35, "ml": 0.40, "market": 0.25},
        quality_flags=["stale_odds"],
        p1_odds_american=-150,
        p2_odds_american=130,
        h2h_p1_wins=2,
        h2h_p2_wins=1,
        feature_snapshot={"d_elo": 42.5, "d_rank_log": -0.3},
    )


def test_prediction_insert_args_records_loaded_lgbm_version() -> None:
    args = prediction_insert_args(_prediction(), "v5")

    assert args == {
        "match_id": 42,
        "model_version": "ensemble-v3+lgbm-v5",
        "p1_elo_prob": 0.60,
        "p1_ml_prob": 0.65,
        "p1_market_prob": 0.58,
        "p1_ensemble_prob": 0.63,
        "ensemble_weights": {"elo": 0.35, "ml": 0.40, "market": 0.25},
        "quality_flags": ["stale_odds"],
        "feature_snapshot": {"d_elo": 42.5, "d_rank_log": -0.3},
    }


def test_prediction_insert_args_records_missing_lgbm_version() -> None:
    args = prediction_insert_args(_prediction(), None)

    assert args["model_version"] == "ensemble-v3+lgbm-none"


def test_prediction_insert_args_forwards_the_feature_snapshot() -> None:
    # The column existed from migration 0001 but the ingest hardcoded None, so every
    # stored prediction was ungradeable against the inputs it was made from.
    args = prediction_insert_args(_prediction(), "v4")

    assert args["feature_snapshot"] == {"d_elo": 42.5, "d_rank_log": -0.3}


def test_prediction_insert_args_passes_through_a_missing_snapshot() -> None:
    prediction = _prediction()
    prediction.feature_snapshot = None

    assert prediction_insert_args(prediction, "v4")["feature_snapshot"] is None
