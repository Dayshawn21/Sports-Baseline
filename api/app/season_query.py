"""The `season` query parameter of the model track-record routes, checked before any cache (F-25)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException

from app.core.model_season import MODEL_FIRST_SEASON, is_model_season


def model_season(season: int) -> int:
    if not is_model_season(season, datetime.now(UTC).date()):
        raise HTTPException(
            status_code=422,
            detail=f"season must be a starting year from {MODEL_FIRST_SEASON} to this year",
        )
    return season


def optional_model_season(season: int | None = None) -> int | None:
    return None if season is None else model_season(season)
