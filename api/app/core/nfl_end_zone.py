"""End-zone target as an anytime-TD signal.

The runner fits the intercept and target conversion value. This module only
combines pre-week rates and turns a supplied rate into an unrounded probability.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite

from app.core.nfl_projection import TD_PRIOR_GAMES, TD_SEASON_WEIGHTS


@dataclass(frozen=True)
class NflEndZoneSeason:
    season: int
    # Games with loaded play-by-play; a NULL weekly count is not evidence.
    games: int
    targets_per_game: float


@dataclass(frozen=True)
class NflEndZoneCoefficients:
    intercept: float
    per_target: float


def _clean(value: float) -> float:
    return value if isfinite(value) and value > 0 else 0.0


def end_zone_target_rate(
    seasons: list[NflEndZoneSeason], line_season: int, position_rate: float,
) -> tuple[float, float]:
    """Recency-weighted targets per game, shrunk to the position rate."""
    total = TD_PRIOR_GAMES * _clean(position_rate)
    weighted_games = 0.0
    for entry in seasons:
        age = line_season - entry.season
        if entry.games <= 0 or not 0 <= age < len(TD_SEASON_WEIGHTS):
            continue
        weight = TD_SEASON_WEIGHTS[age] * entry.games
        total += weight * _clean(entry.targets_per_game)
        weighted_games += weight
    return total / (weighted_games + TD_PRIOR_GAMES), weighted_games


def end_zone_td_probability(
    historical_rate: float, targets_per_game: float,
    coefficients: NflEndZoneCoefficients, blend_weight: float,
) -> float:
    """Blend historical TD rate with a fitted end-zone-target expected rate."""
    weight = min(max(blend_weight, 0.0), 1.0) if isfinite(blend_weight) else 0.0
    target_rate = _clean(coefficients.intercept) + _clean(coefficients.per_target) * _clean(targets_per_game)
    rate = (1 - weight) * _clean(historical_rate) + weight * target_rate
    return 1 - exp(-rate)
