import pytest

from app.core.nfl_usage_shift import (
    CARRIES_BELOW_MIN, NO_CHART_ROW, NOT_FRESH, UsageShift, UsageShiftPlayer, apply_usage_shift, missed_out_players,
    usage_shifts,
)

WALKER, JOHNSON, THIRD = 1, 2, 3


def _player(
    player_id: int, rank: int | None, *, out: bool = False, fresh: bool = True,
    carries: float | None = 10.0, targets: float | None = 2.0, games: int = 8,
) -> UsageShiftPlayer:
    return UsageShiftPlayer(player_id, rank, out, fresh, carries, targets, games)


def _shift(players: list[UsageShiftPlayer], transfer: float = 1.0) -> dict[int, UsageShift]:
    return usage_shifts(players, transfer=transfer, min_own_volume=1.0, max_multiplier=3.0)


def test_a_fresh_out_rb1_hands_transfer_of_his_volume_to_the_rb2() -> None:
    shifts = _shift([
        _player(WALKER, 1, out=True, carries=16.0, targets=3.0),
        _player(JOHNSON, 2, carries=8.0, targets=2.0),
        _player(THIRD, 3, carries=2.0, targets=1.0),
    ], transfer=0.5)

    # Johnson gains half of Walker's 16 carries and 3 targets: (8 + 8) / 8 and (2 + 1.5) / 2.
    assert shifts == {JOHNSON: UsageShift(2.0, 1.75, (WALKER,))}


def test_an_out_player_who_also_missed_last_game_gives_nothing() -> None:
    players = [_player(WALKER, 1, out=True, fresh=False), _player(JOHNSON, 2)]

    assert _shift(players) == {}
    assert missed_out_players(players) == {WALKER: NOT_FRESH}


def test_an_out_player_off_this_weeks_chart_gives_nothing_and_is_missed() -> None:
    players = [_player(WALKER, None, out=True), _player(JOHNSON, 1)]

    assert _shift(players) == {}
    assert missed_out_players(players) == {WALKER: NO_CHART_ROW}


def test_tied_receivers_split_the_volume_equally() -> None:
    shifts = _shift([
        _player(WALKER, 1, out=True, carries=0.0, targets=8.0),
        _player(JOHNSON, 2, carries=None, targets=4.0),
        _player(THIRD, 2, carries=None, targets=4.0),
    ])

    assert shifts[JOHNSON].target_multiplier == shifts[THIRD].target_multiplier == 2.0
    assert shifts[JOHNSON].carry_multiplier == 1.0


def test_a_receiver_below_the_minimum_volume_is_left_unshifted_with_a_reason() -> None:
    shifts = _shift([_player(WALKER, 1, out=True, carries=16.0), _player(JOHNSON, 2, carries=0.5)])

    assert shifts[JOHNSON].carry_multiplier == 1.0
    assert shifts[JOHNSON].unshifted == (CARRIES_BELOW_MIN,)


def test_the_multiplier_is_capped() -> None:
    shifts = _shift([_player(WALKER, 1, out=True, carries=20.0), _player(JOHNSON, 2, carries=2.0)])

    assert shifts[JOHNSON].carry_multiplier == 3.0


def test_an_out_backup_neither_gives_to_nor_receives_from_the_starter() -> None:
    shifts = _shift([
        _player(WALKER, 1, out=True, carries=16.0, targets=0.0),
        _player(JOHNSON, 2, out=True, fresh=False),
        _player(THIRD, 3, carries=4.0),
    ])

    # Two Out players ahead of the RB3 make him active RB1, so Walker's carries go to him.
    assert set(shifts) == {THIRD}
    assert shifts[THIRD].carry_multiplier == pytest.approx(3.0)
    assert shifts[THIRD].from_players == (WALKER,)


def test_nobody_out_shifts_nothing() -> None:
    players = [_player(WALKER, 1), _player(JOHNSON, 2)]

    assert _shift(players) == {}
    assert missed_out_players(players) == {}


SHIFT = UsageShift(carry_multiplier=2.0, target_multiplier=1.5, from_players=(WALKER,))
AVERAGES = {
    "games": 8, "passing_yards": 0.0, "passing_attempts": 0.0, "passing_completions": 0.0,
    "rushing_yards": 40.0, "rushing_attempts": 9.0, "receiving_yards": 20.0, "receptions": 2.0,
    "touchdowns": 0.3, "fantasy_points": 9.0,
}


def _row(market: str, position: str = "RB") -> dict:
    return {"market": market, "position": position, "averages": dict(AVERAGES)}


@pytest.mark.parametrize(("market", "field", "expected"), [
    ("rushing_yards", "rushing_yards", 80.0),
    ("rushing_attempts", "rushing_attempts", 18.0),
    ("receiving_yards", "receiving_yards", 30.0),
    ("receptions", "receptions", 3.0),
])
def test_each_shifted_market_scales_only_its_own_average(market: str, field: str, expected: float) -> None:
    row = _row(market)

    shifted = apply_usage_shift(row, SHIFT)

    assert shifted["averages"][field] == expected
    assert {key: value for key, value in shifted["averages"].items() if key != field} == {
        key: value for key, value in AVERAGES.items() if key != field
    }
    assert shifted["usage_shift"]["from"] == [WALKER]
    assert row["averages"] == AVERAGES


@pytest.mark.parametrize(("market", "position"), [
    ("passing_yards", "RB"), ("fantasy_points", "RB"), ("anytime_touchdown", "RB"), ("rushing_yards", "QB"),
])
def test_other_markets_and_quarterbacks_come_back_unchanged(market: str, position: str) -> None:
    row = _row(market, position)

    assert apply_usage_shift(row, SHIFT) is row


def test_no_shift_returns_the_same_row() -> None:
    row = _row("rushing_yards")

    assert apply_usage_shift(row, None) is row
