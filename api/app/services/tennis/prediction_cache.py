"""Short-lived, shared predictions and best picks for the tennis slate.

Every slate load recomputed every prediction. On 2026-10-15, 20 visitors at
once took a median of 4.4 s warm and 18 s right after startup, so a burst now
computes each date set once and the other callers wait for that result.
"""
from __future__ import annotations

import copy
from datetime import date, timedelta
from typing import Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.registry import ModelRegistry
from app.schemas.tennis import BestPicksResponse
from app.services.tennis.live_odds_cache import TimedSingleFlight
from app.services.tennis.predictor import PredictionOutput, predict_today

# Matches the web's 5-minute staleTime for slate data.
CACHE_TTL_SECONDS = 5 * 60
FAILURE_TTL_SECONDS = 10
# Only dates near today are cached, so a visitor cycling match_date cannot
# grow the cache without bound.
DAYS_BACK = 1
DAYS_AHEAD = 2

_PREDICTIONS: TimedSingleFlight[list[PredictionOutput]] = TimedSingleFlight(
    CACHE_TTL_SECONDS, failure_ttl_seconds=FAILURE_TTL_SECONDS
)
_BEST_PICKS: TimedSingleFlight[BestPicksResponse] = TimedSingleFlight(
    CACHE_TTL_SECONDS, failure_ttl_seconds=FAILURE_TTL_SECONDS
)


def cache_key(dates: list[date], today: date) -> tuple[date, ...] | None:
    """The sorted, distinct dates, or None when any falls outside the window."""
    key = tuple(sorted(set(dates)))
    low, high = today - timedelta(days=DAYS_BACK), today + timedelta(days=DAYS_AHEAD)
    if not key or not all(low <= d <= high for d in key):
        return None
    return key


async def cached_predictions(
    db: AsyncSession,
    registry: ModelRegistry,
    dates: list[date],
    today: date,
) -> Optional[list[PredictionOutput]]:
    """Predictions for `dates`, shared for CACHE_TTL_SECONDS; None after a failure.

    Each caller gets its own copy: the best-picks live-odds overlay writes into
    predictions in place.
    """
    key = cache_key(dates, today)
    if key is None:
        return await predict_today(db, registry, dates)
    predictions = await _PREDICTIONS.get(key, lambda: predict_today(db, registry, list(key)))
    return None if predictions is None else copy.deepcopy(predictions)


async def cached_best_picks(
    dates: list[date],
    today: date,
    build: Callable[[], Awaitable[BestPicksResponse]],
) -> Optional[BestPicksResponse]:
    """The best picks `build` returns for `dates`, shared like the predictions.

    Built for every tour; callers filter by tour on their own copy.
    """
    key = cache_key(dates, today)
    if key is None:
        return await build()
    response = await _BEST_PICKS.get(key, build)
    return None if response is None else response.model_copy(deep=True)
