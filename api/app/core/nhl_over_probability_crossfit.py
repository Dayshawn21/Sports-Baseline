"""Fit, cross-fit and score the candidate P(over) families for NHL markets (item 56c2).

Each family turns a (projection, actual) history into a probability that the result
lands over a line. Development scoring is cross-fitted by ISO-week parity and judged
at 20g1's synthetic x.5 lines; the rule that picks among families is pre-registered in
`app/core/nhl_over_probability.py`. Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import inf
from statistics import stdev

from app.core.count_over_probability import (
    NegBinParams,
    ScaledNormalParams,
    fit_negbin,
    fit_scaled_normal,
    negbin_over_under_push,
    scaled_normal_over_under_push,
)
from app.core.nfl_over_probability import over_probability, ratio_quantiles
from app.core.nfl_over_probability_calibration import (
    CalibrationPair,
    calibrate,
    normal_over_probability,
    synthetic_lines,
)
from app.core.nhl_over_probability import (
    CANDIDATE_ORDER,
    CandidateResult,
    Family,
    family_applies,
    nhl_display_verdict,
    parity,
    select_family,
)
from app.core.nhl_projection_backtest import NhlReplayCase
from app.nhl.markets import NhlLineOnlyMarket

# Fitting needs a spread, so one usable case is not enough for any family.
MIN_FIT_CASES = 2


@dataclass(frozen=True)
class RatioParams:
    """Quantiles of actual / projection, read at `line / projection`."""

    quantiles: tuple[float, ...]


FamilyParams = NegBinParams | ScaledNormalParams | RatioParams


def fit_family(family: Family, market: NhlLineOnlyMarket, cases: Iterable[NhlReplayCase]) -> FamilyParams | None:
    """One market's parameters, or None when the family cannot represent the market or the history is too short.

    A case with a projection at or below zero has no ratio and no mean to scale a variance by, so
    every family skips it.
    """
    if not family_applies(family, market):
        return None
    pairs = [(case.projection, case.actual) for case in cases if case.projection > 0]
    if len(pairs) < MIN_FIT_CASES:
        return None
    if family == "negbin":
        return fit_negbin(pairs)
    if family == "scaled_normal":
        return fit_scaled_normal(pairs)
    return RatioParams(ratio_quantiles(pairs))


def read_family(params: FamilyParams, projection: float, line: float) -> float | None:
    """P(result > line), or None when it cannot be read.

    A whole-number line can push, which no family here models, so it reads None for all of them.
    """
    if float(line).is_integer():
        return None
    if isinstance(params, RatioParams):
        probability = over_probability(params.quantiles, projection, line)
        return None if probability is None else probability.p_over
    read = (
        negbin_over_under_push(params, projection, line) if isinstance(params, NegBinParams)
        else scaled_normal_over_under_push(params, projection, line)
    )
    return None if read is None else read.p_over


@dataclass(frozen=True)
class MarketFit:
    params: FamilyParams
    # Spread of actual - projection, for the constant-sigma normal the fit must beat.
    sigma: float


@dataclass(frozen=True)
class ScoredLine:
    case: NhlReplayCase
    line: float
    p_over: float
    normal_p_over: float
    over: bool


@dataclass(frozen=True)
class MarketSelection:
    """Every applicable family's cross-fit result for one market, and the family selected (None means hidden)."""

    results: tuple[CandidateResult, ...]
    selected: Family | None


def fit_market(family: Family, market: NhlLineOnlyMarket, cases: Iterable[NhlReplayCase]) -> MarketFit | None:
    """Parameters plus the normal baseline's sigma, or None when either cannot be fitted."""
    usable = [case for case in cases if case.projection > 0]
    params = fit_family(family, market, usable)
    if params is None:
        return None
    sigma = stdev(case.actual - case.projection for case in usable)
    return MarketFit(params, sigma) if sigma > 0 else None


def score_cases(fit: MarketFit, cases: Iterable[NhlReplayCase]) -> list[ScoredLine]:
    """Each case at each synthetic x.5 line around its projection; a line that cannot be read is skipped."""
    scored = []
    for case in cases:
        if case.projection <= 0:
            continue
        for line in synthetic_lines(case.projection):
            probability = read_family(fit.params, case.projection, line)
            if probability is None:
                continue
            scored.append(ScoredLine(
                case=case, line=line, p_over=probability,
                normal_p_over=normal_over_probability(case.projection, fit.sigma, line),
                over=case.actual > line,
            ))
    return scored


def _by_market(cases: Iterable[NhlReplayCase]) -> dict[NhlLineOnlyMarket, list[NhlReplayCase]]:
    grouped: dict[NhlLineOnlyMarket, list[NhlReplayCase]] = defaultdict(list)
    for case in cases:
        grouped[NhlLineOnlyMarket(case.market)].append(case)
    return grouped


def split_by_parity(cases: Iterable[NhlReplayCase]) -> tuple[list[NhlReplayCase], list[NhlReplayCase]]:
    """(even ISO weeks, odd ISO weeks)."""
    halves: tuple[list[NhlReplayCase], list[NhlReplayCase]] = ([], [])
    for case in cases:
        halves[parity(case.game_date)].append(case)
    return halves


def score_half(
    family: Family, fit_cases: Iterable[NhlReplayCase], scored_cases: Iterable[NhlReplayCase],
) -> list[ScoredLine]:
    """Fit each market on `fit_cases` and score `scored_cases` with it; a market with no fit is skipped."""
    fit_by_market = _by_market(fit_cases)
    lines: list[ScoredLine] = []
    for market, members in _by_market(scored_cases).items():
        fit = fit_market(family, market, fit_by_market.get(market, []))
        if fit is not None:
            lines += score_cases(fit, members)
    return lines


def cross_fit(family: Family, cases: Iterable[NhlReplayCase]) -> list[ScoredLine]:
    """Each half is scored by a fit on the other half, so no case is scored by a fit containing it."""
    even, odd = split_by_parity(cases)
    return score_half(family, even, odd) + score_half(family, odd, even)


def evaluate(family: Family, lines: Sequence[ScoredLine]) -> CandidateResult:
    """One market's pooled lines under the registered display verdict; no lines is insufficient, never a pass."""
    if not lines:
        return CandidateResult(family=family, cases=0, brier=inf, verdict="insufficient")
    report = calibrate(CalibrationPair(line.p_over, line.over) for line in lines)
    normal_brier = sum((line.normal_p_over - line.over) ** 2 for line in lines) / len(lines)
    cases = len({line.case.key for line in lines})
    return CandidateResult(family=family, cases=cases, brier=report.brier, verdict=nhl_display_verdict(cases, report, normal_brier))


def select_markets(cases: Sequence[NhlReplayCase]) -> dict[NhlLineOnlyMarket, MarketSelection]:
    """The development selection: every applicable family cross-fitted per market, then the registered rule."""
    pooled = {family: _by_market_lines(cross_fit(family, cases)) for family in CANDIDATE_ORDER}
    selections = {}
    for market in _by_market(cases):
        results = tuple(
            evaluate(family, pooled[family].get(market, []))
            for family in CANDIDATE_ORDER if family_applies(family, market)
        )
        selections[market] = MarketSelection(results, select_family(results))
    return selections


def _by_market_lines(lines: Iterable[ScoredLine]) -> dict[NhlLineOnlyMarket, list[ScoredLine]]:
    grouped: dict[NhlLineOnlyMarket, list[ScoredLine]] = defaultdict(list)
    for line in lines:
        grouped[NhlLineOnlyMarket(line.case.market)].append(line)
    return grouped
