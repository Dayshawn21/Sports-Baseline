"""Pure game-context features for testing NFL totals and spreads against the close.

The rules are pre-registered in the 24e spec. Any live use must compute the same
values from forecast weather, so change them only through a new backtest.
"""
from __future__ import annotations

from dataclasses import dataclass

INDOOR_ROOFS = frozenset({"dome", "closed"})
# An open retractable roof plays as outdoors.
OUTDOOR_ROOFS = frozenset({"outdoors", "open"})
COLD_BELOW_F = 40
SHORT_WEEK_DAYS = 5
# A bye (14 days) against a normal week (7) is the largest gap worth counting.
REST_DIFF_CAP = 7

TOTAL_FEATURE_NAMES = ("indoor", "wind", "cold", "weather_unknown", "short_week")
SPREAD_FEATURE_NAMES = ("rest_diff",)


@dataclass(frozen=True)
class NflTotalFeatures:
    indoor: float
    wind: float
    cold: float
    weather_unknown: float
    short_week: float

    def vector(self) -> list[float]:
        return [self.indoor, self.wind, self.cold, self.weather_unknown, self.short_week]


@dataclass(frozen=True)
class NflSpreadFeatures:
    rest_diff: float

    def vector(self) -> list[float]:
        return [self.rest_diff]


def _is_short(rest: int | None) -> bool:
    return rest is not None and rest <= SHORT_WEEK_DAYS


def total_features(
    roof: str | None, temp: int | None, wind: int | None, home_rest: int | None, away_rest: int | None,
) -> NflTotalFeatures:
    """Context that could move a total. Unknown weather is its own flag, never zero wind."""
    short_week = float(_is_short(home_rest) or _is_short(away_rest))
    if roof in INDOOR_ROOFS:
        return NflTotalFeatures(1.0, 0.0, 0.0, 0.0, short_week)
    if roof not in OUTDOOR_ROOFS or temp is None or wind is None:
        return NflTotalFeatures(0.0, 0.0, 0.0, 1.0, short_week)
    return NflTotalFeatures(0.0, float(wind), float(max(0, COLD_BELOW_F - temp)), 0.0, short_week)


def spread_features(home_rest: int | None, away_rest: int | None) -> NflSpreadFeatures:
    """Home rest advantage in days, capped both ways; 0 when either side is unknown."""
    if home_rest is None or away_rest is None:
        return NflSpreadFeatures(0.0)
    return NflSpreadFeatures(float(max(-REST_DIFF_CAP, min(REST_DIFF_CAP, home_rest - away_rest))))
