"""Anchor `nfl-volume-v1` receptions to the PrizePicks standard line (49b).

The blend is a log-odds shrink of the projection's chance of going over the
line, so a projection that leans OVER against a line posted near the median is
pulled back toward 50/50. The rule that will judge it is fixed here, before any
2026 outcome is joined to a projection; changing a constant starts a new version.

Pure: no DB, no I/O, no model loading.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from app.core.nfl_volume_projection import NFL_VOLUME_MODEL_VERSION
from app.core.prop_ranking_rule import (
    MIN_PICK_MARGIN,
    MIN_PICKS,
    MIN_PERIODS,
    STANDARD_ERRORS_REQUIRED,
)

NFL_VOLUME_ANCHOR_VERSION = "nfl-volume-anchor-v1"
ANCHOR_MARKET = "receptions"
ANCHOR_FIT_SEASON = 2026
ANCHOR_FIT_FIRST_WEEK = 1
ANCHOR_FIT_LAST_WEEK = 8
ANCHOR_MIN_FIT_PAIRS = 400
ANCHOR_Q_CLAMP = 0.001

# 27i's pick rule applies unchanged (margin, picks, periods, standard errors),
# imported rather than copied so there is one definition of it.
ANCHOR_PICK_RULE = {
    "min_pick_margin": MIN_PICK_MARGIN,
    "min_picks": MIN_PICKS,
    "min_periods": MIN_PERIODS,
    "standard_errors": STANDARD_ERRORS_REQUIRED,
}
LOG_LOSS_STANDARD_ERRORS = 2.0
LOG_LOSS_MIN_WEEKS_WON = 3
LOG_LOSS_REFERENCES = ("raw_volume", "constant_half")


class AnchorRefused(ValueError):
    pass


def require_anchorable(market: str, model_version: str) -> None:
    """Only adopted receptions from `nfl-volume-v1` may be anchored; the other markets were rejected."""
    if market != ANCHOR_MARKET:
        raise AnchorRefused(f"{market} is not anchored: only {ANCHOR_MARKET} was adopted by {NFL_VOLUME_MODEL_VERSION}")
    if model_version != NFL_VOLUME_MODEL_VERSION:
        raise AnchorRefused(f"{model_version} is not {NFL_VOLUME_MODEL_VERSION}")


def conditional_over(over: float, under: float) -> float:
    """P(over) given no push; the push mass is put back by `anchored_probability`."""
    total = over + under
    if total <= 0:
        raise ValueError("over and under cannot both be zero")
    return over / total


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def clamp_q(q: float) -> float:
    return min(max(q, ANCHOR_Q_CLAMP), 1.0 - ANCHOR_Q_CLAMP)


def anchored_probability(q_vol: float, p_push: float, a: float, b: float) -> tuple[float, float]:
    """The anchored (over, under) for a line; with the push mass they sum to 1."""
    if not 0.0 <= q_vol <= 1.0:
        raise ValueError(f"q_vol must be a probability, got {q_vol}")
    if not 0.0 <= p_push < 1.0:
        raise ValueError(f"p_push must be in [0, 1), got {p_push}")
    q = 1.0 / (1.0 + math.exp(-(a + b * _logit(clamp_q(q_vol)))))
    return q * (1.0 - p_push), (1.0 - q) * (1.0 - p_push)


@dataclass(frozen=True)
class AnchorFit:
    a: float
    b: float
    a_se: float
    b_se: float
    pairs: int


_MAX_ITERATIONS = 50
_TOLERANCE = 1e-10
# A coefficient this large means the sample separates, not that the data is sharp.
_DIVERGENCE_LIMIT = 30.0


def fit_anchor(pairs: Sequence[tuple[float, bool]]) -> AnchorFit:
    """Maximum-likelihood `a`, `b` from (q_vol, went over) pairs; the caller drops pushes and unsettled lines."""
    if len(pairs) < ANCHOR_MIN_FIT_PAIRS:
        raise ValueError(f"need at least {ANCHOR_MIN_FIT_PAIRS} pairs to fit the anchor, got {len(pairs)}")
    x = np.array([_logit(clamp_q(q)) for q, _ in pairs])
    y = np.array([1.0 if over else 0.0 for _, over in pairs])
    if y.min() == y.max():
        raise ValueError("every outcome is the same, so the anchor cannot be fitted")
    design = np.column_stack([np.ones_like(x), x])
    beta = np.zeros(2)
    for _ in range(_MAX_ITERATIONS):
        p = 1.0 / (1.0 + np.exp(-design @ beta))
        weights = p * (1.0 - p)
        information = design.T @ (design * weights[:, None])
        if np.linalg.cond(information) > 1e12:
            raise ValueError("the anchor fit is singular: q_vol does not vary or the sample separates")
        step = np.linalg.solve(information, design.T @ (y - p))
        beta = beta + step
        if np.abs(beta).max() > _DIVERGENCE_LIMIT:
            raise ValueError("the anchor fit diverged: the sample separates")
        if np.abs(step).max() < _TOLERANCE:
            break
    else:
        raise ValueError("the anchor fit did not converge")
    standard_errors = np.sqrt(np.diag(np.linalg.inv(information)))
    return AnchorFit(float(beta[0]), float(beta[1]), float(standard_errors[0]), float(standard_errors[1]), len(pairs))


@dataclass(frozen=True)
class AnchorParameters:
    a: float
    b: float


# Fitted once on 2026 weeks 1-8 (698 pairs, run 2026-11-03). The CLI printed four
# decimals and the run is not repeated, so these are the printed values.
NFL_VOLUME_ANCHOR_PARAMETERS = AnchorParameters(a=-0.0136, b=0.4341)
