"""Cross-fitted scoring of the v2 candidate families on one season (item 44a).

Each half of the season (by ISO-week parity) is scored by a fit on the other
half, so no case is ever scored by a fit that includes it. Scoring follows
20g1: synthetic x.5 lines, the constant-sigma normal as the Brier baseline
(its sigma from the same fitting half), and 20g1's display verdict.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import floor
from statistics import stdev

from app.core.count_over_probability import (
    NegBinParams,
    OverUnderPush,
    ScaledNormalParams,
    fit_negbin,
    fit_scaled_normal,
    negbin_over_under_push,
    scaled_normal_over_under_push,
)
from app.core.nba_over_probability import ScoredLine, nba_display_verdict
from app.core.nba_over_probability_v2 import TARGET_MARKETS, CandidateResult, Family, split_by_parity
from app.core.nba_projection_backtest import NbaReplayCase
from app.core.nfl_over_probability_calibration import (
    SYNTHETIC_LINE_MULTIPLES,
    CalibrationPair,
    calibrate,
    normal_over_probability,
    synthetic_lines,
)

FamilyParams = NegBinParams | ScaledNormalParams


@dataclass(frozen=True)
class PushContext:
    """Whole-number lines, information only: the display verdict reads x.5 lines alone."""
    pairs: int
    predicted: float
    observed: float


def fit_family(family: Family, cases: Iterable[NbaReplayCase]) -> FamilyParams:
    pairs = [(case.projection, case.actual) for case in cases]
    return fit_negbin(pairs) if family == "negbin" else fit_scaled_normal(pairs)


def read_family(params: FamilyParams, projection: float, line: float) -> OverUnderPush | None:
    if isinstance(params, NegBinParams):
        return negbin_over_under_push(params, projection, line)
    return scaled_normal_over_under_push(params, projection, line)


def _by_market(cases: Iterable[NbaReplayCase]) -> dict[str, list[NbaReplayCase]]:
    grouped: dict[str, list[NbaReplayCase]] = defaultdict(list)
    for case in cases:
        if case.projection > 0:
            grouped[case.market].append(case)
    return grouped


def score_half(family: Family, fit_cases: Iterable[NbaReplayCase], score_cases: Iterable[NbaReplayCase]) -> list[ScoredLine]:
    """Fit per market on `fit_cases`, score `score_cases`; a market with under two fit cases is skipped."""
    fitted = {market: members for market, members in _by_market(fit_cases).items() if len(members) >= 2}
    scored = []
    for market, members in _by_market(score_cases).items():
        if market not in fitted:
            continue
        params = fit_family(family, fitted[market])
        sigma = stdev(case.actual - case.projection for case in fitted[market])
        for case in members:
            for line in synthetic_lines(case.projection):
                probability = read_family(params, case.projection, line)
                if probability is None:
                    continue
                scored.append(ScoredLine(
                    case=case, line=line, p_over=probability.p_over,
                    normal_p_over=normal_over_probability(case.projection, sigma, line),
                    over=case.actual > line,
                ))
    return scored


def cross_fit(family: Family, cases: Iterable[NbaReplayCase]) -> list[ScoredLine]:
    targets = [case for case in cases if case.market in TARGET_MARKETS]
    even, odd = split_by_parity(targets)
    return score_half(family, even, odd) + score_half(family, odd, even)


def integer_lines(projection: float) -> tuple[int, ...]:
    """Whole-number lines at the synthetic multiples, 1 or more and distinct."""
    lines: list[int] = []
    for multiple in SYNTHETIC_LINE_MULTIPLES:
        line = floor(projection * multiple)
        if line >= 1 and line not in lines:
            lines.append(line)
    return tuple(lines)


def push_context(family: Family, cases: Iterable[NbaReplayCase]) -> dict[str, PushContext]:
    """Per market, cross-fitted mean P(push) against the observed push rate at whole-number lines."""
    even, odd = split_by_parity(case for case in cases if case.market in TARGET_MARKETS)
    totals: dict[str, list[float]] = defaultdict(lambda: [0, 0.0, 0])
    for fit_cases, score_cases in ((even, odd), (odd, even)):
        fitted = {market: members for market, members in _by_market(fit_cases).items() if len(members) >= 2}
        for market, members in _by_market(score_cases).items():
            if market not in fitted:
                continue
            params = fit_family(family, fitted[market])
            for case in members:
                for line in integer_lines(case.projection):
                    probability = read_family(params, case.projection, line)
                    if probability is None:
                        continue
                    total = totals[market]
                    total[0] += 1
                    total[1] += probability.p_push
                    total[2] += case.actual == line
    return {
        market: PushContext(pairs=int(n), predicted=predicted / n, observed=observed / n)
        for market, (n, predicted, observed) in totals.items()
    }


def evaluate(family: Family, lines: Sequence[ScoredLine]) -> CandidateResult:
    """One market's pooled cross-fit lines under 20g1's display verdict."""
    report = calibrate(CalibrationPair(line.p_over, line.over) for line in lines)
    normal_brier = sum((line.normal_p_over - line.over) ** 2 for line in lines) / len(lines)
    cases = len({line.case.key for line in lines})
    return CandidateResult(
        family=family, cases=cases, brier=report.brier,
        verdict=nba_display_verdict(cases, report, normal_brier),
    )
