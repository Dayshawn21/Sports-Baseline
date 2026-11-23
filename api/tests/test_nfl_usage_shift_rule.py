import pytest

from app.core.nfl_projection_backtest import PairedDiff, ReplayCase
from app.core.nfl_usage_shift_rule import (
    USAGE_SHIFT_MIN_SHIFTED_CASES, pick_transfer, shifted_paired, usage_shift_verdict,
)


def _case(player_id: int, projection: float, shifted: bool = False) -> ReplayCase:
    return ReplayCase(player_id, 10, 5, "RB", "rushing_yards", projection, 50.0, shifted)


def test_shifted_paired_compares_only_the_shifted_cases() -> None:
    production = [_case(1, 40.0), _case(2, 40.0)]
    # Player 2's unshifted case would dilute the gain if it were counted.
    variant = [_case(1, 48.0, shifted=True), _case(2, 40.0)]

    diff = shifted_paired(production, variant)

    assert diff.n == 1
    assert diff.production_mae == 10.0
    assert diff.variant_mae == 2.0


def test_shifted_paired_with_nothing_shifted_raises() -> None:
    with pytest.raises(ValueError):
        shifted_paired([_case(1, 40.0)], [_case(1, 40.0)])


def test_pick_transfer_takes_the_lowest_mae() -> None:
    assert pick_transfer({0.0: 10.0, 0.5: 9.0, 1.0: 9.5}) == 0.5


def test_pick_transfer_breaks_a_tie_toward_the_smaller() -> None:
    assert pick_transfer({1.0: 9.0, 0.0: 10.0, 0.5: 9.0}) == 0.5


def test_pick_transfer_can_pick_production() -> None:
    assert pick_transfer({0.0: 9.0, 0.5: 9.0, 1.0: 9.2}) == 0.0


def _diff(n: int, relative: float, mean_diff: float, se: float) -> PairedDiff:
    return PairedDiff(n, 10.0, 10.0 * (1 + relative), mean_diff, se, relative)


@pytest.mark.parametrize(("diff", "verdict"), [
    (_diff(USAGE_SHIFT_MIN_SHIFTED_CASES - 1, -0.10, -1.0, 0.1), "insufficient"),
    # 1% better, but only 1.9 standard errors from zero.
    (_diff(USAGE_SHIFT_MIN_SHIFTED_CASES, -0.01, -0.19, 0.1), "reject"),
    # Far beyond noise, but under 1% better.
    (_diff(500, -0.009, -1.0, 0.1), "reject"),
    (_diff(USAGE_SHIFT_MIN_SHIFTED_CASES, -0.01, -0.21, 0.1), "adopt"),
])
def test_usage_shift_verdict(diff: PairedDiff, verdict: str) -> None:
    assert usage_shift_verdict(diff) == verdict
