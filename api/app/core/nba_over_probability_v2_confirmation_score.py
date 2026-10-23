"""Score 44a's frozen P(over) families once on the 2026-27 sample (item 44b).

The sample is regular-season weeks 1-4 of `CONFIRMATION_SEASON`, read only once
every one of those weeks is finished. Probabilities come from the frozen
parameters, never a refit. The constant-sigma normal baseline takes its sigma
from the fit season, as 20g1's did, so the scored season never shapes its own
yardstick. A refit on the fit season serves only as a drift check.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import isclose, isinf
from statistics import stdev
from typing import Literal

from app.core.count_over_probability import NegBinParams, ScaledNormalParams
from app.core.nba_over_probability import MIN_BIN_PAIRS, NbaDisplayVerdict, ScoredLine
from app.core.nba_over_probability_v2 import CONFIRMATION_WEEKS, Family
from app.core.nba_over_probability_v2_crossfit import FamilyParams, PushContext, evaluate, fit_family, integer_lines, read_family
from app.core.nba_projection_backtest import NbaReplayCase
from app.core.nfl_over_probability_calibration import CalibrationPair, calibrate, normal_over_probability, synthetic_lines

GateState = Literal["accruing", "ready"]
DRIFT_REL_TOL = 1e-9


@dataclass(frozen=True)
class ConfirmationResult:
    family: Family
    cases: int
    pairs: int
    ece: float
    # None when no bin holds MIN_BIN_PAIRS pairs, so no bin can fail the gap check.
    worst_gap: float | None
    brier: float
    normal_brier: float
    verdict: NbaDisplayVerdict


@dataclass(frozen=True)
class Drift:
    market: str
    frozen: FamilyParams
    refit: FamilyParams | None


def gate(finished_weeks: Collection[int], weeks: Sequence[int] = CONFIRMATION_WEEKS) -> GateState:
    return "ready" if all(week in finished_weeks for week in weeks) else "accruing"


def family_of(params: FamilyParams) -> Family:
    return "negbin" if isinstance(params, NegBinParams) else "scaled_normal"


def sample_cases(
    cases: Iterable[NbaReplayCase], week_by_game: Mapping[int, int], carried: Collection[str],
    weeks: Sequence[int] = CONFIRMATION_WEEKS,
) -> list[NbaReplayCase]:
    """Regular-season cases in the confirmation weeks, carried markets only, projection above zero."""
    return [
        case for case in cases
        if case.game_type == "REG" and week_by_game.get(case.game_id) in weeks
        and case.market in carried and case.projection > 0
    ]


def _by_market(cases: Iterable[NbaReplayCase], markets: Collection[str]) -> dict[str, list[NbaReplayCase]]:
    grouped: dict[str, list[NbaReplayCase]] = defaultdict(list)
    for case in cases:
        if case.market in markets and case.projection > 0:
            grouped[case.market].append(case)
    return grouped


def normal_sigmas(fit_cases: Iterable[NbaReplayCase], markets: Collection[str]) -> dict[str, float]:
    """Per market, the stdev of actual minus projection on the fit season (20g1's baseline)."""
    return {
        market: stdev(case.actual - case.projection for case in members)
        for market, members in _by_market(fit_cases, markets).items() if len(members) >= 2
    }


def refit(frozen: Mapping[str, FamilyParams], fit_cases: Iterable[NbaReplayCase]) -> dict[str, FamilyParams]:
    grouped = _by_market(fit_cases, frozen)
    return {market: fit_family(family_of(params), grouped.get(market, [])) for market, params in frozen.items()}


def _same(x: float, y: float) -> bool:
    return x == y if isinf(x) or isinf(y) else isclose(x, y, rel_tol=DRIFT_REL_TOL)


def _matches(frozen: FamilyParams, again: FamilyParams | None) -> bool:
    if isinstance(frozen, NegBinParams) and isinstance(again, NegBinParams):
        return _same(frozen.r, again.r)
    if isinstance(frozen, ScaledNormalParams) and isinstance(again, ScaledNormalParams):
        return _same(frozen.a, again.a) and _same(frozen.b, again.b)
    return False


def parameter_drift(frozen: Mapping[str, FamilyParams], refitted: Mapping[str, FamilyParams]) -> list[Drift]:
    """Markets whose fit-season refit no longer reproduces the frozen parameters."""
    return [
        Drift(market, params, refitted.get(market))
        for market, params in frozen.items() if not _matches(params, refitted.get(market))
    ]


def score_sample(
    frozen: Mapping[str, FamilyParams], sigmas: Mapping[str, float], cases: Iterable[NbaReplayCase],
) -> list[ScoredLine]:
    scored = []
    for case in cases:
        params, sigma = frozen.get(case.market), sigmas.get(case.market)
        if params is None or sigma is None:
            continue
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


def evaluate_markets(frozen: Mapping[str, FamilyParams], lines: Sequence[ScoredLine]) -> dict[str, ConfirmationResult]:
    """Each carried market's display verdict and its checks; a market with no scored line is absent."""
    grouped: dict[str, list[ScoredLine]] = defaultdict(list)
    for line in lines:
        grouped[line.case.market].append(line)
    results = {}
    for market, params in frozen.items():
        members = grouped[market]
        if not members:
            continue
        verdict = evaluate(family_of(params), members)
        report = calibrate(CalibrationPair(line.p_over, line.over) for line in members)
        gaps = [b.gap for b in report.bins if b.n >= MIN_BIN_PAIRS]
        results[market] = ConfirmationResult(
            family=verdict.family, cases=verdict.cases, pairs=len(members), ece=report.ece,
            worst_gap=max(gaps) if gaps else None, brier=verdict.brier,
            normal_brier=sum((line.normal_p_over - line.over) ** 2 for line in members) / len(members),
            verdict=verdict.verdict,
        )
    return results


def push_context(frozen: Mapping[str, FamilyParams], cases: Iterable[NbaReplayCase]) -> dict[str, PushContext]:
    """Mean predicted P(push) against the observed push rate at whole-number lines; information only."""
    totals: dict[str, list[float]] = defaultdict(lambda: [0, 0.0, 0])
    for case in cases:
        params = frozen.get(case.market)
        if params is None:
            continue
        for line in integer_lines(case.projection):
            probability = read_family(params, case.projection, line)
            if probability is None:
                continue
            total = totals[case.market]
            total[0] += 1
            total[1] += probability.p_push
            total[2] += case.actual == line
    return {
        market: PushContext(pairs=int(n), predicted=predicted / n, observed=observed / n)
        for market, (n, predicted, observed) in totals.items()
    }
