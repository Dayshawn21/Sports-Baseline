"""Which `season` values a model track-record route will build for (F-25)."""
from __future__ import annotations

from datetime import date

# Earlier than any season a ranking has frozen predictions for, so no real
# season is refused; the bound only keeps arbitrary ints out of the caches.
MODEL_FIRST_SEASON = 2020


def is_model_season(season: int, today: date) -> bool:
    """Seasons are stored by the year they start, so none is later than this year."""
    return MODEL_FIRST_SEASON <= season <= today.year
