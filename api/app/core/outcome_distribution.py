"""Whole-outcome distributions for player props: counts and yards.

A projection that is only a mean cannot say where the median sits, and prop
lines sit near the median. These distributions carry the full shape, so a
caller can read the median, the chance of going over a line (with pushes), and
score the forecast with CRPS.

Pure: no DB, no I/O, and no sport imports, so any sport can reuse it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cached_property

import numpy as np
from scipy.special import ndtr

# Opportunity counts are truncated once the remaining tail holds less than this,
# then renormalized, so a PMF always sums to 1.
TAIL_MASS = 1e-6
YARDS_GRID_LOW = -20.0
YARDS_GRID_HIGH = 600.0
YARDS_GRID_STEP = 1.0


@dataclass(frozen=True)
class LineProbability:
    over: float
    under: float
    push: float


def _negative_binomial_pmf(mean: float, dispersion: float) -> np.ndarray:
    """PMF over 0..K, where K is where the tail falls below `TAIL_MASS`.

    `dispersion` is the size r: variance = mean + mean**2 / r.
    """
    if not math.isfinite(mean) or mean < 0:
        raise ValueError(f"mean must be finite and >= 0, got {mean}")
    if not math.isfinite(dispersion) or dispersion <= 0:
        raise ValueError(f"dispersion must be finite and > 0, got {dispersion}")
    if mean == 0:
        return np.array([1.0])
    p = dispersion / (dispersion + mean)
    probs = [p ** dispersion]
    total = probs[0]
    k = 0
    while 1.0 - total >= TAIL_MASS:
        k += 1
        probs.append(probs[-1] * (k - 1 + dispersion) / k * (1.0 - p))
        total += probs[-1]
    pmf = np.array(probs)
    return pmf / pmf.sum()


def _step_crps(points: np.ndarray, cdf_values: np.ndarray, widths: np.ndarray, actual: float) -> float:
    """CRPS as the sum of (F - 1{y >= actual})**2 over cells where F is read at `points`."""
    indicator = (points >= actual).astype(float)
    return float(np.sum((cdf_values - indicator) ** 2 * widths))


def count_crps(cdf_from_zero: np.ndarray, actual: float) -> float:
    """CRPS of a count forecast given F(0), F(1), ... up to where F reaches 1.

    F and the indicator of a whole-number actual are both constant on [k, k + 1),
    so unit cells read at their left edge are exact. Any forecast scored this way
    is scored on the same cells, which keeps two arms comparable.
    """
    if actual < 0 or actual != math.floor(actual):
        raise ValueError(f"a count actual must be a whole number >= 0, got {actual}")
    upper = max(len(cdf_from_zero), int(actual) + 1)
    cdf_values = np.ones(upper)
    cdf_values[: len(cdf_from_zero)] = cdf_from_zero
    return _step_crps(np.arange(upper, dtype=float), cdf_values, np.ones(upper), actual)


def yards_grid(actual: float) -> np.ndarray:
    """Midpoints of 1-yard cells over the fixed range, widened to reach the actual."""
    low = min(YARDS_GRID_LOW, math.floor(actual) - YARDS_GRID_STEP)
    high = max(YARDS_GRID_HIGH, math.ceil(actual) + YARDS_GRID_STEP)
    return np.arange(low, high, YARDS_GRID_STEP) + YARDS_GRID_STEP / 2.0


def yards_crps(points: np.ndarray, cdf_values: np.ndarray, actual: float) -> float:
    """CRPS of a yards forecast read at `yards_grid(actual)`."""
    return _step_crps(points, cdf_values, np.full(len(points), YARDS_GRID_STEP), actual)


@dataclass(frozen=True)
class NegativeBinomial:
    """Counts (targets, receptions, carries, attempts) with variance above the mean."""

    mean: float
    dispersion: float

    def __post_init__(self) -> None:
        _ = self.pmf

    @cached_property
    def pmf(self) -> np.ndarray:
        return _negative_binomial_pmf(self.mean, self.dispersion)

    @cached_property
    def _cumulative(self) -> np.ndarray:
        return np.minimum(np.cumsum(self.pmf), 1.0)

    def cdf(self, x: float) -> float:
        if x < 0:
            return 0.0
        k = math.floor(x)
        return 1.0 if k >= len(self.pmf) else float(self._cumulative[k])

    def median(self) -> float:
        return float(np.searchsorted(self._cumulative, 0.5))

    def p_over(self, line: float) -> LineProbability:
        push = self._mass_at(line)
        under = self.cdf(line - 1) if push else self.cdf(line)
        return LineProbability(over=1.0 - self.cdf(line), under=under, push=push)

    def crps(self, actual: float) -> float:
        return count_crps(self._cumulative, actual)

    def _mass_at(self, line: float) -> float:
        if line < 0 or line != math.floor(line) or line >= len(self.pmf):
            return 0.0
        return float(self.pmf[int(line)])


@dataclass(frozen=True)
class CompoundYards:
    """Yards from N opportunities, N negative binomial and each one normal.

    yards | N ~ Normal(N * yards_mean, sqrt(N) * yards_sd), and N = 0 is a
    point mass at zero yards (no target, no carry, no yards).
    """

    opportunities: NegativeBinomial
    yards_mean: float
    yards_sd: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.yards_mean):
            raise ValueError(f"yards_mean must be finite, got {self.yards_mean}")
        if not math.isfinite(self.yards_sd) or self.yards_sd <= 0:
            raise ValueError(f"yards_sd must be finite and > 0, got {self.yards_sd}")

    def _cdf_array(self, ys: np.ndarray) -> np.ndarray:
        pmf = self.opportunities.pmf
        values = pmf[0] * (ys >= 0)
        n = np.arange(1, len(pmf))
        if len(n):
            z = (ys[:, None] - n * self.yards_mean) / (np.sqrt(n) * self.yards_sd)
            values = values + ndtr(z) @ pmf[1:]
        return np.minimum(values, 1.0)

    def cdf(self, x: float) -> float:
        return float(self._cdf_array(np.array([float(x)]))[0])

    def median(self) -> float:
        if self.cdf(0.0) >= 0.5 and self.cdf(-1e-9) < 0.5:
            return 0.0
        most = len(self.opportunities.pmf)
        high = most * abs(self.yards_mean) + 10.0 * self.yards_sd * math.sqrt(most) + 1.0
        low = -high
        for _ in range(100):
            mid = (low + high) / 2.0
            if self.cdf(mid) >= 0.5:
                high = mid
            else:
                low = mid
        return high

    def p_over(self, line: float) -> LineProbability:
        push = float(self.opportunities.pmf[0]) if line == 0 else 0.0
        over = 1.0 - self.cdf(line)
        return LineProbability(over=over, under=1.0 - over - push, push=push)

    def crps(self, actual: float) -> float:
        points = yards_grid(actual)
        return yards_crps(points, self._cdf_array(points), actual)
