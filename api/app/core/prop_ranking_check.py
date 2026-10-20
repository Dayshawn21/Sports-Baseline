"""Apply 27i's pre-registered ranking rule to frozen, settled prop predictions (27j).

Each provider prop is graded on its latest frozen pre-start row, at the line
that row was frozen against. The rule itself lives, unchanged, in
`app/core/prop_ranking_rule.py`. Settlement is each sport's own: a frozen line
arrives here already settled. Formerly `app/core/nfl_ranking_check.py` (17c).

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from app.core.prop_ranking_rule import (
    BREAK_EVEN_BY_ODDS_TYPE, PLAYABLE_SIDES, FrozenCall, Side, Slice, SliceResult, one_pick_per_bet, slice_verdict,
    to_pick,
)

# A frozen line that is not a call: a version or period reason here, or the
# sport's own settlement reason (push, void_dnp, ...) passed through unchanged.
Exclusion = str
PERIOD_NOT_FINISHED = "period_not_finished"

SLICES: tuple[Slice, ...] = tuple((odds_type, side) for odds_type, sides in PLAYABLE_SIDES.items() for side in sides)


@dataclass(frozen=True)
class FrozenLine:
    """The line a prediction was frozen on, settled by its sport, with what was served."""

    line_id: int
    period: int
    player_id: int
    game_id: int
    market: str
    odds_type: str | None
    # "over" or "under" makes a call; anything else is why the line cannot be one.
    outcome: str
    p_over: float | None
    p_under: float | None
    model_version: str
    # None when the slate served no P(over) for the line.
    over_probability_version: str | None


@dataclass(frozen=True)
class PickFunnel:
    calls: int
    with_p_over: int
    picks: int
    # After `one_pick_per_bet` collapses ladder rungs into one decision.
    bets: int


@dataclass(frozen=True)
class RankingCheck:
    slices: dict[Slice, SliceResult]
    funnel: PickFunnel


def to_frozen_call(
    frozen: FrozenLine, finished_periods: Collection[int], model_version: str, over_probability_version: str | None,
) -> FrozenCall | Exclusion:
    """A settled over-or-under call, or the reason the frozen line cannot be one."""
    if frozen.model_version != model_version or frozen.over_probability_version not in (None, over_probability_version):
        return "wrong_version"
    # A period counts only once it is whole, so a half-played period can never
    # fix a verdict sample that later games would then change.
    if frozen.period not in finished_periods:
        return PERIOD_NOT_FINISHED
    if frozen.outcome not in ("over", "under"):
        return frozen.outcome
    outcome: Side = "over" if frozen.outcome == "over" else "under"
    return FrozenCall(
        line_id=frozen.line_id, period=frozen.period, player_id=frozen.player_id, game_id=frozen.game_id,
        market=frozen.market, odds_type=frozen.odds_type or "",
        p_over=frozen.p_over if over_probability_version is not None else None,
        p_under=frozen.p_under if over_probability_version is not None else None,
        outcome=outcome,
    )


def slice_results(calls: Sequence[FrozenCall]) -> RankingCheck:
    """Every slice's verdict under 27i's rule; an empty slice reads insufficient rather than raising."""
    picks = [pick for call in calls if (pick := to_pick(call)) is not None]
    bets = one_pick_per_bet(picks)
    slices: dict[Slice, SliceResult] = {}
    for slice_ in SLICES:
        in_slice = [pick for pick in bets if pick.slice == slice_]
        slices[slice_] = (
            slice_verdict(in_slice) if in_slice
            else SliceResult("insufficient", 0, 0, 0, BREAK_EVEN_BY_ODDS_TYPE[slice_[0]])
        )
    funnel = PickFunnel(
        calls=len(calls),
        with_p_over=sum(call.p_over is not None for call in calls),
        picks=len(picks),
        bets=len(bets),
    )
    return RankingCheck(slices, funnel)
