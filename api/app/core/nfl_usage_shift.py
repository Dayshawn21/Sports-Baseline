"""Hand a freshly Out starter's carries or targets to the teammate who takes his place (70b).

Backtest only: no served projection imports this. Pure: no DB, no I/O.

For one team and position in one week, a giver is a player who is Out on the
Friday report, is on this week's chart, and played his team's previous game. An
absence that is not fresh is already inside his backup's recent averages, so it
is never shifted twice. A receiver is a teammate who is not Out and whose active
rank (chart rank minus the Out players charted ahead of him) equals the giver's
chart rank; tied receivers split the volume.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.nfl.markets import NflPropMarket

CARRIES_BELOW_MIN = "carries_below_min"
TARGETS_BELOW_MIN = "targets_below_min"
NO_CHART_ROW = "no_chart_row"
NOT_FRESH = "not_fresh"


@dataclass(frozen=True)
class UsageShiftPlayer:
    player_id: int
    depth_rank: int | None
    out: bool
    # Played his team's latest game before this week.
    fresh: bool
    carries_per_game: float | None
    targets_per_game: float | None
    games: int


@dataclass(frozen=True)
class UsageShift:
    carry_multiplier: float
    target_multiplier: float
    from_players: tuple[int, ...]
    # Why a volume was left at 1.0 although a giver handed some over.
    unshifted: tuple[str, ...] = ()


def _active_rank(player: UsageShiftPlayer, charted_out: Sequence[UsageShiftPlayer]) -> int | None:
    if player.out or player.depth_rank is None:
        return None
    return player.depth_rank - sum(out.depth_rank < player.depth_rank for out in charted_out if out.depth_rank is not None)


def _multiplier(own: float | None, gained: float, min_own_volume: float, max_multiplier: float) -> float | None:
    """None when there is volume to hand over but too little own volume to scale."""
    if gained == 0:
        return 1.0
    if own is None or own < min_own_volume:
        return None
    return min((own + gained) / own, max_multiplier)


def usage_shifts(
    players: Sequence[UsageShiftPlayer], transfer: float, min_own_volume: float, max_multiplier: float,
) -> dict[int, UsageShift]:
    """Each receiver's carry and target multipliers for one team-position-week."""
    charted_out = [player for player in players if player.out and player.depth_rank is not None]
    givers = [player for player in charted_out if player.fresh]
    gained: dict[int, tuple[float, float, list[int]]] = {}
    for giver in givers:
        receivers = [player for player in players if _active_rank(player, charted_out) == giver.depth_rank]
        for receiver in receivers:
            carries, targets, sources = gained.get(receiver.player_id, (0.0, 0.0, []))
            gained[receiver.player_id] = (
                carries + transfer * (giver.carries_per_game or 0.0) / len(receivers),
                targets + transfer * (giver.targets_per_game or 0.0) / len(receivers),
                [*sources, giver.player_id],
            )
    by_id = {player.player_id: player for player in players}
    shifts = {}
    for player_id, (carries, targets, sources) in gained.items():
        player = by_id[player_id]
        carry = _multiplier(player.carries_per_game, carries, min_own_volume, max_multiplier)
        target = _multiplier(player.targets_per_game, targets, min_own_volume, max_multiplier)
        unshifted = tuple(reason for reason, value in ((CARRIES_BELOW_MIN, carry), (TARGETS_BELOW_MIN, target)) if value is None)
        shifts[player_id] = UsageShift(carry or 1.0, target or 1.0, tuple(sources), unshifted)
    return shifts


SHIFT_POSITIONS = frozenset({"RB", "WR", "TE"})
# Each market's baseline fields and the volume that drives them. Passing,
# fantasy and anytime TD are never shifted.
_CARRY_MARKETS = {NflPropMarket.RUSHING_YARDS: "rushing_yards", NflPropMarket.RUSHING_ATTEMPTS: "rushing_attempts"}
_TARGET_MARKETS = {NflPropMarket.RECEIVING_YARDS: "receiving_yards", NflPropMarket.RECEPTIONS: "receptions"}


def apply_usage_shift(row: dict, shift: UsageShift | None) -> dict:
    """The row with its market's own average scaled by the shift; any other row comes back as it is.

    Apply after the season blend, so the shift stacks on what the slate serves.
    """
    if shift is None or row.get("position") not in SHIFT_POSITIONS:
        return row
    market = NflPropMarket(row["market"])
    if market in _CARRY_MARKETS:
        field, multiplier = _CARRY_MARKETS[market], shift.carry_multiplier
    elif market in _TARGET_MARKETS:
        field, multiplier = _TARGET_MARKETS[market], shift.target_multiplier
    else:
        return row
    averages = {**row["averages"], field: row["averages"][field] * multiplier}
    return {**row, "averages": averages, "usage_shift": {"multiplier": multiplier, "from": list(shift.from_players)}}


def missed_out_players(players: Sequence[UsageShiftPlayer]) -> dict[int, str]:
    """Out players who give nothing this week, and why."""
    return {
        player.player_id: NO_CHART_ROW if player.depth_rank is None else NOT_FRESH
        for player in players
        if player.out and (player.depth_rank is None or not player.fresh)
    }
