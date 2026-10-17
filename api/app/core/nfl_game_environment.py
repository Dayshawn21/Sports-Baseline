"""Game environment for NFL prop projections (build-plan item 27e).

The spread and total give each team an implied total and an expected margin.
A projection moves only when this game's environment differs from the one the
player's baseline games were played in, so a good offense's usual high totals
are not counted twice. Each market has its own slopes, fitted on 2024 and
frozen, so passing volume can rise when trailing while rushing falls.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from app.core.nfl_baseline import MIN_BASELINE_GAMES
from app.core.nfl_projection_backtest import REPLAY_MARKETS_BY_POSITION
from app.nfl.markets import NflPropMarket

# Pre-registered 2026-09-26, before the 2024 fit and the 2025 score.
ENVIRONMENT_ADJUSTMENT_MAX = 0.15
MARGIN_SCALE_POINTS = 7.0
# A fitted slope is kept only this many standard errors from zero, otherwise it
# is zero, so noise in the 2024 fit never reaches a projection.
KEEP_SLOPE_STANDARD_ERRORS = 2.0


@dataclass(frozen=True)
class NflEnvironmentSlopes:
    """Fractional change per unit of relative team total, and per 7 points of margin."""

    total: float
    margin: float


# Kept slopes from `python -m app.backtest.nfl_game_environment_fit --season 2024`,
# frozen 2026-09-26 before the 2025 score. Only the rushing margin slopes cleared
# 2 player-clustered SE; every zero is a slope that did not.
GAME_ENVIRONMENT_SLOPES: dict[NflPropMarket, NflEnvironmentSlopes] = {
    NflPropMarket.PASSING_YARDS: NflEnvironmentSlopes(total=0.0, margin=0.0),
    NflPropMarket.PASSING_ATTEMPTS: NflEnvironmentSlopes(total=0.0, margin=0.0),
    NflPropMarket.PASSING_COMPLETIONS: NflEnvironmentSlopes(total=0.0, margin=0.0),
    NflPropMarket.RUSHING_YARDS: NflEnvironmentSlopes(total=0.0, margin=0.127),
    NflPropMarket.RUSHING_ATTEMPTS: NflEnvironmentSlopes(total=0.0, margin=0.120),
    NflPropMarket.RECEIVING_YARDS: NflEnvironmentSlopes(total=0.0, margin=0.0),
    NflPropMarket.RECEPTIONS: NflEnvironmentSlopes(total=0.0, margin=0.0),
    NflPropMarket.FANTASY_POINTS: NflEnvironmentSlopes(total=0.0, margin=0.0),
}


def team_lines(home_spread_margin: float, total: float, is_home: bool) -> tuple[float, float]:
    """(implied team total, expected margin) for one side, from the home margin and the game total."""
    margin = home_spread_margin if is_home else -home_spread_margin
    return (total + margin) / 2, margin


def apply_game_environment(
    row: dict, markets: frozenset[NflPropMarket],
    slopes: dict[NflPropMarket, NflEnvironmentSlopes] = GAME_ENVIRONMENT_SLOPES,
) -> dict:
    """The row switched from moneyline scaling to game environment when its market is in `markets`.

    Anytime TD never switches: it has its own backtest and ignores the moneyline.
    A player whose team is not in the game has no side, so no adjustment.
    """
    market = NflPropMarket(row["market"])
    if market is NflPropMarket.ANYTIME_TOUCHDOWN or market not in markets:
        return row
    lines = row.get("game_lines")
    adjustment = None
    if lines is not None and row.get("opponent_team") is not None:
        team_total, team_margin = team_lines(
            lines["home_spread_margin"], lines["total"], row["player_team_id"] == row["home_team_id"],
        )
        adjustment = environment_adjustment_pct(market, team_total, team_margin, row.get("environment"), slopes)
    return {**row, "uses_game_environment": True, "environment_adjustment_pct": adjustment}


def environment_adjustment_pct(
    market: NflPropMarket,
    team_total: float | None,
    team_margin: float | None,
    environment: dict | None,
    slopes: dict[NflPropMarket, NflEnvironmentSlopes],
) -> float | None:
    """Bounded adjustment in percentage points, or None without the inputs to compute it."""
    market_slopes = slopes.get(market)
    if market_slopes is None or team_total is None or team_margin is None or environment is None:
        return None
    if environment["team_total"] <= 0:
        return None
    x_total = team_total / environment["team_total"] - 1
    x_margin = (team_margin - environment["team_margin"]) / MARGIN_SCALE_POINTS
    raw_adjustment = market_slopes.total * x_total + market_slopes.margin * x_margin
    bounded_adjustment = max(-ENVIRONMENT_ADJUSTMENT_MAX, min(ENVIRONMENT_ADJUSTMENT_MAX, raw_adjustment))
    return round(bounded_adjustment * 100, 2)


@dataclass(frozen=True)
class NflEnvironmentGame:
    """One player-game with its lines, as the 2024 fits read it. Stats keyed by market.

    Roof and observed wind are read by the 27k wind fit only.
    """

    player_id: int
    position: str
    team_total: float
    team_margin: float
    stats: dict[str, float | None]
    roof: str | None = None
    wind: int | None = None


@dataclass(frozen=True)
class NflEnvironmentSample:
    player_id: int
    y: float
    x_total: float
    x_margin: float
    weight: float


@dataclass(frozen=True)
class NflEnvironmentFit:
    n: int
    players: int
    total: float
    total_se: float
    margin: float
    margin_se: float

    def kept(self) -> NflEnvironmentSlopes:
        """The slopes with any not clearly different from zero set to zero."""
        def keep(slope: float, se: float) -> float:
            return slope if abs(slope) >= KEEP_SLOPE_STANDARD_ERRORS * se else 0.0
        return NflEnvironmentSlopes(keep(self.total, self.total_se), keep(self.margin, self.margin_se))


def environment_samples(games: list[NflEnvironmentGame], market: NflPropMarket) -> list[NflEnvironmentSample]:
    """Each game against the player's other games that season, the same comparison production makes.

    Leave-one-out keeps the game out of its own reference, as a pre-game
    baseline would. Players need MIN_BASELINE_GAMES other games, as a rated line does.
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
        total_sum = sum(game.team_total for _, game in played)
        margin_sum = sum(game.team_margin for _, game in played)
        for value, game in played:
            loo_mean = (stat_sum - value) / others
            loo_total = (total_sum - game.team_total) / others
            if loo_mean <= 0 or loo_total <= 0:
                continue
            samples.append(NflEnvironmentSample(
                player_id=player_id,
                y=value / loo_mean - 1,
                x_total=game.team_total / loo_total - 1,
                x_margin=(game.team_margin - (margin_sum - game.team_margin) / others) / MARGIN_SCALE_POINTS,
                weight=loo_mean,
            ))
    return samples


