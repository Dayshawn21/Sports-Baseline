"""24c efficiency arm: do pre-game EPA, success, and pace ratings beat the close?

Learning rates are chosen on the fit seasons by how well each rating predicts
the next game's value, never by the market, so the betting outcome plays no
part in tuning. The residual fit and report reuse the 24e helpers.
Run through: python -m app.backtest.nfl_game_lines --signal efficiency
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from app.backtest.nfl_game_context import (
    CaseVector, ContextArm, describe_residual_fit, fit_residuals, market_cases, residual_report,
)
from app.backtest.nfl_game_lines import FIT_SEASONS, HOLDOUT_SEASONS, LEARNING_RATE_GRID
from app.core.nfl_efficiency_ratings import (
    SPREAD_FEATURE_NAMES, TOTAL_FEATURE_NAMES, NflEfficiencyConfig, NflEfficiencyFeatures, TeamGameMetric,
    efficiency_features, replay,
)
from app.core.nfl_game_lines import NflGameLineGame, mae
from app.ingest.nflverse_team_efficiency import NflverseTeamEfficiency

Metric = Literal["epa_per_play", "success_rate", "plays"]
METRICS: tuple[Metric, ...] = ("epa_per_play", "success_rate", "plays")

TeamEfficiencyRows = Mapping[tuple[str, bool], NflverseTeamEfficiency]


def metric_maps(rows: TeamEfficiencyRows) -> dict[Metric, dict[tuple[str, bool], float]]:
    """Per-play rates from the stored sums, one map per metric."""
    return {
        "epa_per_play": {key: row.epa / row.plays for key, row in rows.items()},
        "success_rate": {key: row.successes / row.plays for key, row in rows.items()},
        "plays": {key: float(row.plays) for key, row in rows.items()},
    }


def missing_efficiency(games: list[NflGameLineGame], rows: TeamEfficiencyRows) -> list[str]:
    """Final games through the holdout that lack either offense row."""
    return [
        line_game.game.game_key for line_game in games
        if line_game.game.season <= max(HOLDOUT_SEASONS)
        and line_game.game.home_score is not None and line_game.game.away_score is not None
        and not ((line_game.game.game_key, True) in rows and (line_game.game.game_key, False) in rows)
    ]


def require_coverage(games: list[NflGameLineGame], rows: TeamEfficiencyRows) -> None:
    """Missing rows would quietly weaken the ratings, so refuse to fit on them."""
    missing = missing_efficiency(games, rows)
    if missing:
        raise ValueError(
            f"{len(missing)} final games lack team efficiency rows (run the nflverse_team_efficiency backfill): "
            + ", ".join(missing[:10])
        )


def rate_loss(games: list[NflGameLineGame], metric: TeamGameMetric, rate: float) -> float:
    """Next-game MAE on fit-season team-games: expected value against the value played."""
    predicted: list[float] = []
    actual: list[float] = []
    for row in replay([line_game.game for line_game in games], metric, NflEfficiencyConfig(rate)):
        if row.season not in FIT_SEASONS or row.league is None:
            continue
        for is_home, expected in ((True, row.expected_home), (False, row.expected_away)):
            value = metric.get((row.game_key, is_home))
            if value is not None and expected is not None:
                predicted.append(expected)
                actual.append(value)
    return mae(predicted, actual)


def fit_rates(games: list[NflGameLineGame], maps: Mapping[Metric, TeamGameMetric]) -> dict[Metric, float]:
    """Lowest fit-season loss per metric; `min` keeps the smaller rate on a tie."""
    return {metric: min(LEARNING_RATE_GRID, key=lambda rate: rate_loss(games, maps[metric], rate)) for metric in METRICS}


def build_features(
    games: list[NflGameLineGame], maps: Mapping[Metric, TeamGameMetric], rates: Mapping[Metric, float],
) -> dict[str, NflEfficiencyFeatures]:
    """Pre-game features for every game, replayed over the full history."""
    elo_games = [line_game.game for line_game in games]
    epa, success, plays = (replay(elo_games, maps[m], NflEfficiencyConfig(rates[m])) for m in METRICS)
    return {e.game_key: efficiency_features(e, s, p) for e, s, p in zip(epa, success, plays, strict=True)}


FEATURE_NAMES: dict[ContextArm, tuple[str, ...]] = {"total": TOTAL_FEATURE_NAMES, "spread": SPREAD_FEATURE_NAMES}


def efficiency_vectors(features: Mapping[str, NflEfficiencyFeatures]) -> dict[ContextArm, CaseVector]:
    return {
        "total": lambda case: features[case.game_key].total_vector(),
        "spread": lambda case: features[case.game_key].spread_vector(),
    }


@dataclass(frozen=True)
class NflEfficiencyFit:
    rates: dict[Metric, float]
    coefficients: dict[ContextArm, tuple[float, ...]]


def fit_efficiency(games: list[NflGameLineGame], rows: TeamEfficiencyRows) -> NflEfficiencyFit:
    """Rates, then per-arm residual coefficients, from fit seasons alone."""
    require_coverage(games, rows)
    maps = metric_maps(rows)
    rates = fit_rates(games, maps)
    vectors = efficiency_vectors(build_features(games, maps, rates))
    return NflEfficiencyFit(rates, fit_residuals(market_cases(games, FIT_SEASONS), vectors))


def describe_efficiency_fit(result: NflEfficiencyFit) -> str:
    rates = ", ".join(f"{metric} {rate:g}" for metric, rate in result.rates.items())
    return f"Learning rates (fit-season next-game MAE): {rates}\n" + describe_residual_fit(
        "efficiency", FEATURE_NAMES, result.coefficients,
    )


def efficiency_report(games: list[NflGameLineGame], rows: TeamEfficiencyRows, result: NflEfficiencyFit) -> str:
    """Score the holdout once with the fitted rates and coefficients, under the 24e rule."""
    features = build_features(games, metric_maps(rows), result.rates)
    holdout = market_cases(games, HOLDOUT_SEASONS)
    return "\n".join([
        describe_efficiency_fit(result),
        *residual_report("efficiency", holdout, efficiency_vectors(features), result.coefficients),
    ])
