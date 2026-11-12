"""Shrink the served tennis ensemble toward the market at large gaps (66a, `shrink-v1`).

Pre-registered: the rule and the forward check below are frozen by the commit that
added this module, before any data was read for item 66. Editing any constant
invalidates `tennis-shrink-check-v1`; a changed rule is a new version with a fresh
forward sample. Pure math, no I/O.
"""
from __future__ import annotations

from math import isfinite
from typing import Literal

from app.core.tennis_grading import PairedDifference

SHRINK_VERSION = "shrink-v1"
# 26a's CLV_MIN_GAP, fixed before any ensemble-v3 prediction existed.
SHRINK_THRESHOLD = 0.03
# Share of the gap the shadow keeps at or above the threshold.
SHRINK_WEIGHT = 0.5

CHECK_VERSION = "tennis-shrink-check-v1"
MIN_AFFECTED = 400
MIN_DAYS = 30
SETTLEMENT_LAG_DAYS = 3
MIN_COVERAGE = 0.98
GATE_STANDARD_ERRORS = 2.0
SLICES = ("ATP+WTA", "CHALLENGER")

# Stored probabilities are floats, so 0.36 - 0.33 lands a hair under 0.03.
# A gap that reads as 3.00 points must count as 3 points.
_EDGE_TOLERANCE = 1e-9

Verdict = Literal["accruing", "adopt", "keep served"]


def _at_least(gap: float, edge: float) -> bool:
    return abs(gap) >= edge - _EDGE_TOLERANCE


def is_affected(ensemble: float, market: float) -> bool:
    return _at_least(ensemble - market, SHRINK_THRESHOLD)


def shrink_toward_market(ensemble: float, market: float) -> float:
    """p1's shadow probability; symmetric, so p2's is 1 minus it."""
    if not is_affected(ensemble, market):
        return ensemble
    return market + SHRINK_WEIGHT * (ensemble - market)


def shadow_version(served_version: str) -> str:
    return f"{served_version}+{SHRINK_VERSION}"


def slice_for(tour: str) -> str:
    """The served blend group, so WTA 125 (stored as CHALLENGER) rides with Challenger."""
    return "ATP+WTA" if (tour or "").upper() in ("ATP", "WTA") else "CHALLENGER"


def gap_bucket(gap: float) -> str:
    if _at_least(gap, 0.05):
        return "5+"
    if _at_least(gap, SHRINK_THRESHOLD):
        return "3-5"
    if _at_least(gap, 0.01):
        return "1-3"
    return "<1"


def verdict(difference: PairedDifference, affected: int, days: int) -> Verdict:
    """Shadow minus served on affected matches: adopt only when better by more than 2 SE."""
    if affected < MIN_AFFECTED or days < MIN_DAYS:
        return "accruing"
    se = difference.standard_error
    if se is None or not isfinite(se) or not isfinite(difference.mean):
        raise ValueError("a locked sample needs a finite mean and standard error")
    return "adopt" if difference.mean + GATE_STANDARD_ERRORS * se < 0 else "keep served"
