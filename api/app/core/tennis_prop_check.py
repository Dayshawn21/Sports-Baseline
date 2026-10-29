"""The rule that decides which tennis PrizePicks slices may be ranked by P(over) (48e).

Pre-registered 2026-10-29, before any props-v3 or later snapshot was graded.
It applies 27i's shared rule (`app/core/prop_ranking_rule.py`) per stat, tour,
total anchor, payout and side, with a 3 SE gate where 27i uses 2: tennis has
hundreds of slices where NFL has four, so 2 SE would adopt some on noise alone.
Changing any constant here is a new rule name and a new sample, never a re-read
of the old one. Each projection version is graded as its own sample.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Literal, NamedTuple

from app.core.box_score_join import JoinResult
from app.core.prop_projection import normalize_stat_type
from app.core.prop_ranking_rule import (
    BREAK_EVEN_BY_ODDS_TYPE, FrozenCall, Pick, Side, SliceResult, one_pick_per_bet, to_pick, verdict_sample,
)
from app.core.prop_settlement import resolve_actual, settle
from app.core.tennis_format import display_tour
from app.core.tennis_grading import is_completed_score

TENNIS_PROP_CHECK_RULE = "tennis-props-check-v1"
TENNIS_STANDARD_ERRORS_REQUIRED = 3.0
# routers/props.py projects from the book total only at 17 games or more.
BOOK_TOTAL_MIN_GAMES = 17.0
# Box-score stats settle after the next day's refetch (26e), so a week joins
# the sample only once its late lines have had time to land.
MATURITY_DAYS = 3
# Flags that mean the row is not a real pre-match projection of a supported stat.
EXCLUDED_FLAGS = frozenset({
    "match_finished", "match_link_invalid", "bo5_unsupported_stat", "unsupported_stat", "ungraded_stat",
    "missing_player", "missing_match",
})
UNKNOWN_ODDS_TYPE = "unknown_odds_type"
NO_PROBABILITY = "no_probability"
INCOMPLETE_SCORE = "incomplete_score"
PERIOD_NOT_FINISHED = "period_not_finished"

Anchor = Literal["book", "model"]
# A frozen line that is not a call: an excluded flag, one of the reasons above,
# or the settlement reason (push, incomplete_score, ...) passed through.
Exclusion = str


class TennisSlice(NamedTuple):
    stat: str
    tour: str
    anchor: Anchor
    odds_type: str
    side: Side


@dataclass(frozen=True)
class TennisFrozenLine:
    """The latest pre-start snapshot of one PrizePicks line, settled."""

    line_id: int
    player_id: int
    match_id: int
    stat_type: str
    match_tour: str | None
    p1_tour: str | None
    p2_tour: str | None
    odds_type: str | None
    start_time: datetime
    p_over: float | None
    p_under: float | None
    p_push: float | None
    market_total_games: float | None
    data_quality_flags: tuple[str, ...]
    # "over" or "under" makes a call; anything else is why the line cannot be one.
    outcome: str


@dataclass(frozen=True)
class CheckFunnel:
    rows: int
    calls: int
    picks: int
    # After `one_pick_per_bet` collapses ladder rungs into one decision.
    bets: int


@dataclass(frozen=True)
class CheckResult:
    slices: dict[TennisSlice, SliceResult]
    exclusions: dict[Exclusion, int]
    funnel: CheckFunnel
    finished_weeks: int


def settled_outcome(
    stat_type: str, line: float, score: str | None, best_of: int | None, player_is_p1: bool,
    join: JoinResult | None,
) -> str:
    """over, under or push by the 26f settlement path, or why the line has no result."""
    if not is_completed_score(score, best_of or 3):
        return INCOMPLETE_SCORE
    actual, reason = resolve_actual(normalize_stat_type(stat_type), score, player_is_p1, join)
    if actual is None:
        return str(reason)
    return settle(actual, line)


def anchor_of(market_total_games: float | None) -> Anchor:
    return "book" if market_total_games is not None and market_total_games >= BOOK_TOTAL_MIN_GAMES else "model"


def slice_key(line: TennisFrozenLine, side: Side) -> TennisSlice:
    return TennisSlice(
        stat=normalize_stat_type(line.stat_type),
        tour=display_tour(line.match_tour, line.p1_tour, line.p2_tour),
        anchor=anchor_of(line.market_total_games),
        odds_type=(line.odds_type or "").lower(),
        side=side,
    )


def period_of(start_time: datetime) -> int:
    """The ordinal of the UTC Monday that starts the line's week."""
    day = start_time.astimezone(UTC).date()
    return (day - timedelta(days=day.weekday())).toordinal()


