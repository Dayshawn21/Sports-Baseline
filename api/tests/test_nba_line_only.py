import pytest

from app.core.nba_line_only import has_rule, line_only_value
from app.nba.markets import NbaLineOnlyMarket, NbaMarket, NbaPropMarket as M

ALL_MARKETS: list[NbaMarket] = [*M, *NbaLineOnlyMarket]

ROW = {
    "did_not_play": False, "points": 27, "rebounds": 8, "assists": 6, "steals": 2, "blocks": 1,
    "three_pointers_made": 4,
}


@pytest.mark.parametrize("market", ALL_MARKETS)
def test_every_market_has_a_rule(market: NbaMarket) -> None:
    assert has_rule(market)
    assert line_only_value(market, ROW) is not None


@pytest.mark.parametrize(("market", "expected"), [
    (M.POINTS, 27), (M.REBOUNDS, 8), (M.ASSISTS, 6), (M.THREES_MADE, 4), (M.BLOCKS, 1),
    (M.POINTS_REBOUNDS_ASSISTS, 41), (M.POINTS_REBOUNDS, 35), (M.POINTS_ASSISTS, 33), (M.REBOUNDS_ASSISTS, 14),
])
def test_singles_and_sums(market: M, expected: int) -> None:
    assert line_only_value(market, ROW) == float(expected)


@pytest.mark.parametrize(("stats", "expected"), [
    ({"points": 22, "rebounds": 11}, 1.0),
    ({"points": 12, "assists": 10, "rebounds": 10}, 1.0),
    ({"rebounds": 10, "blocks": 10}, 1.0),
    ({"points": 35, "rebounds": 9}, 0.0),
    ({"points": 9, "rebounds": 9, "assists": 9}, 0.0),
])
def test_double_double(stats: dict[str, int], expected: float) -> None:
    row = {"did_not_play": False, "points": 0, "rebounds": 0, "assists": 0, "steals": 0, "blocks": 0, **stats}
    assert line_only_value(NbaLineOnlyMarket.DOUBLE_DOUBLE, row) == expected


@pytest.mark.parametrize("market", list(M))
def test_dnp_is_none_never_zero(market: M) -> None:
    row = {"did_not_play": True, "points": None, "rebounds": None, "assists": None, "steals": None,
           "blocks": None, "three_pointers_made": None}
    assert line_only_value(market, row) is None


@pytest.mark.parametrize("market", [M.POINTS_REBOUNDS_ASSISTS, NbaLineOnlyMarket.DOUBLE_DOUBLE])
def test_missing_column_is_none(market: M) -> None:
    row = {key: value for key, value in ROW.items() if key != "assists"}
    assert line_only_value(market, row) is None
