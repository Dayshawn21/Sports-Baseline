"""The market-anchored tennis blend (26d): a log-odds combination of market and ELO.

Pure math. The coefficients are fitted on the 2022 development season by
app.backtest.tennis_market_blend_fit and frozen in tennis_market_blend_fit.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, log

_INPUT_FLOOR = 1e-6
_OUTPUT_MIN = 0.01
_OUTPUT_MAX = 0.99


@dataclass(frozen=True)
class BlendCoefficients:
    market: float
    elo: float


def logit(probability: float) -> float:
    p = min(max(probability, _INPUT_FLOOR), 1 - _INPUT_FLOOR)
    return log(p / (1 - p))


def market_anchored_prob(coefs: BlendCoefficients, market_prob: float, elo_prob: float | None) -> float:
    """p1's win probability. No intercept, so swapping the players gives 1 - p."""
    if elo_prob is None:
        return market_prob
    z = coefs.market * logit(market_prob) + coefs.elo * logit(elo_prob)
    p = 1 / (1 + exp(-z)) if z >= 0 else exp(z) / (1 + exp(z))
    return min(max(p, _OUTPUT_MIN), _OUTPUT_MAX)