def fit_environment_slopes(samples: list[NflEnvironmentSample]) -> NflEnvironmentFit | None:
    """Weighted least squares with an intercept, standard errors clustered by player.

    A player's leave-one-out samples share games, so they are not independent;
    per-sample errors would overstate the evidence. The intercept absorbs the
    ratio's skew and is discarded. None without enough players to estimate.
    """
    fit = clustered_wls(
        [[sample.x_total, sample.x_margin] for sample in samples],
        [sample.y for sample in samples], [sample.weight for sample in samples],
        [sample.player_id for sample in samples],
    )
    if fit is None:
        return None
    (total, margin), (total_se, margin_se), players = fit
    return NflEnvironmentFit(
        n=len(samples), players=players, total=total, total_se=total_se, margin=margin, margin_se=margin_se,
    )


def clustered_wls(
    regressors: list[list[float]], y: list[float], weights: list[float], player_ids: list[int],
) -> tuple[list[float], list[float], int] | None:
    """(slopes, standard errors, clusters) from WLS with an intercept, errors clustered by player.

    The intercept is fitted and dropped. None with fewer than 3 players or a
    singular design.
    """
    players = sorted(set(player_ids))
    if len(players) < 3:
        return None
    x = np.array([[1.0, *row] for row in regressors])
    y_arr = np.array(y)
    w = np.array(weights)
    columns = x.shape[1]
    bread = x.T @ (x * w[:, None])
    if np.linalg.matrix_rank(bread) < columns:
        return None
    bread_inv = np.linalg.inv(bread)
    beta = bread_inv @ (x.T @ (w * y_arr))
    scores = x * (w * (y_arr - x @ beta))[:, None]
    index = {player: i for i, player in enumerate(players)}
    by_player = np.zeros((len(players), columns))
    np.add.at(by_player, [index[player_id] for player_id in player_ids], scores)
    clusters = len(players)
    covariance = bread_inv @ (by_player.T @ by_player) @ bread_inv * clusters / (clusters - 1)
    slopes = [float(value) for value in beta[1:]]
    errors = [float(np.sqrt(covariance[i, i])) for i in range(1, columns)]
    return slopes, errors, clusters
