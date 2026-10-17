import pytest

from app.core.prop_sports import (
    FULL_GAME_SEGMENT, SportPropConfig, board_leagues, market_for_stat, segment_for_league_name,
)
from app.nfl.markets import NFL_PROPS

TOY_NBA = SportPropConfig(
    code="nba",
    league_prefix="NBA",
    segment_suffixes={"1H": "first_half", "1Q": "q1"},
    board_segments=frozenset({FULL_GAME_SEGMENT, "first_half"}),
    market_aliases={"points": "points", "pts+rebs+asts": "pra"},
    period_label="day",
)

# What the pre-17c NFL-only mapping returned for every league name its tests used.
NFL_SEGMENTS_BEFORE_17C = {
    "NFL": "full_game", " nfl ": "full_game", "NFLSZN": "season", "NFL1H": "first_half",
    "NFL2H": "second_half", "NFL1Q": "q1", "NFL2Q": "q2", "NFL3Q": "q3", "NFL4Q": "q4",
    "nfl 1h": "first_half", "NFL-1Q": "q1", "NFL 1Q": "q1",
    "NBA": None, "MLB": None, "NCAAF": None, "": None, "NFLDRAFT": None,
}


@pytest.mark.parametrize(("name", "segment"), NFL_SEGMENTS_BEFORE_17C.items())
def test_nfl_config_maps_leagues_as_before(name: str, segment: str | None) -> None:
    assert segment_for_league_name(name, NFL_PROPS) == segment


def test_nfl_board_keeps_full_game_first_half_and_first_quarter() -> None:
    leagues = [{"id": str(index), "attributes": {"name": name}} for index, name in enumerate(
        ("NFL", "NFL1H", "NFL1Q", "NFL2H", "NFL2Q", "NFL3Q", "NFL4Q", "NFLSZN", "NBA"), start=1,
    )]

    assert [(league_id, segment) for league_id, _, segment in board_leagues(leagues, NFL_PROPS)] == [
        (1, "full_game"), (2, "first_half"), (3, "q1"),
    ]


def test_another_sport_reads_only_its_own_leagues() -> None:
    assert segment_for_league_name("NBA1H", TOY_NBA) == "first_half"
    assert segment_for_league_name("nba", TOY_NBA) == FULL_GAME_SEGMENT
    for other in ("WNBA", "NFL", "NBA4Q", "NBASZN"):
        assert segment_for_league_name(other, TOY_NBA) is None, other
    leagues = [{"id": 1, "attributes": {"name": "NBA1Q"}}, {"id": 2, "attributes": {"name": "NBA1H"}}]
    assert board_leagues(leagues, TOY_NBA) == [(2, "NBA1H", "first_half")]


def test_market_aliases_ignore_case_and_padding() -> None:
    assert market_for_stat(" Pts+Rebs+Asts ", TOY_NBA) == "pra"
    assert market_for_stat("Receiving Yards", NFL_PROPS) == "receiving_yards"
    assert market_for_stat("Longest Rush", NFL_PROPS) is None
