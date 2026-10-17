"""Residual arms: does a signal move totals and spreads away from the close?

Fits the closing line's residual (actual minus line) on a signal's features over
the fit seasons only, then scores the holdout once. There is no intercept, so
a general over or under lean in the fit seasons cannot pass for signal.
24e's context arm lives here; 24c's efficiency arm reuses the same helpers.
Run through: python -m app.backtest.nfl_game_lines --signal context
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from sklearn.linear_model import LinearRegression

from app.backtest.nfl_game_lines import (
    ADOPTION_HIT_RATE, ADOPTION_MIN_PICKS, BUCKETS, FIT_SEASONS, HOLDOUT_SEASONS, LEARNING_RATE_GRID,
    NflGameLineCase, build_cases,
)
from app.core.nfl_elo import NFL_ELO_V1
from app.core.nfl_game_context import SPREAD_FEATURE_NAMES, TOTAL_FEATURE_NAMES
from app.core.nfl_game_lines import NflGameLineGame, PickRecord, mae, pick_record
from app.core.nfl_scoring_ratings import NflScoringConfig

# Pre-registered in the 24e spec before any holdout number existed.
CONTEXT_THRESHOLDS = (0.5, 1.0, 2.0)
CONTEXT_ADOPTION_THRESHOLD = 0.5

ContextArm = Literal["total", "spread"]
CONTEXT_ARMS: tuple[ContextArm, ...] = ("total", "spread")
FEATURE_NAMES: dict[ContextArm, tuple[str, ...]] = {"total": TOTAL_FEATURE_NAMES, "spread": SPREAD_FEATURE_NAMES}

# One feature vector per case for one arm. Features that do not live on the
# case (24c efficiency) are looked up by `case.game_key` inside the function.
CaseVector = Callable[[NflGameLineCase], list[float]]
ResidualRow = tuple[list[float], float, float]


def residual_rows(cases: list[NflGameLineCase], arm: ContextArm, vector: CaseVector) -> list[ResidualRow]:
    """(features, closing line, actual) for every case with that arm's line."""
    rows: list[ResidualRow] = []
    for case in cases:
        if arm == "total" and case.total_line is not None:
            rows.append((vector(case), case.total_line, float(case.total_points)))
        elif arm == "spread" and case.spread_line is not None:
            rows.append((vector(case), case.spread_line, float(case.home_margin)))
    return rows


CONTEXT_VECTORS: dict[ContextArm, CaseVector] = {
    "total": lambda case: case.total_features.vector(),
    "spread": lambda case: case.spread_features.vector(),
}


def context_rows(cases: list[NflGameLineCase], arm: ContextArm) -> list[ResidualRow]:
    return residual_rows(cases, arm, CONTEXT_VECTORS[arm])


def adjustment(coefficients: tuple[float, ...], features: list[float]) -> float:
    return sum(c * f for c, f in zip(coefficients, features, strict=True))


def market_cases(games: list[NflGameLineGame], seasons: frozenset[int]) -> list[NflGameLineCase]:
    # Residual arms never read the 24b ratings; any valid configuration builds the cases.
    return build_cases(games, NFL_ELO_V1, NflScoringConfig(LEARNING_RATE_GRID[0]), seasons)


def fit_residuals(
    cases: list[NflGameLineCase], vectors: Mapping[ContextArm, CaseVector],
) -> dict[ContextArm, tuple[float, ...]]:
    """Per-arm coefficients from the given (fit-season) cases alone."""
    coefficients: dict[ContextArm, tuple[float, ...]] = {}
    for arm in CONTEXT_ARMS:
        rows = residual_rows(cases, arm, vectors[arm])
        model = LinearRegression(fit_intercept=False).fit(
            [features for features, _, _ in rows], [actual - line for _, line, actual in rows],
        )
        coefficients[arm] = tuple(float(value) for value in model.coef_)
    return coefficients


def fit_context(games: list[NflGameLineGame]) -> dict[ContextArm, tuple[float, ...]]:
    return fit_residuals(market_cases(games, FIT_SEASONS), CONTEXT_VECTORS)


@dataclass(frozen=True)
class NflContextScore:
    label: str
    games: int
    market_mae: float
    adjusted_mae: float
    picks: dict[float, PickRecord]


