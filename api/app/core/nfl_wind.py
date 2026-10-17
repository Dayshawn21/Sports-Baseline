"""Wind for NFL passing props (build-plan item 27k).

Only wind above a threshold counts, and in absolute terms: most games have none,
so a player's baseline average is close to zero and comparing against it would
add a baseline query for little gain. The slope per market is fitted on 2024
and frozen; the rules below are pre-registered in the 27k spec.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.core.nfl_baseline import MIN_BASELINE_GAMES
from app.core.nfl_game_context import INDOOR_ROOFS, OUTDOOR_ROOFS
from app.core.nfl_game_environment import KEEP_SLOPE_STANDARD_ERRORS, NflEnvironmentGame, clustered_wls
from app.core.nfl_projection_backtest import REPLAY_MARKETS_BY_POSITION
from app.nfl.markets import NflPropMarket

# Pre-registered 2026-09-26, before the 2024 fit and the 2025 score.
WIND_THRESHOLD_MPH = 10
WIND_SCALE_MPH = 10.0
WIND_ADJUSTMENT_MAX = 0.15
WIND_MARKETS = frozenset({
    NflPropMarket.PASSING_ATTEMPTS, NflPropMarket.PASSING_COMPLETIONS, NflPropMarket.PASSING_YARDS,
})

# Kept slopes from `python -m app.backtest.nfl_wind_fit --season 2024`, frozen
# 2026-09-26 before the 2025 score. Only passing yards cleared 2 player-clustered SE.
WIND_SLOPES: dict[NflPropMarket, float] = {
    NflPropMarket.PASSING_ATTEMPTS: 0.0,
    NflPropMarket.PASSING_COMPLETIONS: 0.0,
    NflPropMarket.PASSING_YARDS: -0.245,
}


def excess_wind(roof: str | None, wind: int | float | None) -> float | None:
    """Wind above the threshold in units of 10 mph; 0 indoors, None when unknown."""
    if roof in INDOOR_ROOFS:
        return 0.0
    if roof not in OUTDOOR_ROOFS or wind is None:
        return None
    return max(0.0, wind - WIND_THRESHOLD_MPH) / WIND_SCALE_MPH


def wind_adjustment_pct(market: NflPropMarket, excess: float | None, slopes: dict[NflPropMarket, float]) -> float | None:
    """Bounded adjustment in percentage points, or None when the market or the wind is not covered."""
    slope = slopes.get(market)
    if slope is None or excess is None:
        return None
    bounded_adjustment = max(-WIND_ADJUSTMENT_MAX, min(WIND_ADJUSTMENT_MAX, slope * excess))
    return round(bounded_adjustment * 100, 2)


def apply_wind(row: dict, markets: frozenset[NflPropMarket], slopes: dict[NflPropMarket, float] = WIND_SLOPES) -> dict:
    """The row with a wind adjustment when its market is in `markets`, read from `game_weather`.

    Anytime TD never takes one. A row without weather gets None, never a zero-wind adjustment.
    """
    market = NflPropMarket(row["market"])
    if market is NflPropMarket.ANYTIME_TOUCHDOWN or market not in markets:
        return row
    weather = row.get("game_weather") or {}
    excess = excess_wind(weather.get("roof"), weather.get("wind"))
    return {**row, "wind_adjustment_pct": wind_adjustment_pct(market, excess, slopes)}


@dataclass(frozen=True)
class NflWindSample:
    player_id: int
    y: float
    x: float
    weight: float


@dataclass(frozen=True)
class NflWindFit:
    n: int
    players: int
    windy: int
    slope: float
    se: float

    def kept(self) -> float:
        """The slope, or zero when it is not clearly different from zero."""
        return self.slope if abs(self.slope) >= KEEP_SLOPE_STANDARD_ERRORS * self.se else 0.0


def wind_samples(games: list[NflEnvironmentGame], market: NflPropMarket) -> list[NflWindSample]:
    """Each known-wind game against the player's other games that season.

    Unknown-wind games are no sample but stay in the leave-one-out mean, since a
    pre-game baseline would have averaged them too.
    """
    by_player: dict[int, list[tuple[float, NflEnvironmentGame]]] = defaultdict(list)
    for game in games:
        value = game.stats.get(market.value)
        if value is not None and market.value in REPLAY_MARKETS_BY_POSITION.get(game.position, ()):
            by_player[game.player_id].append((value, game))
    samples = []
    for player_id, played in by_player.items():
        others = len(played) - 1
        if others < MIN_BASELINE_GAMES:
            continue
        stat_sum = sum(value for value, _ in played)
        for value, game in played:
            excess = excess_wind(game.roof, game.wind)
            loo_mean = (stat_sum - value) / others
            if excess is None or loo_mean <= 0:
                continue
            samples.append(NflWindSample(player_id=player_id, y=value / loo_mean - 1, x=excess, weight=loo_mean))
    return samples


def fit_wind_slope(samples: list[NflWindSample]) -> NflWindFit | None:
    """WLS with an intercept and player-clustered SE, as the 27e environment fit."""
    fit = clustered_wls(
        [[sample.x] for sample in samples], [sample.y for sample in samples],
        [sample.weight for sample in samples], [sample.player_id for sample in samples],
    )
    if fit is None:
        return None
    [slope], [se], players = fit
    windy = sum(1 for sample in samples if sample.x > 0)
    return NflWindFit(n=len(samples), players=players, windy=windy, slope=slope, se=se)
