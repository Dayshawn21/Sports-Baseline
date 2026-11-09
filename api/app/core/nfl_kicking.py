"""Kicking stats by distance (item 27l), named as in the NFLverse weekly stats file."""
from __future__ import annotations

KICKING_DISTANCE_BANDS = ("0_19", "20_29", "30_39", "40_49", "50_59", "60_")
KICKING_DISTANCE_COLUMNS: tuple[str, ...] = (
    *(f"fg_made_{band}" for band in KICKING_DISTANCE_BANDS),
    *(f"fg_missed_{band}" for band in KICKING_DISTANCE_BANDS),
    "pat_missed",
)