def finished_periods(periods: Iterable[int], as_of: date) -> frozenset[int]:
    """Weeks whose Sunday is past and whose late box scores have had MATURITY_DAYS to land."""
    return frozenset(p for p in periods if date.fromordinal(p) + timedelta(days=7 + MATURITY_DAYS) <= as_of)


def _push_excluded(line: TennisFrozenLine) -> tuple[float, float] | None:
    if line.p_over is None or line.p_under is None or line.p_push is None or line.p_push >= 1:
        return None
    actionable = 1.0 - line.p_push
    return line.p_over / actionable, line.p_under / actionable


def to_frozen_call(line: TennisFrozenLine, finished: Collection[int]) -> FrozenCall | Exclusion:
    """A settled over-or-under call with push-excluded probabilities, or why the line cannot be one."""
    flagged = sorted(EXCLUDED_FLAGS.intersection(line.data_quality_flags))
    if flagged:
        return flagged[0]
    odds_type = (line.odds_type or "").lower()
    if odds_type not in BREAK_EVEN_BY_ODDS_TYPE:
        return UNKNOWN_ODDS_TYPE
    probabilities = _push_excluded(line)
    if probabilities is None:
        return NO_PROBABILITY
    period = period_of(line.start_time)
    if period not in finished:
        return PERIOD_NOT_FINISHED
    if line.outcome not in ("over", "under"):
        return line.outcome
    outcome: Side = "over" if line.outcome == "over" else "under"
    return FrozenCall(
        line_id=line.line_id, period=period, player_id=line.player_id, game_id=line.match_id,
        market=normalize_stat_type(line.stat_type), odds_type=odds_type,
        p_over=probabilities[0], p_under=probabilities[1], outcome=outcome,
    )


def tennis_slice_verdict(picks: Sequence[Pick]) -> SliceResult:
    """27i's fixed verdict sample, judged at TENNIS_STANDARD_ERRORS_REQUIRED."""
    if not picks:
        raise ValueError("tennis_slice_verdict needs at least one pick")
    sample = verdict_sample(picks)
    counted = sample if sample is not None else list(picks)
    result = SliceResult(
        verdict="insufficient", n=len(counted), periods=len({p.call.period for p in counted}),
        hits=sum(p.hit for p in counted), break_even=picks[0].break_even,
    )
    if sample is None or result.hit_rate is None or result.standard_error is None:
        return result
    lower = result.hit_rate - TENNIS_STANDARD_ERRORS_REQUIRED * result.standard_error
    return replace(result, verdict="adopt" if lower > result.break_even else "reject")


def check(lines: Sequence[TennisFrozenLine], as_of: date) -> CheckResult:
    """Every slice with a pick, graded under the pre-registered rule as of `as_of`.

    Ladder rungs collapse into one bet before slicing, so the surviving rung's
    own tour and anchor place it and no decision is counted twice.
    """
    finished = finished_periods({period_of(line.start_time) for line in lines}, as_of)
    exclusions: Counter[Exclusion] = Counter()
    calls: list[FrozenCall] = []
    for line in lines:
        call = to_frozen_call(line, finished)
        if isinstance(call, FrozenCall):
            calls.append(call)
        else:
            exclusions[call] += 1
    picks = [pick for call in calls if (pick := to_pick(call)) is not None]
    bets = one_pick_per_bet(picks)
    by_id = {line.line_id: line for line in lines}
    grouped: dict[TennisSlice, list[Pick]] = {}
    for bet in bets:
        grouped.setdefault(slice_key(by_id[bet.call.line_id], bet.side), []).append(bet)
    return CheckResult(
        slices={key: tennis_slice_verdict(group) for key, group in sorted(grouped.items())},
        exclusions=dict(exclusions),
        funnel=CheckFunnel(rows=len(lines), calls=len(calls), picks=len(picks), bets=len(bets)),
        finished_weeks=len(finished),
    )


def adopted(result: CheckResult) -> frozenset[TennisSlice]:
    return frozenset(key for key, slice_result in result.slices.items() if slice_result.verdict == "adopt")
