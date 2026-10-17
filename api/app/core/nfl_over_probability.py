"""P(over line) from an empirical distribution of actual / projection.

A projection is a mean, and prop stats are right-skewed, so the chance of going
over a line near the projection is usually below 50%. Scaling a fitted ratio
distribution by the projection keeps that skew, and lets the spread grow with
the projection.

Pure: no DB, no I/O, and no NFL imports, so it can serve other sports later.
"""
from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

QUANTILE_LEVELS: tuple[float, ...] = tuple(round(i * 0.025, 3) for i in range(41))


@dataclass(frozen=True)
class OverProbability:
    p_over: float

    @property
    def p_under(self) -> float:
        return 1.0 - self.p_over


def ratio_quantiles(pairs: Iterable[tuple[float, float]]) -> tuple[float, ...]:
    """Quantiles of actual / projection at `QUANTILE_LEVELS`, from (projection, actual) pairs."""
    ratios = sorted(actual / projection for projection, actual in pairs if projection > 0)
    if not ratios:
        raise ValueError("ratio_quantiles needs at least one pair with a positive projection")
    last = len(ratios) - 1
    quantiles = []
    for level in QUANTILE_LEVELS:
        position = level * last
        lower = int(position)
        upper = min(lower + 1, last)
        quantiles.append(ratios[lower] + (position - lower) * (ratios[upper] - ratios[lower]))
    return tuple(quantiles)


def _ratio_cdf(quantiles: Sequence[float], ratio: float) -> float:
    if ratio < quantiles[0]:
        return 0.0
    if ratio >= quantiles[-1]:
        return 1.0
    # The last quantile at or below the ratio, so a repeated value (a mass of
    # zero-yard games) counts in full: over 0.5 yards never includes a zero.
    i = bisect_right(quantiles, ratio) - 1
    lower, upper = quantiles[i], quantiles[i + 1]
    fraction = (ratio - lower) / (upper - lower)
    return QUANTILE_LEVELS[i] + fraction * (QUANTILE_LEVELS[i + 1] - QUANTILE_LEVELS[i])


def over_probability(quantiles: Sequence[float], projection: float, line: float) -> OverProbability | None:
    """P(result > line), or None when it cannot be read.

    An integer line can push, which this distribution does not model, and a
    projection at or below zero has no ratio.
    """
    if projection <= 0 or float(line).is_integer():
        return None
    return OverProbability(1.0 - _ratio_cdf(quantiles, line / projection))
