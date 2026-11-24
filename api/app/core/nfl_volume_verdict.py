"""The forward verdict for `nfl-volume-anchor-v1` (49d): 49b's two clauses applied to a frozen sample.

A slice reads `adopt` only if 27i's pick rule passes on its fixed verdict
sample and the blend's log loss beats both the raw volume probability and a
constant 0.5 on every line of the slice's payout in those same weeks. This module adds no
threshold: every number is 49b's or 27i's, imported, so changing one starts a
new version and a new sample.

"At least 3 of the 4 sample weeks" is written for a four-week sample; the 27i
sample can run longer, so the weeks required scale as
`ceil(weeks * LOG_LOSS_MIN_WEEKS_WON / MIN_PERIODS)`, which is 3 at four weeks.

Pure: no DB, no I/O.
"""
from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.core.nfl_volume_anchor import LOG_LOSS_MIN_WEEKS_WON, LOG_LOSS_STANDARD_ERRORS, clamp_q
from app.core.nfl_volume_backtest import clustered_se
from app.core.prop_ranking_rule import (
    BREAK_EVEN_BY_ODDS_TYPE, MIN_PERIODS, Pick, SliceResult, SliceVerdict, slice_verdict as pick_rule_verdict,
    verdict_sample,
)

Outcome = Literal["over", "under", "push"]
Slice = tuple[str, Literal["over", "under"]]

# Whether a payout has a frozen sample yet is read from the data, not fixed here (49e).
EVALUATED_SLICES: tuple[Slice, ...] = (("standard", "over"), ("standard", "under"), ("goblin", "over"), ("demon", "over"))


@dataclass(frozen=True)
class LogLossRow:
    """One frozen line settled: the served probabilities, the raw projection chance and the result."""

    game_id: int
    week: int
    p_over: float
    p_under: float
    q_vol: float
    outcome: Outcome


@dataclass(frozen=True)
class LogLossResult:
    n: int
    weeks: int
    weeks_won: int
    weeks_required: int
    blend: float | None
    raw: float | None
    half: float | None
    # Blend minus reference, so a negative mean difference means the blend is better.
    raw_difference: float | None
    raw_standard_error: float | None
    half_difference: float | None
    half_standard_error: float | None
    passed: bool


@dataclass(frozen=True)
class VolumeSliceVerdict:
    verdict: SliceVerdict
    picks: SliceResult
    log_loss: LogLossResult | None


def _blend_loss(row: LogLossRow) -> float:
    q = row.p_over / (row.p_over + row.p_under)
    return -math.log(q if row.outcome == "over" else 1.0 - q)


def _raw_loss(row: LogLossRow) -> float:
    q = clamp_q(row.q_vol)
    return -math.log(q if row.outcome == "over" else 1.0 - q)


def _weeks_required(weeks: int) -> int:
    return math.ceil(weeks * LOG_LOSS_MIN_WEEKS_WON / MIN_PERIODS)


def _better(differences: Sequence[float], clusters: Sequence[int]) -> tuple[float | None, float | None, bool]:
    """The mean paired difference, its clustered SE, and whether it is below zero by more than the required SEs."""
    if not differences:
        return None, None, False
    mean = sum(differences) / len(differences)
    try:
        standard_error = clustered_se(differences, clusters)
    except ValueError:
        return mean, None, False
    return mean, standard_error, mean < -LOG_LOSS_STANDARD_ERRORS * standard_error


def log_loss_clause(rows: Sequence[LogLossRow], weeks: Sequence[int]) -> LogLossResult:
    """49b's second clause over `weeks`; pushes and rows from other weeks are left out."""
    sample = set(weeks)
    counted = [row for row in rows if row.week in sample and row.outcome != "push"]
    required = _weeks_required(len(sample))
    if not counted:
        return LogLossResult(0, len(sample), 0, required, None, None, None, None, None, None, None, False)
    blend = [_blend_loss(row) for row in counted]
    raw = [_raw_loss(row) for row in counted]
    half = [math.log(2.0)] * len(counted)
    clusters = [row.game_id for row in counted]
    raw_mean, raw_se, raw_better = _better([b - r for b, r in zip(blend, raw)], clusters)
    half_mean, half_se, half_better = _better([b - h for b, h in zip(blend, half)], clusters)
    by_week: dict[int, list[int]] = defaultdict(list)
    for index, row in enumerate(counted):
        by_week[row.week].append(index)
    weeks_won = sum(
        1 for indexes in by_week.values()
        if sum(blend[i] for i in indexes) < sum(raw[i] for i in indexes)
        and sum(blend[i] for i in indexes) < sum(half[i] for i in indexes)
    )
    return LogLossResult(
        n=len(counted), weeks=len(sample), weeks_won=weeks_won, weeks_required=required,
        blend=sum(blend) / len(blend), raw=sum(raw) / len(raw), half=math.log(2.0),
        raw_difference=raw_mean, raw_standard_error=raw_se, half_difference=half_mean, half_standard_error=half_se,
        passed=raw_better and half_better and weeks_won >= required,
    )


def volume_slice_verdict(odds_type: str, picks: Sequence[Pick], rows: Sequence[LogLossRow]) -> VolumeSliceVerdict:
    """`adopt` needs both clauses on the fixed pick sample; `insufficient` until that sample exists."""
    if not picks:
        empty = SliceResult("insufficient", 0, 0, 0, BREAK_EVEN_BY_ODDS_TYPE[odds_type])
        return VolumeSliceVerdict("insufficient", empty, None)
    pick_result = pick_rule_verdict(list(picks))
    sample = verdict_sample(picks)
    if sample is None:
        return VolumeSliceVerdict("insufficient", pick_result, None)
    clause = log_loss_clause(rows, sorted({pick.call.period for pick in sample}))
    verdict: SliceVerdict = "adopt" if pick_result.verdict == "adopt" and clause.passed else "reject"
    return VolumeSliceVerdict(verdict, pick_result, clause)
