import pytest

from app.core.prop_sports import FULL_GAME_SEGMENT, board_leagues, market_for_stat, segment_for_league_name
from app.nba.markets import NBA_MARKETS, NBA_PROPS, NbaLineOnlyMarket, NbaMarket, NbaPropMarket, nba_market

# Every NBA and WNBA league name in the 2026-10-06 PrizePicks catalog.
CATALOG = [
    (7, "NBA"), (84, "NBA1H"), (80, "NBA2H"), (192, "NBA1Q"), (149, "NBA4Q"), (173, "NBASZN"),
    (188, "NBASZN2"), (237, "NBAP"), (40, "NBASL"), (310, "NBASL2H"), (250, "NBA SERIES"),
    (3, "WNBA"), (4, "WNBA1H"), (5, "WNBA1Q"), (6, "WNBA2H"), (8, "WNBA4Q"), (9, "WNBASZN"),
    (10, "WNBA SERIES"), (11, "ALLSTAR WNBA"), (12, "ALLSTAR WNBA 2H"),
]

BOARD_NAMES = {
    "Points": NbaPropMarket.POINTS,
    "Rebounds": NbaPropMarket.REBOUNDS,
    "Assists": NbaPropMarket.ASSISTS,
    "3-PT Made": NbaPropMarket.THREES_MADE,
    "Blocked Shots": NbaPropMarket.BLOCKS,
    "Pts+Rebs+Asts": NbaPropMarket.POINTS_REBOUNDS_ASSISTS,
    "Pts+Rebs": NbaPropMarket.POINTS_REBOUNDS,
    "Pts+Asts": NbaPropMarket.POINTS_ASSISTS,
    "Rebs+Asts": NbaPropMarket.REBOUNDS_ASSISTS,
    "Double-Double": NbaLineOnlyMarket.DOUBLE_DOUBLE,
}


def test_only_the_full_game_league_is_on_the_board() -> None:
    leagues = [{"id": league_id, "attributes": {"name": name}} for league_id, name in CATALOG]
    assert board_leagues(leagues, NBA_PROPS) == [(7, "NBA", FULL_GAME_SEGMENT)]


def test_first_half_is_recognized_but_off_the_board() -> None:
    assert segment_for_league_name("NBA1H", NBA_PROPS) == "first_half"
    assert "first_half" not in NBA_PROPS.board_segments


@pytest.mark.parametrize("name", [
    "NBAP", "NBASZN", "NBASZN2", "NBA4Q", "NBASL", "NBASL2H", "NBA SERIES",
    "WNBA", "WNBA1H", "WNBA1Q", "WNBA2H", "WNBA4Q", "WNBASZN", "WNBA SERIES", "ALLSTAR WNBA", "ALLSTAR WNBA 2H",
])
def test_other_leagues_have_no_board_segment(name: str) -> None:
    assert segment_for_league_name(name, NBA_PROPS) not in NBA_PROPS.board_segments


@pytest.mark.parametrize(("stat", "market"), BOARD_NAMES.items())
def test_board_stat_names_map_case_insensitively(stat: str, market: NbaMarket) -> None:
    assert market_for_stat(stat, NBA_PROPS) == market
    assert market_for_stat(f" {stat.upper()} ", NBA_PROPS) == market


def test_every_market_has_a_board_name() -> None:
    assert set(BOARD_NAMES.values()) == {*NbaPropMarket, *NbaLineOnlyMarket}


def test_modelled_and_line_only_markets_are_disjoint_and_keep_their_stored_values() -> None:
    assert not {m.value for m in NbaPropMarket} & {m.value for m in NbaLineOnlyMarket}
    assert [m.value for m in NbaPropMarket] == [
        "points", "rebounds", "assists", "threes_made", "blocks",
        "points_rebounds_assists", "points_rebounds", "points_assists", "rebounds_assists",
    ]
    assert [m.value for m in NbaLineOnlyMarket] == ["double_double"]


def test_each_alias_lands_in_exactly_one_enum() -> None:
    for market in NBA_PROPS.market_aliases.values():
        assert isinstance(market, NbaPropMarket) != isinstance(market, NbaLineOnlyMarket)


@pytest.mark.parametrize("stat", ["Points (Combo)", "Steals", "Fantasy Score"])
def test_unseen_and_combo_names_are_unmapped(stat: str) -> None:
    assert market_for_stat(stat, NBA_PROPS) is None


def test_nba_market_parses_every_stored_value_and_rejects_others() -> None:
    assert [nba_market(market.value) for market in NBA_MARKETS] == list(NBA_MARKETS)
    assert isinstance(nba_market("double_double"), NbaLineOnlyMarket)
    with pytest.raises(ValueError):
        nba_market("fantasy_score")