def score_context(
    label: str, cases: list[NflGameLineCase], arm: ContextArm, coefficients: tuple[float, ...],
) -> NflContextScore:
    return score_residuals(label, context_rows(cases, arm), coefficients)


def score_residuals(label: str, rows: list[ResidualRow], coefficients: tuple[float, ...]) -> NflContextScore:
    lines = [line for _, line, _ in rows]
    actuals = [actual for _, _, actual in rows]
    adjusted = [line + adjustment(coefficients, features) for features, line, _ in rows]
    return NflContextScore(
        label, len(rows), mae(lines, actuals), mae(adjusted, actuals),
        {threshold: pick_record(adjusted, lines, actuals, threshold) for threshold in CONTEXT_THRESHOLDS},
    )


def context_adopted(score: NflContextScore) -> bool:
    """The pre-registered 24e rule; strict MAE improvement, then enough winning picks."""
    picks = score.picks[CONTEXT_ADOPTION_THRESHOLD]
    return (
        score.adjusted_mae < score.market_mae
        and picks.picks >= ADOPTION_MIN_PICKS
        and picks.hit_rate is not None and picks.hit_rate >= ADOPTION_HIT_RATE
    )


def describe_residual_fit(
    signal: str, names: Mapping[ContextArm, tuple[str, ...]], coefficients: dict[ContextArm, tuple[float, ...]],
) -> str:
    lines = [f"{signal.capitalize()} fit {min(FIT_SEASONS)}-{max(FIT_SEASONS)} (points added to the closing line per unit):"]
    for arm in CONTEXT_ARMS:
        terms = ", ".join(f"{name} {value:+.3f}" for name, value in zip(names[arm], coefficients[arm]))
        lines.append(f"  {arm}: {terms}")
    return "\n".join(lines)


def describe_context_fit(coefficients: dict[ContextArm, tuple[float, ...]]) -> str:
    return describe_residual_fit("context", FEATURE_NAMES, coefficients)


def _picks(record: PickRecord) -> str:
    rate = f"{record.hit_rate:.3f}" if record.hit_rate is not None else "  -  "
    return f"{rate} ({record.hits}-{record.misses}-{record.pushes})"


def _row(score: NflContextScore) -> str:
    picks = "  ".join(f"@{t:g} {_picks(score.picks[t])}" for t in CONTEXT_THRESHOLDS)
    return f"{score.label:<12}{score.games:>6}  {score.market_mae:>8.4f} {score.adjusted_mae:>9.4f}  {picks}"


def residual_report(
    signal: str, holdout: list[NflGameLineCase], vectors: Mapping[ContextArm, CaseVector],
    coefficients: dict[ContextArm, tuple[float, ...]],
) -> list[str]:
    """Per-arm holdout tables and verdicts, scored once with the fitted coefficients."""
    label = f"{min(HOLDOUT_SEASONS)}-{max(HOLDOUT_SEASONS)}"
    lines: list[str] = []
    for arm in CONTEXT_ARMS:
        overall = score_residuals(label, residual_rows(holdout, arm, vectors[arm]), coefficients[arm])
        buckets = [
            score_residuals(
                f"  wk {bucket}",
                residual_rows([case for case in holdout if case.week_bucket == bucket], arm, vectors[arm]),
                coefficients[arm],
            )
            for bucket in BUCKETS
        ]
        lines += [
            "", f"{arm.upper()} {signal.upper()} (MAE: closing line, adjusted line; picks by adjustment size)",
            f"{'set':<12}{'games':>6}  {'close':>8} {'adjusted':>9}  hit rate (W-L-P)",
            _row(overall), *(_row(bucket) for bucket in buckets),
            f"Verdict: {'ADOPTED (provisional)' if context_adopted(overall) else 'rejected'}",
        ]
    return lines


def context_report(games: list[NflGameLineGame], coefficients: dict[ContextArm, tuple[float, ...]]) -> str:
    holdout = market_cases(games, HOLDOUT_SEASONS)
    return "\n".join([describe_context_fit(coefficients), *residual_report("context", holdout, CONTEXT_VECTORS, coefficients)])
