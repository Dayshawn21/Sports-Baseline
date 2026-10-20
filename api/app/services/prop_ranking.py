"""Load and record a sport's frozen, settled prop predictions under 27i's ranking rule (17c, from 27j).

The record is what each sport's model page serves (NFL 33d, NBA 20g4), so the
page and the CLI read the same calls through the same rule.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prop_ranking_check import PERIOD_NOT_FINISHED, FrozenLine, PickFunnel, slice_results, to_frozen_call
from app.core.prop_ranking_rule import (
    MIN_PERIODS, MIN_PICK_MARGIN, MIN_PICKS, FrozenCall, Side, SliceResult, SliceVerdict,
)
from app.core.prop_sports import SportPropConfig
from app.core.track_record import Signal, verdict_signal


class RankingSource(Protocol):
    """The read-only subset a single model needs from its sport."""

    @property
    def config(self) -> SportPropConfig: ...

    @property
    def model_version(self) -> str: ...

    @property
    def over_probability_version(self) -> str | None: ...

    async def frozen_lines(self, db: AsyncSession, season: int) -> list[FrozenLine]: ...

    async def finished_periods(self, db: AsyncSession, season: int) -> set[int]: ...

    async def frozen_coverage(self, db: AsyncSession, season: int) -> dict[int, tuple[int, int]]: ...


@dataclass(frozen=True)
class RankingCalls:
    calls: list[FrozenCall]
    exclusions: Counter[str]
    frozen_rows: int
    coverage: dict[int, tuple[int, int]]
    finished_periods: set[int]


async def load_ranking_calls(db: AsyncSession, source: RankingSource, season: int) -> RankingCalls:
    """Each provider prop's latest frozen pre-start row as a settled call, or the reason it is not one."""
    frozen = await source.frozen_lines(db, season)
    finished = await source.finished_periods(db, season)
    coverage = await source.frozen_coverage(db, season)
    # Reports name the unfinished reason after the sport's own period: week_not_finished for NFL.
    unfinished = f"{source.config.period_label}_not_finished"
    calls: list[FrozenCall] = []
    exclusions: Counter[str] = Counter()
    for line in frozen:
        result = to_frozen_call(line, finished, source.model_version, source.over_probability_version)
        if isinstance(result, FrozenCall):
            calls.append(result)
        else:
            exclusions[unfinished if result == PERIOD_NOT_FINISHED else result] += 1
    return RankingCalls(calls, exclusions, len(frozen), coverage, finished)


@dataclass(frozen=True)
class RankingRule:
    min_picks: int
    min_weeks: int
    min_pick_margin: float


@dataclass(frozen=True)
class CoverageWeek:
    week: int
    lines: int
    frozen: int


@dataclass(frozen=True)
class RankingSliceRow:
    odds_type: str
    side: Side
    verdict: SliceVerdict
    n: int
    weeks: int
    hits: int
    hit_rate: float | None
    # None below two picks or on a unanimous rate, where a binomial SE of 0 would read as certainty.
    standard_error: float | None
    break_even: float
    signal: Signal


@dataclass(frozen=True)
class RankingRecord:
    graded_at: datetime
    season: int
    model_version: str
    over_probability_version: str | None
    rule: RankingRule
    finished_weeks: list[int]
    last_settled_week: int | None
    frozen_rows: int
    excluded: dict[str, int]
    coverage: list[CoverageWeek]
    funnel: PickFunnel
    slices: list[RankingSliceRow]


def display_standard_error(n: int, rate: float | None, standard_error: float | None) -> float | None:
    if n < 2 or rate is None or rate in (0.0, 1.0):
        return None
    return standard_error


def _slice_row(odds_type: str, side: Side, result: SliceResult) -> RankingSliceRow:
    return RankingSliceRow(
        odds_type=odds_type, side=side, verdict=result.verdict, n=result.n, weeks=result.periods,
        hits=result.hits, hit_rate=result.hit_rate,
        standard_error=display_standard_error(result.n, result.hit_rate, result.standard_error),
        break_even=result.break_even,
        # The raw SE, so a decided slice is colored exactly as the rule judged it.
        signal=verdict_signal(
            result.verdict != "insufficient", result.hit_rate, result.standard_error, result.break_even,
        ),
    )


def build_ranking_record(
    inputs: RankingCalls, season: int, graded_at: datetime, model_version: str, over_probability_version: str | None,
) -> RankingRecord:
    """The page's record; the period reads as weeks, the period of every sport graded so far."""
    check = slice_results(inputs.calls)
    finished = sorted(inputs.finished_periods)
    return RankingRecord(
        graded_at=graded_at, season=season,
        model_version=model_version, over_probability_version=over_probability_version,
        rule=RankingRule(MIN_PICKS, MIN_PERIODS, MIN_PICK_MARGIN),
        finished_weeks=finished, last_settled_week=finished[-1] if finished else None,
        frozen_rows=inputs.frozen_rows, excluded=dict(sorted(inputs.exclusions.items())),
        coverage=[CoverageWeek(week, lines, frozen) for week, (lines, frozen) in sorted(inputs.coverage.items())],
        funnel=check.funnel,
        slices=[_slice_row(odds_type, side, result) for (odds_type, side), result in check.slices.items()],
    )
