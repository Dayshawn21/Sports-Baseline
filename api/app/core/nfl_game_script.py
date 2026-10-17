"""Pure scoring-environment math for NFL anytime-touchdown backtests."""
from __future__ import annotations

from math import exp, isfinite


def _rate(value: float) -> float:
    return value if isfinite(value) and value > 0 else 0.0


def _weight(value: float) -> float:
    return min(max(value, 0.0), 1.0) if isfinite(value) else 0.0


def implied_team_points(total: float | None, spread: float | None, is_home: bool) -> float | None:
    """Return an NFLverse team's implied points, or `None` when lines are unusable.

    NFLverse `spread_line` is the expected home margin: positive when the home
    team is favored (2,272 of 2,279 home moneyline favorites in 2012-2025).
    """
    if total is None or spread is None or not isfinite(total) or not isfinite(spread):
        return None
    return total / 2 + spread / 2 if is_home else total / 2 - spread / 2


def scoring_environment_probability(
    historical_rate: float, total: float | None, spread: float | None, is_home: bool,
    league_average_implied_points: float, exponent: float, blend_weight: float,
) -> float:
    """Blend a team's implied-total TD rate with historical rate as a Poisson probability."""
    baseline = _rate(historical_rate)
    implied = implied_team_points(total, spread, is_home)
    if implied is None or not isfinite(league_average_implied_points) or league_average_implied_points <= 0:
        return 1 - exp(-baseline)
    fitted_exponent = exponent if isfinite(exponent) else 0.0
    try:
        scale = (max(implied, 0.0) / league_average_implied_points) ** fitted_exponent
    except (OverflowError, ZeroDivisionError):
        scale = 0.0
    environment_rate = baseline * scale if isfinite(scale) and scale >= 0 else 0.0
    rate = (1 - _weight(blend_weight)) * baseline + _weight(blend_weight) * environment_rate
    return 1 - exp(-_rate(rate))
