"""The rule that decides whether a PrizePicks line may be ranked by P(over) (27h).

Pre-registered 2026-09-26, before any frozen prediction existed (build-plan
item 27i). 27j applies it to frozen, settled predictions; 27h may use a slice
only after its verdict is `adopt`. Changing any constant here starts a new
sample under a new version; it is never a re-read of the old one.

Shared by every sport since 17c (formerly `app/core/nfl_ranking_rule.py`). A
period is the sport's grading period; for NFL it is the week, so NFL verdicts
are exactly 27i's.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import sqrt
from typing import Literal

from app.core.prop_ev import DEMON_LEG_DECIMAL, GOBLIN_LEG_DECIMAL, STANDARD_LEG_DECIMAL

Side = Literal["over", "under"]
Slice = tuple[str, Side]
SliceVerdict = Literal["adopt", "reject", "insufficient"]

BREAK_EVEN_BY_ODDS_TYPE: dict[str, float] = {
    "standard": 1 / STANDARD_LEG_DECIMAL,
    "goblin": 1 / GOBLIN_LEG_DECIMAL,
    "demon": 1 / DEMON_LEG_DECIMAL,
}
# PrizePicks only offers "more" on goblin and demon lines.
PLAYABLE_SIDES: dict[str, tuple[Side, ...]] = {
    "standard": ("over", "under"),
    "goblin": ("over",),
    "demon": ("over",),
}
MIN_PICK_MARGIN = 0.03
MIN_PICKS = 200
MIN_PERIODS = 4
STANDARD_ERRORS_REQUIRED = 2.0


@dataclass(frozen=True)
class FrozenCall:
    """One frozen full-game prediction on a line that settled over or under."""

    line_id: int
    period: int
    player_id: int
    game_id: int
    market: str
    odds_type: str
    p_over: float | None
    p_under: float | None
    outcome: Side


@dataclass(frozen=True)
class Pick:
    call: FrozenCall
    side: Side
    probability: float
    break_even: float

    @property
    def margin(self) -> float:
        return self.probability - self.break_even

    @property
    def slice(self) -> Slice:
        return (self.call.odds_type, self.side)

    @property
    def hit(self) -> bool:
        return self.call.outcome == self.side


@dataclass(frozen=True)
class SliceResult:
    verdict: SliceVerdict
    # The fixed verdict sample once it exists, otherwise every pick so far.
    n: int
    periods: int
    hits: int
    break_even: float

    @property
    def hit_rate(self) -> float | None:
        return self.hits / self.n if self.n else None

    @property
    def standard_error(self) -> float | None:
        rate = self.hit_rate
        return sqrt(rate * (1 - rate) / self.n) if rate is not None else None


def pick_side(odds_type: str, p_over: float | None, p_under: float | None) -> tuple[Side, float] | None:
    """The side worth playing and its probability, or None when no side clears break-even plus the margin."""
    break_even = BREAK_EVEN_BY_ODDS_TYPE.get(odds_type)
    if break_even is None or p_over is None or p_under is None:
        return None
    probabilities = {"over": p_over, "under": p_under}
    clearing = [
        (side, probabilities[side]) for side in PLAYABLE_SIDES[odds_type]
        if probabilities[side] >= break_even + MIN_PICK_MARGIN
    ]
    return max(clearing, key=lambda item: item[1]) if clearing else None


def to_pick(call: FrozenCall) -> Pick | None:
    chosen = pick_side(call.odds_type, call.p_over, call.p_under)
    if chosen is None:
        return None
    side, probability = chosen
    return Pick(call, side, probability, BREAK_EVEN_BY_ODDS_TYPE[call.odds_type])


def one_pick_per_bet(picks: Iterable[Pick]) -> list[Pick]:
    """One pick per player, game, market, odds type and side: the rung that clears break-even by the most.

    A goblin or demon ladder is one decision about one player's game, so its
    rungs are not independent evidence.
    """
    best: dict[tuple[int, int, str, str, Side], Pick] = {}
    for pick in picks:
        c = pick.call
        key = (c.player_id, c.game_id, c.market, c.odds_type, pick.side)
        current = best.get(key)
        if current is None or (pick.margin, -c.line_id) > (current.margin, -current.call.line_id):
            best[key] = pick
    return sorted(best.values(), key=lambda pick: (pick.call.period, pick.call.line_id))


def verdict_sample(picks: Sequence[Pick]) -> list[Pick] | None:
    """The shortest run of whole periods, from the first, holding MIN_PICKS picks across MIN_PERIODS periods.

    Fixing the sample this way means later periods never change a verdict, so a
    periodic report is not a repeated test.
    """
    sample: list[Pick] = []
    for period in sorted({pick.call.period for pick in picks}):
        sample += [pick for pick in picks if pick.call.period == period]
        if len(sample) >= MIN_PICKS and len({pick.call.period for pick in sample}) >= MIN_PERIODS:
            return sample
    return None


def slice_verdict(picks: Sequence[Pick]) -> SliceResult:
    """The pre-registered verdict for one slice's deduplicated picks."""
    slices = {pick.slice for pick in picks}
    if len(slices) > 1:
        raise ValueError(f"slice_verdict takes one slice, got {sorted(slices)}")
    if not picks:
        raise ValueError("slice_verdict needs at least one pick")
    break_even = picks[0].break_even
    sample = verdict_sample(picks)
    counted = sample if sample is not None else list(picks)
    result = SliceResult(
        verdict="insufficient", n=len(counted), periods=len({p.call.period for p in counted}),
        hits=sum(p.hit for p in counted), break_even=break_even,
    )
    if sample is None:
        return result
    lower = result.hit_rate - STANDARD_ERRORS_REQUIRED * result.standard_error
    verdict: SliceVerdict = "adopt" if lower > break_even else "reject"
    return SliceResult(verdict, result.n, result.periods, result.hits, break_even)
