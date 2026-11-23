"""The 70b3 usage-shift arm's fixed values, development grid, selection rule and holdout rule.

Fixed before any usage-shift arm is scored; see the pre-registration commit.
Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from app.core.nfl_projection_backtest import (
    MIN_RELATIVE_MAE_IMPROVEMENT, STANDARD_ERRORS_REQUIRED, PairedDiff, ReplayCase, Verdict, paired,
)

# Carries or targets per game below which a receiver is never scaled: a ratio on
# about one touch a game is noise, not a projection.
USAGE_SHIFT_MIN_OWN_VOLUME = 2.0
# A backup taking a full workload really does about triple his carries.
USAGE_SHIFT_MAX_MULTIPLIER = 3.0
# Transfer shares scored on 2024; a transfer of 0 is production itself.
USAGE_SHIFT_TRANSFER_GRID = (0.5, 1.0)
# Sized to one season's rated receiving sample (76 shifted rows a market in
# 2024, counted before any score). Rushing, at 15 a season, reads insufficient
# by design.
USAGE_SHIFT_MIN_SHIFTED_CASES = 60
# Set once the rule above is committed (70b3 Step 5).
USAGE_SHIFT_PREREGISTRATION_COMMIT: str | None = None
# Each market's 2024 pick under `pick_transfer` (70b3 Step 6); empty until then.
# A market at 0, or missing, is not a holdout candidate.
USAGE_SHIFT_TRANSFER_BY_MARKET: dict[str, float] = {}


def usage_shift_arm_name(transfer: float) -> str:
    return f"usage_shift_t{round(transfer * 10):02d}"


def shifted_paired(production: Iterable[ReplayCase], variant: Iterable[ReplayCase]) -> PairedDiff:
    """The variant's shifted cases against production's on the same player, game and market.

    An unshifted case is production by construction, so it would only dilute the difference.
    """
    return paired(production, [case for case in variant if case.shifted])


def pick_transfer(mae_by_transfer: Mapping[float, float]) -> float:
    """The transfer with the lowest development MAE on shifted rows, ties to the smaller; 0 is production."""
    if not mae_by_transfer:
        raise ValueError("pick_transfer needs at least one transfer")
    return min(sorted(mae_by_transfer), key=lambda transfer: mae_by_transfer[transfer])


def usage_shift_verdict(diff: PairedDiff) -> Verdict:
    if diff.n < USAGE_SHIFT_MIN_SHIFTED_CASES:
        return "insufficient"
    improves_enough = diff.relative_mae_change <= -MIN_RELATIVE_MAE_IMPROVEMENT
    beyond_noise = diff.mean_diff < -STANDARD_ERRORS_REQUIRED * diff.standard_error
    return "adopt" if improves_enough and beyond_noise else "reject"
