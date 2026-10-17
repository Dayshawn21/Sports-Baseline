"""P(over) for NBA props from the reference projection (item 20g1).

A per-market distribution of actual / projection, fitted on the development
season and scored on the holdout, read with 27g's sport-agnostic
`over_probability`. Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from statistics import stdev
from typing import Literal

from app.core.nba_projection_backtest import NbaReplayCase
from app.core.nfl_over_probability import over_probability, ratio_quantiles
from app.core.nfl_over_probability_calibration import CalibrationReport, normal_over_probability, synthetic_lines

NBA_OVER_PROBABILITY_VERSION = "nba-pover-v1"

# Pre-registered 2026-10-06 with the 20g1 spec, before any fit was scored. 27g's
# values, kept as NBA's own so a change to NFL's rule cannot move this one.
MIN_CASES = 300
MAX_ECE = 0.02
MAX_BIN_GAP = 0.05
MIN_BIN_PAIRS = 200

NbaDisplayVerdict = Literal["show", "hide", "insufficient"]


@dataclass(frozen=True)
class MarketFit:
    quantiles: tuple[float, ...]
    # Spread of actual - projection, for the normal baseline the fit must beat.
    sigma: float


@dataclass(frozen=True)
class ScoredLine:
    case: NbaReplayCase
    line: float
    p_over: float
    normal_p_over: float
    over: bool


def fit_markets(cases: Iterable[NbaReplayCase]) -> dict[str, MarketFit]:
    """Per market, from cases with a positive projection; a ratio needs one, and so does a spread."""
    by_market: dict[str, list[NbaReplayCase]] = defaultdict(list)
    for case in cases:
        if case.projection > 0:
            by_market[case.market].append(case)
    return {
        market: MarketFit(
            quantiles=ratio_quantiles((case.projection, case.actual) for case in members),
            sigma=stdev(case.actual - case.projection for case in members),
        )
        for market, members in by_market.items()
        if len(members) >= 2
    }


def score_cases(fits: Mapping[str, MarketFit], cases: Iterable[NbaReplayCase]) -> list[ScoredLine]:
    """Each case at each synthetic x.5 line around its projection; cases without a fit are skipped."""
    scored = []
    for case in cases:
        fit = fits.get(case.market)
        if fit is None:
            continue
        for line in synthetic_lines(case.projection):
            probability = over_probability(fit.quantiles, case.projection, line)
            if probability is None:
                continue
            scored.append(ScoredLine(
                case=case, line=line, p_over=probability.p_over,
                normal_p_over=normal_over_probability(case.projection, fit.sigma, line),
                over=case.actual > line,
            ))
    return scored


def nba_display_verdict(cases_n: int, report: CalibrationReport, normal_brier: float) -> NbaDisplayVerdict:
    if cases_n < MIN_CASES:
        return "insufficient"
    # Recomputed from the bins so NBA's minimum bin size governs, not the one `calibrate` was built with.
    large_gaps = [b.gap for b in report.bins if b.n >= MIN_BIN_PAIRS]
    calibrated = report.ece <= MAX_ECE and all(gap <= MAX_BIN_GAP for gap in large_gaps)
    return "show" if calibrated and report.brier <= normal_brier else "hide"
