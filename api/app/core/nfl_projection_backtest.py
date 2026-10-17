"""Score replayed NFL prop projections against results, and decide adoption.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import sqrt
from statistics import stdev
from typing import Literal, Protocol

# The markets PrizePicks posts for each position, so a replay scores the numbers
# that actually get bet rather than a backup QB's receiving yards.
REPLAY_MARKETS_BY_POSITION: dict[str, tuple[str, ...]] = {
    "QB": ("passing_yards", "passing_attempts", "passing_completions", "rushing_yards", "fantasy_points"),
    "RB": ("rushing_yards", "rushing_attempts", "receiving_yards", "receptions", "fantasy_points"),
    "WR": ("receiving_yards", "receptions", "fantasy_points"),
    "TE": ("receiving_yards", "receptions", "fantasy_points"),
}


@dataclass(frozen=True)
class ReplayRow:
    """One player-game and market, shaped like a slate line, with what actually happened."""

    row: dict
    actual: float
    home_market_prob: float | None


@dataclass(frozen=True)
class ReplayCase:
    player_id: int
    game_id: int
    week: int
    position: str
    market: str
    projection: float
    actual: float

    @property
    def key(self) -> tuple[int, int, str]:
        return (self.player_id, self.game_id, self.market)

    @property
    def error(self) -> float:
        return self.projection - self.actual


class ScoredCase(Protocol):
    """What the metrics read, so NBA's replay cases (item 20f) are scored by the same code."""

    @property
    def key(self) -> tuple[int, int, str]: ...

    @property
    def error(self) -> float: ...


Verdict = Literal["adopt", "reject", "insufficient"]

# Pre-registered 2026-09-26, before any variant was scored. 27c-27f cite these.
MIN_PAIRED_CASES = 300
MIN_RELATIVE_MAE_IMPROVEMENT = 0.01
STANDARD_ERRORS_REQUIRED = 2.0


@dataclass(frozen=True)
class MarketMetrics:
    n: int
    mae: float
    rmse: float
    bias: float
    # None when every actual lands exactly on the projection.
    share_below: float | None


@dataclass(frozen=True)
class PairedDiff:
    n: int
    production_mae: float
    variant_mae: float
    # Mean of |variant error| - |production error|; negative means the variant is closer.
    mean_diff: float
    standard_error: float
    relative_mae_change: float


def market_metrics(cases: Iterable[ScoredCase]) -> MarketMetrics:
    errors = [case.error for case in cases]
    if not errors:
        raise ValueError("market_metrics needs at least one case")
    n = len(errors)
    # Ties are neither above nor below, so a median-like projection reads about 50%.
    untied = [e for e in errors if e != 0]
    return MarketMetrics(
        n=n,
        mae=sum(abs(e) for e in errors) / n,
        rmse=sqrt(sum(e * e for e in errors) / n),
        bias=sum(errors) / n,
        share_below=sum(e > 0 for e in untied) / len(untied) if untied else None,
    )


def paired(production: Iterable[ScoredCase], variant: Iterable[ScoredCase]) -> PairedDiff:
    by_key = {case.key: case for case in production}
    pairs = [(by_key[case.key], case) for case in variant if case.key in by_key]
    if not pairs:
        raise ValueError("paired needs at least one matched case")
    n = len(pairs)
    diffs = [abs(v.error) - abs(p.error) for p, v in pairs]
    production_mae = sum(abs(p.error) for p, _ in pairs) / n
    variant_mae = sum(abs(v.error) for _, v in pairs) / n
    return PairedDiff(
        n=n,
        production_mae=production_mae,
        variant_mae=variant_mae,
        mean_diff=sum(diffs) / n,
        standard_error=stdev(diffs) / sqrt(n) if n > 1 else 0.0,
        relative_mae_change=(variant_mae - production_mae) / production_mae if production_mae else 0.0,
    )


def adoption_verdict(diff: PairedDiff) -> Verdict:
    if diff.n < MIN_PAIRED_CASES:
        return "insufficient"
    improves_enough = diff.relative_mae_change <= -MIN_RELATIVE_MAE_IMPROVEMENT
    beyond_noise = diff.mean_diff < -STANDARD_ERRORS_REQUIRED * diff.standard_error
    return "adopt" if improves_enough and beyond_noise else "reject"
