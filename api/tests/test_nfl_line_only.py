import pytest

from app.core.nfl_line_only import LINE_ONLY_COLUMNS, _RULES, line_only_value
from app.nfl.markets import NflLineOnlyMarket as M

ROW = {
    "targets": 9, "passing_tds": 2, "interceptions": 1, "rushing_yards": 31, "receiving_yards": 64,
    "passing_yards": 248, "touchdowns": 1, "fg_made": 3, "pat_made": 2, "punts": 4,
}


@pytest.mark.parametrize(("market", "expected"), [
    (M.RECEIVING_TARGETS, 9.0),
    (M.PASSING_TOUCHDOWNS, 2.0),
    (M.INTERCEPTIONS, 1.0),
    (M.RUSHING_RECEIVING_YARDS, 95.0),
    (M.PASSING_RUSHING_YARDS, 279.0),
    (M.PASSING_RUSHING_RECEIVING_TOUCHDOWNS, 3.0),
    (M.FIELD_GOALS_MADE, 3.0),
    (M.KICKING_POINTS, 11.0),
    (M.PUNTS, 4.0),
])
def test_each_market_settles_on_its_rule(market: M, expected: float) -> None:
    assert line_only_value(market, ROW) == expected


@pytest.mark.parametrize("missing", ["fg_made", "pat_made"])
def test_kicking_points_needs_both_kicking_counts(missing: str) -> None:
    assert line_only_value(M.KICKING_POINTS, ROW | {missing: None}) is None


@pytest.mark.parametrize("missing", ["rushing_yards", "receiving_yards"])
def test_a_combo_is_unknown_when_either_part_is(missing: str) -> None:
    assert line_only_value(M.RUSHING_RECEIVING_YARDS, ROW | {missing: None}) is None


def test_a_zero_is_a_real_zero() -> None:
    assert line_only_value(M.PUNTS, ROW | {"punts": 0}) == 0.0


def test_every_line_only_market_has_a_rule_and_its_columns_are_listed() -> None:
    assert set(_RULES) == set(M)
    assert set(LINE_ONLY_COLUMNS) == set(ROW)
