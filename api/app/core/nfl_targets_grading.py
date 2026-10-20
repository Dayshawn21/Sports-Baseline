"""Settle frozen Rec Targets lines without treating unknown stats as zero."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

from app.core.prop_settlement import LineOutcome, settle

TargetsOutcome = LineOutcome | Literal["void_dnp", "week_not_loaded", "stat_unavailable", "invalid_line"]


@dataclass(frozen=True)
class TargetsSettlementInput:
    line: float | None
    targets: float | None
    player_has_stats: bool
    offense_snaps: int | None
    game_has_stats: bool


@dataclass(frozen=True)
class TargetsSettlement:
    outcome: TargetsOutcome
    actual: float | None


def settle_targets(input: TargetsSettlementInput) -> TargetsSettlement:
    if input.line is None or not isfinite(input.line) or input.line < 0:
        return TargetsSettlement("invalid_line", None)
    if not input.game_has_stats:
        return TargetsSettlement("week_not_loaded", None)
    if not input.player_has_stats:
        if input.offense_snaps is None or input.offense_snaps <= 0:
            return TargetsSettlement("void_dnp", None)
        # NFLverse omits players with no recorded stats, even if they played snaps.
        actual = 0.0
    else:
        actual = input.targets
        if actual is None or not isfinite(actual) or actual < 0:
            return TargetsSettlement("stat_unavailable", None)
    return TargetsSettlement(settle(actual, input.line), actual)
