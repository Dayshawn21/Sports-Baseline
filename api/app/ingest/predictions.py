"""Generate and persist the daily tennis predictions."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, TypedDict

from app.core.tennis_shrink import shadow_version, shrink_toward_market
from app.db.pool import SessionLocal
from app.ml.registry import ModelRegistry
from app.repositories.predictions import insert_prediction, insert_prediction_shadow
from app.services.tennis.ensemble import ENSEMBLE_VERSION
from app.services.tennis.predictor import PredictionOutput, predict_today

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"


class PredictionInsertArgs(TypedDict):
    match_id: int
    model_version: str
    p1_elo_prob: Optional[float]
    p1_ml_prob: Optional[float]
    p1_market_prob: Optional[float]
    p1_ensemble_prob: Optional[float]
    ensemble_weights: dict[str, float]
    quality_flags: list[str]
    feature_snapshot: Optional[dict[str, float]]


def prediction_insert_args(
    prediction: PredictionOutput,
    lgbm_version: Optional[str],
) -> PredictionInsertArgs:
    return {
        "match_id": prediction.match_id,
        "model_version": f"{ENSEMBLE_VERSION}+lgbm-{lgbm_version or 'none'}",
        "p1_elo_prob": prediction.p1_elo_prob,
        "p1_ml_prob": prediction.p1_ml_prob,
        "p1_market_prob": prediction.p1_market_prob,
        "p1_ensemble_prob": prediction.p1_win_prob,
        "ensemble_weights": prediction.ensemble_weights,
        "quality_flags": prediction.quality_flags,
        "feature_snapshot": prediction.feature_snapshot,
    }


class ShadowInsertArgs(TypedDict):
    model_version: str
    p1_prob: float


def shadow_insert_args(prediction: PredictionOutput, served_version: str) -> Optional[ShadowInsertArgs]:
    """The 66a shrink-v1 shadow. Stored even when it equals the served value, so
    coverage can be counted; none without a market price or a served probability."""
    if prediction.p1_win_prob is None or prediction.p1_market_prob is None:
        return None
    return {
        "model_version": shadow_version(served_version),
        "p1_prob": shrink_toward_market(prediction.p1_win_prob, prediction.p1_market_prob),
    }


async def persist_predictions() -> int:
    registry = ModelRegistry(MODELS_DIR)
    today = date.today()
    target_dates = [today, today + timedelta(days=1)]

    async with SessionLocal() as db:
        predictions = await predict_today(db, registry, target_dates)
        for prediction in predictions:
            args = prediction_insert_args(prediction, registry.get_lgbm_version(prediction.tour))
            prediction_id = await insert_prediction(db, **args)
            shadow = shadow_insert_args(prediction, args["model_version"])
            if shadow is not None:
                await insert_prediction_shadow(db, prediction_id, **shadow)
        await db.commit()

    return len(predictions)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Persist today and tomorrow's tennis predictions")
    parser.parse_args()

    count = await persist_predictions()
    logger.info("Inserted %d predictions", count)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
