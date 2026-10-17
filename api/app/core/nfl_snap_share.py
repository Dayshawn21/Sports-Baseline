"""Offensive snap share as an anytime-TD role signal.

Expected touchdowns are modeled as linear in snap share, then blended with the
player's TD history. Two share forms exist so the backtest can choose between a
season-weighted role (steady) and the latest games (quick to catch a role
change). The coefficients, form, and blend weight are inputs: the backtest fits
them, and production reads frozen values only if the backtest earns them.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite

from app.core.nfl_projection import (
    TD_SEASON_WEIGHTS,
    NflSeasonTouchdowns,
    anytime_td_probability,
    anytime_td_rate,
)

RECENT_SNAP_WINDOW = 4
# Far lighter than TD_PRIOR_GAMES: snap share is steady game to game, while TDs are
# rare and noisy. With the TD prior, four games would carry only 29% of the recent
# form. Fixed before the backtest ran (2026-09-19), not tuned on it.
SNAP_PRIOR_GAMES = 2.0


@dataclass(frozen=True)
class NflSnapSeason:
    season: int
    # Games with a snap row; players with no stored snaps are not evidence.
    games: int
    share: float


@dataclass(frozen=True)
class NflSnapCoefficients:
    """TDs per game at zero snap share, and TDs per game per unit of share (0 to 1)."""

    intercept: float
    per_share: float


# Frozen from the 19m backtest (2026-09-19): fit on 2024, form and weight chosen by
# 2024 RB+TE log loss, scored once on 2025. Holdout RB+TE log loss 0.47489 -> 0.46577,
# Brier 0.15199 -> 0.14989; RB and TE each improved. Production uses the
# season-weighted form (`season_snap_share`), which is what the backtest chose.
SNAP_SHARE_BLEND_WEIGHT = 0.6
SNAP_SHARE_COEFFICIENTS = {
    "RB": NflSnapCoefficients(intercept=-0.046260, per_share=0.965586),
    "TE": NflSnapCoefficients(intercept=-0.018431, per_share=0.328985),
}


def _share(value: float) -> float:
    return min(max(value, 0.0), 1.0) if isfinite(value) else 0.0


def _rate(value: float) -> float:
    return value if isfinite(value) and value > 0 else 0.0


def season_snap_share(
    seasons: list[NflSnapSeason], line_season: int, position_share: float, prior_games: float = SNAP_PRIOR_GAMES,
) -> tuple[float, float]:
    """Recency-weighted share shrunk toward the position, as (share, weighted games).

    Mirrors `red_zone_rates` with the TD baseline's season weights, but its own prior.
    """
    total = prior_games * _share(position_share)
    weighted_games = 0.0
    for entry in seasons:
        age = line_season - entry.season
        if entry.games <= 0 or not 0 <= age < len(TD_SEASON_WEIGHTS):
            continue
        weight = TD_SEASON_WEIGHTS[age] * entry.games
        total += weight * _share(entry.share)
        weighted_games += weight
    return total / (weighted_games + prior_games), weighted_games


def recent_snap_share(
    recent_shares: list[float], position_share: float,
    window: int = RECENT_SNAP_WINDOW, prior_games: float = SNAP_PRIOR_GAMES,
) -> tuple[float, int]:
    """Share over the latest `window` games (oldest first in the input), shrunk toward the position.

    The window crosses season boundaries, so week 1 reads last season's final games.
    """
    latest = recent_shares[-window:] if window > 0 else []
    total = prior_games * _share(position_share) + sum(_share(value) for value in latest)
    return total / (len(latest) + prior_games), len(latest)


def snap_td_probability(
    historical_rate: float, share: float, coefficients: NflSnapCoefficients, blend_weight: float,
) -> float:
    """Unrounded anytime-TD probability from a blend of TD history and snap-share role."""
    weight = min(max(blend_weight, 0.0), 1.0) if isfinite(blend_weight) else 0.0
    expected = _rate(coefficients.intercept + coefficients.per_share * _share(share))
    rate = (1 - weight) * _rate(historical_rate) + weight * expected
    return 1 - exp(-rate)


@dataclass(frozen=True)
class NflSnapEvidence:
    """The player's own snap evidence behind a line; `share` is None when there is none."""

    share: float | None
    games: int


def snap_evidence(seasons: list[NflSnapSeason], line_season: int, position_share: float) -> NflSnapEvidence:
    """The shrunk season share and the raw snap games inside the recency weights."""
    games = sum(
        entry.games for entry in seasons
        if entry.games > 0 and 0 <= line_season - entry.season < len(TD_SEASON_WEIGHTS)
    )
    if not games:
        return NflSnapEvidence(None, 0)
    return NflSnapEvidence(season_snap_share(seasons, line_season, position_share)[0], games)


def production_anytime_td_probability(
    position: str | None,
    td_seasons: list[NflSeasonTouchdowns],
    snap_seasons: list[NflSnapSeason],
    line_season: int,
    position_td_rate: float,
    position_snap_share: float,
) -> tuple[float, float]:
    """The anytime-TD probability users see, as (probability rounded to 2, weighted TD games).

    RB and TE blend in the frozen snap-share model exactly as the backtest scored
    it, including falling back to the position share when the player has no snap
    history. Every other position is `anytime_td_probability` unchanged.
    """
    coefficients = SNAP_SHARE_COEFFICIENTS.get(position or "")
    if coefficients is None:
        return anytime_td_probability(td_seasons, line_season, position_td_rate)
    rate, weighted_games = anytime_td_rate(td_seasons, line_season, position_td_rate)
    share, _ = season_snap_share(snap_seasons, line_season, position_snap_share)
    probability = snap_td_probability(rate, share, coefficients, SNAP_SHARE_BLEND_WEIGHT)
    return round(probability, 2), round(weighted_games, 2)
