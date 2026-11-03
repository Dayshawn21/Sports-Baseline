"""The volume model's report-only source and forward record (49d); ingest and freezing keep their sport source.

The shared ranking record would judge a slice on 27i's pick rule alone. 49b's
rule also needs the log-loss clause, so the slice verdicts here come from
`volume_slice_verdict`, and every other field is the shared record's.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_volume_anchor import NFL_VOLUME_ANCHOR_VERSION
from app.core.nfl_volume_projection import NFL_VOLUME_MODEL_VERSION
from app.core.nfl_volume_verdict import (
    EVALUATED_SLICES, LogLossResult, LogLossRow, log_loss_clause, volume_slice_verdict,
)
from app.core.prop_ranking_check import FrozenLine
from app.core.prop_ranking_rule import BREAK_EVEN_BY_ODDS_TYPE, Side, SliceResult, SliceVerdict, one_pick_per_bet, to_pick
from app.core.track_record import verdict_signal
from app.nfl.markets import NFL_PROPS
from app.repositories import nfl, nfl_volume_ranking
from app.repositories.nfl_volume_ranking import VolumeFrozenLine
from app.services import prop_ranking
from app.services.prop_ranking import RankingCalls, RankingRecord, RankingSliceRow, display_standard_error
from app.services.tennis.live_odds_cache import TimedSingleFlight

CACHE_TTL_SECONDS = 15 * 60

SliceState = Literal["evaluated", "not_frozen"]


class NflVolumeRankingSource:
    config = NFL_PROPS
    model_version = NFL_VOLUME_MODEL_VERSION
    over_probability_version = NFL_VOLUME_ANCHOR_VERSION

    async def frozen_lines(self, db: AsyncSession, season: int) -> list[FrozenLine]:
        return await nfl_volume_ranking.get_frozen_gradeable_lines(db, season)

    async def finished_periods(self, db: AsyncSession, season: int) -> set[int]:
        return await nfl.get_finished_weeks(db, season)

    async def frozen_coverage(self, db: AsyncSession, season: int) -> dict[int, tuple[int, int]]:
        return await nfl_volume_ranking.get_frozen_coverage(db, season)


class _LoadedSource(NflVolumeRankingSource):
    """The same source over rows already read, so one query serves the calls and the log-loss rows."""

    def __init__(self, lines: list[FrozenLine]) -> None:
        self._lines = lines

    async def frozen_lines(self, db: AsyncSession, season: int) -> list[FrozenLine]:
        return self._lines


@dataclass(frozen=True)
class VolumeInputs:
    calls: RankingCalls
    # Settled lines of finished weeks by payout: the log-loss clause is judged on a slice's own payout.
    log_rows: dict[str, list[LogLossRow]]
    # Payouts with at least one frozen row, settled or not: the rest read not frozen.
    frozen_payouts: frozenset[str]


@dataclass(frozen=True)
class VolumeSliceState:
    odds_type: str
    side: Side
    state: SliceState
    log_loss: LogLossResult | None


@dataclass(frozen=True)
class VolumeRankingRecord:
    record: RankingRecord
    states: list[VolumeSliceState]
    # Every settled standard line of the finished weeks so far: progress, never a verdict. Rungs are judged per slice.
    log_loss_progress: LogLossResult


def log_loss_rows(lines: list[VolumeFrozenLine], finished_weeks: set[int]) -> dict[str, list[LogLossRow]]:
    """Settled frozen lines of finished weeks by payout; a half-played week never reaches the clause."""
    rows: dict[str, list[LogLossRow]] = {}
    for item in lines:
        frozen = item.frozen
        if frozen.odds_type is None or frozen.period not in finished_weeks:
            continue
        if item.q_vol is None or frozen.p_over is None or frozen.p_under is None:
            continue
        if frozen.outcome == "over" or frozen.outcome == "under" or frozen.outcome == "push":
            rows.setdefault(frozen.odds_type, []).append(LogLossRow(
                game_id=frozen.game_id, week=frozen.period, p_over=frozen.p_over, p_under=frozen.p_under,
                q_vol=item.q_vol, outcome=frozen.outcome,
            ))
    return rows


async def load_volume_inputs(db: AsyncSession, season: int) -> VolumeInputs:
    lines = await nfl_volume_ranking.get_frozen_volume_lines(db, season)
    calls = await prop_ranking.load_ranking_calls(db, _LoadedSource([item.frozen for item in lines]), season)
    payouts = frozenset(item.frozen.odds_type for item in lines if item.frozen.odds_type is not None)
    return VolumeInputs(calls, log_loss_rows(lines, calls.finished_periods), payouts)


def _row(odds_type: str, side: Side, verdict: SliceVerdict, result: SliceResult) -> RankingSliceRow:
    rate = result.hit_rate
    signal = verdict_signal(verdict != "insufficient", rate, result.standard_error, result.break_even)
    # A slice the log-loss clause rejected is never colored for a pick-rule rate that cleared.
    if signal == "positive" and verdict != "adopt":
        signal = "neutral"
    return RankingSliceRow(
        odds_type=odds_type, side=side, verdict=verdict,
        n=result.n, weeks=result.periods, hits=result.hits, hit_rate=rate,
        standard_error=display_standard_error(result.n, rate, result.standard_error),
        break_even=result.break_even, signal=signal,
    )


def build_volume_record(inputs: VolumeInputs, season: int, graded_at: datetime) -> VolumeRankingRecord:
    base = prop_ranking.build_ranking_record(
        inputs.calls, season, graded_at, NFL_VOLUME_MODEL_VERSION, NFL_VOLUME_ANCHOR_VERSION,
    )
    picks = one_pick_per_bet([pick for call in inputs.calls.calls if (pick := to_pick(call)) is not None])
    rows: list[RankingSliceRow] = []
    states: list[VolumeSliceState] = []
    for odds_type, side in EVALUATED_SLICES:
        if odds_type in inputs.frozen_payouts:
            payout_rows = inputs.log_rows.get(odds_type, [])
            decided = volume_slice_verdict(odds_type, [pick for pick in picks if pick.slice == (odds_type, side)], payout_rows)
            rows.append(_row(odds_type, side, decided.verdict, decided.picks))
            states.append(VolumeSliceState(odds_type, side, "evaluated", decided.log_loss))
        else:
            empty = SliceResult("insufficient", 0, 0, 0, BREAK_EVEN_BY_ODDS_TYPE[odds_type])
            rows.append(_row(odds_type, side, "insufficient", empty))
            states.append(VolumeSliceState(odds_type, side, "not_frozen", None))
    standard_rows = inputs.log_rows.get("standard", [])
    progress = log_loss_clause(standard_rows, sorted({row.week for row in standard_rows}))
    return VolumeRankingRecord(replace(base, slices=rows), states, progress)


_VOLUME: TimedSingleFlight[VolumeRankingRecord] = TimedSingleFlight(CACHE_TTL_SECONDS)


async def get_volume_record(db: AsyncSession, season: int) -> VolumeRankingRecord | None:
    """None when grading failed; the failure is shared for the cache window too."""
    async def fetch() -> VolumeRankingRecord:
        return build_volume_record(await load_volume_inputs(db, season), season, datetime.now(UTC))

    return await _VOLUME.get((season, NFL_VOLUME_MODEL_VERSION, NFL_VOLUME_ANCHOR_VERSION), fetch)
