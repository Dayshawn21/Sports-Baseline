"""Score P(over) against results, and decide which markets may show it.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import erf, floor, sqrt
from typing import Literal

# Roughly where PrizePicks posts demon, standard and goblin lines around a
# player's median, so calibration is judged across the lines that get priced,
# not only at the projection.
SYNTHETIC_LINE_MULTIPLES = (0.5, 0.75, 1.0, 1.25, 1.5)
BIN_COUNT = 10

# Pre-registered 2026-09-26, before any fit was scored (build-plan item 27g).
MIN_CASES = 300
MAX_ECE = 0.02
MAX_BIN_GAP = 0.05
MIN_BIN_PAIRS = 200

DisplayVerdict = Literal["show", "hide", "insufficient"]


@dataclass(frozen=True)
class CalibrationPair:
    predicted: float
    over: bool


@dataclass(frozen=True)
class CalibrationBin:
    n: int
    mean_predicted: float
    observed: float

    @property
    def gap(self) -> float:
        return abs(self.mean_predicted - self.observed)


@dataclass(frozen=True)
class CalibrationReport:
    n: int
    brier: float
    # Pair-weighted mean |predicted - observed| over the non-empty bins.
    ece: float
    bins: tuple[CalibrationBin, ...]
    # None when no bin holds MIN_BIN_PAIRS pairs.
    worst_gap: float | None


def synthetic_lines(projection: float) -> tuple[float, ...]:
    """x.5 lines around a projection, positive and distinct, in multiple order."""
    lines: list[float] = []
    for multiple in SYNTHETIC_LINE_MULTIPLES:
        line = floor(projection * multiple) + 0.5
        if line > 0 and line not in lines:
            lines.append(line)
    return tuple(lines)


def calibrate(pairs: Iterable[CalibrationPair], bin_count: int = BIN_COUNT) -> CalibrationReport:
    pairs = list(pairs)
    if not pairs:
        raise ValueError("calibrate needs at least one pair")
    n = len(pairs)
    buckets: list[list[CalibrationPair]] = [[] for _ in range(bin_count)]
    for pair in pairs:
        buckets[min(int(pair.predicted * bin_count), bin_count - 1)].append(pair)
    bins = tuple(
        CalibrationBin(
            n=len(bucket),
            mean_predicted=sum(p.predicted for p in bucket) / len(bucket),
            observed=sum(p.over for p in bucket) / len(bucket),
        )
        for bucket in buckets if bucket
    )
    large = [b.gap for b in bins if b.n >= MIN_BIN_PAIRS]
    return CalibrationReport(
        n=n,
        brier=sum((p.predicted - p.over) ** 2 for p in pairs) / n,
        ece=sum(b.n * b.gap for b in bins) / n,
        bins=bins,
        worst_gap=max(large) if large else None,
    )


def normal_over_probability(projection: float, sigma: float, line: float) -> float:
    """The baseline: a normal centered on the projection, as a mean-only model implies."""
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    z = (line - projection) / sigma
    return 1.0 - 0.5 * (1.0 + erf(z / sqrt(2.0)))


def display_verdict(cases_n: int, report: CalibrationReport, normal_brier: float) -> DisplayVerdict:
    if cases_n < MIN_CASES:
        return "insufficient"
    calibrated = report.ece <= MAX_ECE and (report.worst_gap is None or report.worst_gap <= MAX_BIN_GAP)
    return "show" if calibrated and report.brier <= normal_brier else "hide"
