"""Select a Rec Targets development baseline on one common 2024 cohort."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Literal

from app.core.nfl_projection_backtest import PairedDiff, ReplayCase, Verdict, adoption_verdict, paired
from app.core.nfl_targets_projection import TargetsReplayRow, project_targets, valid_target_count

DEVELOPMENT_SEASON = 2024
REGULAR_SEASON_WEEKS = range(1, 19)
TargetsArm = Literal["reference", "moneyline", "recent_form"]


@dataclass
class TargetsCoverage:
    week: int
    total: int = 0
    missing_actual: int = 0
    invalid_actual: int = 0
    no_baseline: int = 0
    thin_baseline: int = 0
    scored: int = 0
    missing_moneyline: int = 0
    unresolved_side: int = 0
    missing_history: int = 0
    invalid_history: int = 0


@dataclass(frozen=True)
class TargetsComparison:
    arm: TargetsArm
    incumbent: TargetsArm
    diff: PairedDiff | None
    verdict: Verdict


@dataclass(frozen=True)
class TargetsBacktest:
    cases_by_arm: dict[TargetsArm, tuple[ReplayCase, ...]]
    comparisons: tuple[TargetsComparison, ...]
    coverage: tuple[TargetsCoverage, ...]
    selected_arm: TargetsArm | None
    moneyline_scaled: bool
    recent_form: bool


def validate_development_season(season: int) -> None:
    if season != DEVELOPMENT_SEASON:
        raise ValueError("Rec Targets baseline selection accepts 2024 only; do not read the 2025 holdout")


def _count_context(row: TargetsReplayRow, coverage: TargetsCoverage) -> None:
    probability = row.input.home_market_prob
    coverage.missing_moneyline += int(
        probability is None or not isfinite(probability) or not 0 < probability < 1
    )
    coverage.unresolved_side += int(row.input.player_is_home is None)
    for item in row.input.observations:
        if (item.season, item.week) >= (row.input.season, row.input.week):
            continue
        coverage.missing_history += int(item.targets is None)
        coverage.invalid_history += int(item.targets is not None and not valid_target_count(item.targets))


def _cohort(rows: Sequence[TargetsReplayRow]) -> tuple[list[TargetsReplayRow], tuple[TargetsCoverage, ...]]:
    coverage = {week: TargetsCoverage(week) for week in REGULAR_SEASON_WEEKS}
    eligible = []
    seen: set[tuple[int, int, str]] = set()
    for row in rows:
        validate_development_season(row.input.season)
        if row.week != row.input.week or row.week not in coverage or row.position not in ("RB", "WR", "TE"):
            raise ValueError("Replay rows require a matching REG week 1-18 and an RB/WR/TE position")
        key = (row.player_id, row.game_id, "receiving_targets")
        if key in seen:
            raise ValueError(f"Duplicate Rec Targets replay key: {key}")
        seen.add(key)
        week = coverage[row.week]
        week.total += 1
        _count_context(row, week)
        if row.actual is None:
            week.missing_actual += 1
        elif not valid_target_count(row.actual):
            week.invalid_actual += 1
        else:
            projection = project_targets(row.input, moneyline_scaled=False, recent_form=False)
            if projection.projection is None:
                if projection.baseline_season is None:
                    week.no_baseline += 1
                else:
                    week.thin_baseline += 1
            else:
                eligible.append(row)
                week.scored += 1
    return eligible, tuple(coverage.values())


def _score(
    rows: Sequence[TargetsReplayRow], *, moneyline_scaled: bool, recent_form: bool,
) -> tuple[ReplayCase, ...]:
    cases = []
    for row in rows:
        projection = project_targets(row.input, moneyline_scaled=moneyline_scaled, recent_form=recent_form)
        assert projection.projection is not None and row.actual is not None
        cases.append(ReplayCase(
            player_id=row.player_id, game_id=row.game_id, week=row.week, position=row.position,
            market="receiving_targets", projection=projection.projection, actual=row.actual,
        ))
    return tuple(cases)


def _compare(
    arm: TargetsArm, incumbent: TargetsArm, cases: dict[TargetsArm, tuple[ReplayCase, ...]],
) -> TargetsComparison:
    diff = paired(cases[incumbent], cases[arm]) if cases[incumbent] else None
    return TargetsComparison(arm, incumbent, diff, adoption_verdict(diff) if diff is not None else "insufficient")


def select_baseline(rows: Sequence[TargetsReplayRow]) -> TargetsBacktest:
    eligible, coverage = _cohort(rows)
    cases: dict[TargetsArm, tuple[ReplayCase, ...]] = {
        "reference": _score(eligible, moneyline_scaled=False, recent_form=False),
        "moneyline": _score(eligible, moneyline_scaled=True, recent_form=False),
    }
    moneyline = _compare("moneyline", "reference", cases)
    moneyline_scaled = moneyline.verdict == "adopt"
    incumbent: TargetsArm = "moneyline" if moneyline_scaled else "reference"
    cases["recent_form"] = _score(eligible, moneyline_scaled=moneyline_scaled, recent_form=True)
    recent = _compare("recent_form", incumbent, cases)
    recent_form = recent.verdict == "adopt"
    selected: TargetsArm = "recent_form" if recent_form else incumbent
    return TargetsBacktest(cases, (moneyline, recent), coverage, selected if eligible else None,
                           moneyline_scaled, recent_form)
