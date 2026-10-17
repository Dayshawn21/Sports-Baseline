"""Red-zone opportunity as an anytime-TD signal.

Expected touchdowns are modeled as linear in opportunities (a base rate plus a
per-carry and per-target conversion value near the goal line), so applying the
model to per-game averages is exact rather than an approximation. The
coefficients and blend weight are inputs: the backtest fits them, and production
reads frozen values only if the backtest earns them.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite

from app.core.nfl_projection import TD_PRIOR_GAMES, TD_SEASON_WEIGHTS


@dataclass(frozen=True)
class NflRedZoneRates:
    """Per-game red-zone opportunities. Inside-5 is a subset of inside-20."""

    rz20_carries: float
    rz20_targets: float
    rz5_carries: float
    rz5_targets: float


@dataclass(frozen=True)
class NflRedZoneSeason:
    season: int
    # Games with play-by-play loaded; NULL-count games are not evidence.
    games: int
    rates: NflRedZoneRates


@dataclass(frozen=True)
class NflRedZoneCoefficients:
    """TDs per game at zero opportunity, and TDs per opportunity in each disjoint band."""

    intercept: float
    rz5_carry: float
    rz6_20_carry: float
    rz5_target: float
    rz6_20_target: float


def _clean(value: float) -> float:
    return value if isfinite(value) and value > 0 else 0.0


def _clean_values(rates: NflRedZoneRates) -> tuple[float, float, float, float]:
    return (
        _clean(rates.rz20_carries), _clean(rates.rz20_targets),
        _clean(rates.rz5_carries), _clean(rates.rz5_targets),
    )


def red_zone_rates(
    seasons: list[NflRedZoneSeason], line_season: int, position_rates: NflRedZoneRates,
) -> tuple[NflRedZoneRates, float]:
    """Recency-weighted per-game rates shrunk toward the position, as (rates, weighted games).

    Same season weights and prior as the TD baseline, so both signals trust a
    player's history to the same degree.
    """
    totals = [TD_PRIOR_GAMES * value for value in _clean_values(position_rates)]
    weighted_games = 0.0
    for entry in seasons:
        age = line_season - entry.season
        if entry.games <= 0 or not 0 <= age < len(TD_SEASON_WEIGHTS):
            continue
        weight = TD_SEASON_WEIGHTS[age] * entry.games
        totals = [total + weight * value for total, value in zip(totals, _clean_values(entry.rates))]
        weighted_games += weight
    denominator = weighted_games + TD_PRIOR_GAMES
    return NflRedZoneRates(*(total / denominator for total in totals)), weighted_games


def expected_td_rate(rates: NflRedZoneRates, coefficients: NflRedZoneCoefficients) -> float:
    rz20_carries, rz20_targets, rz5_carries, rz5_targets = _clean_values(rates)
    rate = (
        coefficients.intercept
        + coefficients.rz5_carry * rz5_carries
        + coefficients.rz6_20_carry * max(rz20_carries - rz5_carries, 0.0)
        + coefficients.rz5_target * rz5_targets
        + coefficients.rz6_20_target * max(rz20_targets - rz5_targets, 0.0)
    )
    return _clean(rate)


def red_zone_td_probability(
    historical_rate: float, rates: NflRedZoneRates,
    coefficients: NflRedZoneCoefficients, blend_weight: float,
) -> float:
    """Unrounded anytime-TD probability from a blend of TD history and red-zone opportunity."""
    weight = min(max(blend_weight, 0.0), 1.0) if isfinite(blend_weight) else 0.0
    rate = (1 - weight) * _clean(historical_rate) + weight * expected_td_rate(rates, coefficients)
    return 1 - exp(-rate)
