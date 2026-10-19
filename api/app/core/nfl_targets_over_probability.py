"""P(over) for NFL Rec Targets from the `nfl-targets-v1` projection (item 39b).

A per-position distribution of actual / projection, fitted on 2024 and scored
once on the 2025 holdout, read with 27g's sport-agnostic `over_probability`.
Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from statistics import stdev
from typing import Literal

from app.core.nfl_over_probability import over_probability, ratio_quantiles
from app.core.nfl_over_probability_calibration import CalibrationReport, normal_over_probability, synthetic_lines
from app.core.nfl_projection_backtest import ReplayCase
from app.core.nfl_targets_projection import TargetsReplayRow, project_targets, valid_target_count

NFL_TARGETS_OVER_PROBABILITY_VERSION = "nfl-targets-pover-v1"
TARGETS_MARKET = "receiving_targets"
TARGETS_POSITIONS = ("RB", "WR", "TE")
REGULAR_SEASON_WEEKS = range(1, 19)

# Pre-registered 2026-10-18 with the 39b spec, before any fit was scored. 27g's
# values, kept as Rec Targets' own so a change to another rule cannot move this one.
MIN_CASES = 300
MAX_ECE = 0.02
MAX_BIN_GAP = 0.05
MIN_BIN_PAIRS = 200

TargetsDisplayVerdict = Literal["show", "hide", "insufficient"]


@dataclass(frozen=True)
class TargetsCaseCoverage:
    season: int
    total: int = 0
    missing_actual: int = 0
    invalid_actual: int = 0
    no_baseline: int = 0
    thin_baseline: int = 0
    zero_projection: int = 0
    cases: int = 0


@dataclass(frozen=True)
class TargetsCaseSet:
    cases: tuple[ReplayCase, ...]
    coverage: TargetsCaseCoverage


@dataclass(frozen=True)
class PositionFit:
    quantiles: tuple[float, ...]
    # Spread of actual - projection, for the normal baseline the fit must beat.
    sigma: float


@dataclass(frozen=True)
class ScoredLine:
    case: ReplayCase
    line: float
    p_over: float
    normal_p_over: float
    over: bool


def _check_row(row: TargetsReplayRow, season: int, seen: set[tuple[int, int]]) -> None:
    if row.input.season != season or row.week != row.input.week or row.week not in REGULAR_SEASON_WEEKS:
        raise ValueError(f"Rec Targets case rows must be {season} REG weeks 1-18")
    if row.position not in TARGETS_POSITIONS:
        raise ValueError(f"Rec Targets cases are RB, WR and TE only, not {row.position}")
    key = (row.player_id, row.game_id)
    if key in seen:
        raise ValueError(f"Duplicate Rec Targets case key: {key}")
    seen.add(key)


def targets_cases(rows: Iterable[TargetsReplayRow], season: int) -> TargetsCaseSet:
    """Scorable cases for one season under `project_targets` defaults, with what was dropped and why."""
    counts = dict.fromkeys(
        ("total", "missing_actual", "invalid_actual", "no_baseline", "thin_baseline", "zero_projection"), 0,
    )
    cases: list[ReplayCase] = []
    seen: set[tuple[int, int]] = set()
    for row in rows:
        _check_row(row, season, seen)
        counts["total"] += 1
        if row.actual is None:
            counts["missing_actual"] += 1
            continue
        if not valid_target_count(row.actual):
            counts["invalid_actual"] += 1
            continue
        projection = project_targets(row.input)
        if projection.projection is None:
            counts["no_baseline" if projection.baseline_season is None else "thin_baseline"] += 1
        elif projection.projection <= 0:
            # A ratio needs a positive projection, so these can be neither fitted nor read.
            counts["zero_projection"] += 1
        else:
            cases.append(ReplayCase(
                player_id=row.player_id, game_id=row.game_id, week=row.week, position=row.position,
                market=TARGETS_MARKET, projection=projection.projection, actual=row.actual,
            ))
    return TargetsCaseSet(tuple(cases), TargetsCaseCoverage(season=season, cases=len(cases), **counts))


def fit_positions(cases: Iterable[ReplayCase]) -> dict[str, PositionFit]:
    by_position: dict[str, list[ReplayCase]] = defaultdict(list)
    for case in cases:
        if case.projection > 0:
            by_position[case.position].append(case)
    return {
        position: PositionFit(
            quantiles=ratio_quantiles((case.projection, case.actual) for case in members),
            sigma=stdev(case.actual - case.projection for case in members),
        )
        for position, members in by_position.items()
        if len(members) >= 2
    }


def score_cases(fits: Mapping[str, PositionFit], cases: Sequence[ReplayCase]) -> list[ScoredLine]:
    """Each case at each synthetic x.5 line around its projection; positions without a fit are skipped."""
    scored = []
    for case in cases:
        fit = fits.get(case.position)
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


def targets_display_verdict(cases_n: int, report: CalibrationReport, normal_brier: float) -> TargetsDisplayVerdict:
    if cases_n < MIN_CASES:
        return "insufficient"
    # Recomputed from the bins so this rule's minimum bin size governs, not the one `calibrate` was built with.
    large_gaps = [b.gap for b in report.bins if b.n >= MIN_BIN_PAIRS]
    calibrated = report.ece <= MAX_ECE and all(gap <= MAX_BIN_GAP for gap in large_gaps)
    return "show" if calibrated and report.brier <= normal_brier else "hide"
