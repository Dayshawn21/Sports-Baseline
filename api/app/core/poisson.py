"""Poisson distribution utilities for prop projections."""

import math


def poisson_cdf(k: int, lam: float) -> float:
    """P(X <= k) for Poisson(lam)."""
    if lam <= 0:
        return 1.0 if k >= 0 else 0.0
    total = 0.0
    exp_neg = math.exp(-lam)
    for i in range(k + 1):
        total += exp_neg * (lam ** i) / math.factorial(i)
    return min(1.0, max(0.0, total))


def over_under_probs(line: float, expected: float) -> tuple[float, float]:
    """
    Given a prop line and expected value (lambda), return (p_over, p_under).

    Half-point lines: floor(line) acts as the under threshold.
    """
    under_k = int(math.floor(line))
    p_under = poisson_cdf(under_k, expected)
    p_over = 1.0 - p_under
    return p_over, p_under


def over_under_push_probs(line: float, expected: float) -> tuple[float, float, float]:
    """
    Given a prop line and expected value, return (p_over, p_under, p_push).

    Half-point lines have no push. Whole-number count lines split the exact
    line probability into p_push so confidence is not inflated by treating
    pushes as unders.
    """
    if not float(line).is_integer():
        p_over, p_under = over_under_probs(line, expected)
        return p_over, p_under, 0.0

    k = int(line)
    p_under = poisson_cdf(k - 1, expected)
    p_at_line = max(0.0, poisson_cdf(k, expected) - p_under)
    p_over = max(0.0, 1.0 - p_under - p_at_line)
    return p_over, p_under, p_at_line


def confidence_tier(p: float) -> str:
    """Label a probability as a confidence tier."""
    if p >= 0.70:
        return "LOCK"
    if p >= 0.62:
        return "STRONG"
    if p >= 0.55:
        return "LEAN"
    return "PASS"
