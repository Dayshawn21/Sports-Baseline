from dataclasses import replace

import pytest

from app.core.nfl_targets_grading import TargetsOutcome, TargetsSettlementInput, settle_targets


INPUT = TargetsSettlementInput(
    line=4.5, targets=6.0, player_has_stats=True, offense_snaps=40, game_has_stats=True,
)


@pytest.mark.parametrize("targets, line, outcome", [
    (6.0, 4.5, "over"),
    (3.0, 4.5, "under"),
    (4.0, 4.0, "push"),
    (0.0, 4.5, "under"),
    (0.0, 0.0, "push"),
    (1.0, 0.0, "over"),
])
def test_known_targets_settle_against_the_frozen_line(
    targets: float, line: float, outcome: TargetsOutcome,
) -> None:
    result = settle_targets(replace(INPUT, targets=targets, line=line))

    assert (result.outcome, result.actual) == (outcome, targets)


@pytest.mark.parametrize("line", [None, -1.0, float("nan"), float("inf"), -float("inf")])
def test_missing_or_invalid_lines_cannot_settle(line: float | None) -> None:
    result = settle_targets(replace(INPUT, line=line))

    assert (result.outcome, result.actual) == ("invalid_line", None)


@pytest.mark.parametrize("targets", [None, -1.0, float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("snaps", [None, 0, 40])
def test_unknown_targets_on_an_existing_stat_row_are_never_zeroed(
    targets: float | None, snaps: int | None,
) -> None:
    result = settle_targets(replace(INPUT, targets=targets, offense_snaps=snaps))

    assert (result.outcome, result.actual) == ("stat_unavailable", None)


@pytest.mark.parametrize("targets, has_player_row, snaps", [
    (6.0, True, 40),
    (None, True, 40),
    (None, False, 40),
    (None, False, None),
])
def test_no_game_stats_prevents_settlement_or_voiding(
    targets: float | None, has_player_row: bool, snaps: int | None,
) -> None:
    result = settle_targets(replace(
        INPUT, targets=targets, player_has_stats=has_player_row, offense_snaps=snaps, game_has_stats=False,
    ))

    assert (result.outcome, result.actual) == ("week_not_loaded", None)


@pytest.mark.parametrize("snaps", [None, 0, -1])
def test_absent_player_row_without_positive_snaps_voids(snaps: int | None) -> None:
    result = settle_targets(replace(INPUT, targets=None, player_has_stats=False, offense_snaps=snaps))

    assert (result.outcome, result.actual) == ("void_dnp", None)


@pytest.mark.parametrize("snaps", [1, 40])
def test_absent_player_row_with_positive_snaps_means_zero_targets(snaps: int) -> None:
    result = settle_targets(replace(INPUT, targets=None, player_has_stats=False, offense_snaps=snaps))

    assert (result.outcome, result.actual) == ("under", 0.0)


def test_explicit_zero_needs_no_snap_fallback() -> None:
    result = settle_targets(replace(INPUT, targets=0.0, offense_snaps=None))

    assert (result.outcome, result.actual) == ("under", 0.0)
