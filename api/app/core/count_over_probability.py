"""P(over), P(under) and P(push) for integer-valued stats from a projection (item 44a).

Two families, each with per-market parameters fitted from (projection, actual)
pairs:

- `negbin`: a negative binomial with mean = projection. Discrete, so a
  whole-number line gets an exact push mass, and small counts (blocks, threes)
  keep their lumpy shape. An infinite `r` is the Poisson limit.
- `scaled_normal`: a normal with variance `a + b * projection`, read with a
  continuity correction. Its spread grows with the projection, unlike the
  constant-sigma normal the display rule uses as its baseline; a candidate
  equal to that baseline would tie its Brier gate by construction.

Pure: no DB, no I/O, and no sport imports, so any sport can fit its own.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import erf, exp, floor, inf, isinf, log, sqrt

# Floors keep a degenerate fit readable: r near zero piles all mass on 0, and a
# variance at or below zero has no normal.
MIN_R = 0.1
MIN_VARIANCE = 0.25


@dataclass(frozen=True)
class OverUnderPush:
    p_over: float
    p_under: float
    p_push: float


@dataclass(frozen=True)
class NegBinParams:
    # inf means Poisson: no variance beyond the mean.
    r: float


@dataclass(frozen=True)
class ScaledNormalParams:
    a: float
    b: float


def _negbin_cdf(r: float, mean: float, k: int) -> float:
    """P(X <= k), summed by the pmf recurrence so large counts never overflow."""
    if k < 0:
        return 0.0
    if isinf(r):
        pmf, step = exp(-mean), lambda i: mean / (i + 1)
    else:
        p = r / (r + mean)
        pmf, step = exp(r * log(p)), lambda i: (i + r) / (i + 1) * (1.0 - p)
    total = pmf
    for i in range(k):
        pmf *= step(i)
        total += pmf
    return min(total, 1.0)


def _from_cdf(cdf_below: float, cdf_at_or_below: float) -> OverUnderPush:
    return OverUnderPush(
        p_over=1.0 - cdf_at_or_below,
        p_under=cdf_below,
        p_push=cdf_at_or_below - cdf_below,
    )


def negbin_over_under_push(params: NegBinParams, projection: float, line: float) -> OverUnderPush | None:
    if projection <= 0:
        return None
    k = floor(line)
    if float(line).is_integer():
        return _from_cdf(_negbin_cdf(params.r, projection, k - 1), _negbin_cdf(params.r, projection, k))
    at_or_below = _negbin_cdf(params.r, projection, k)
    return _from_cdf(at_or_below, at_or_below)


def _normal_cdf(x: float, mean: float, sigma: float) -> float:
    return 0.5 * (1.0 + erf((x - mean) / (sigma * sqrt(2.0))))


def scaled_normal_over_under_push(params: ScaledNormalParams, projection: float, line: float) -> OverUnderPush | None:
    if projection <= 0:
        return None
    sigma = sqrt(max(params.a + params.b * projection, MIN_VARIANCE))
    # Outcomes are integers, so P(X <= k) reads the normal at k + 0.5.
    k = floor(line)
    at_or_below = _normal_cdf(k + 0.5, projection, sigma)
    below = _normal_cdf(k - 0.5, projection, sigma) if float(line).is_integer() else at_or_below
    return _from_cdf(below, at_or_below)


def _positive(pairs: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    kept = [(projection, actual) for projection, actual in pairs if projection > 0]
    if len(kept) < 2:
        raise ValueError("fitting needs at least two pairs with a positive projection")
    return kept


def fit_negbin(pairs: Iterable[tuple[float, float]]) -> NegBinParams:
    """Method of moments: E[(y - mu)^2 - mu] = mu^2 / r, pooled as a ratio of sums."""
    kept = _positive(pairs)
    excess = sum((actual - mu) ** 2 - mu for mu, actual in kept)
    if excess <= 0:
        return NegBinParams(r=inf)
    return NegBinParams(r=max(sum(mu * mu for mu, _ in kept) / excess, MIN_R))


def fit_scaled_normal(pairs: Iterable[tuple[float, float]]) -> ScaledNormalParams:
    """Least squares of the squared residual on the projection."""
    kept = _positive(pairs)
    n = len(kept)
    mean_mu = sum(mu for mu, _ in kept) / n
    squares = [(actual - mu) ** 2 for mu, actual in kept]
    mean_sq = sum(squares) / n
    spread = sum((mu - mean_mu) ** 2 for mu, _ in kept)
    if spread == 0:
        return ScaledNormalParams(a=mean_sq, b=0.0)
    b = sum((mu - mean_mu) * (sq - mean_sq) for (mu, _), sq in zip(kept, squares)) / spread
    return ScaledNormalParams(a=mean_sq - b * mean_mu, b=b)
