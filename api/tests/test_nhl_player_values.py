import datetime as dt

import pytest

from app.core.nhl_player_values import GOALIE_MARKETS, NHL_FIRST_HISTORY_SEASON, nhl_stat_value, player_props_date
from app.nhl.markets import NhlLineOnlyMarket

ROW = {
    "shots": 4, "points": 2, "assists": 1, "goals": 1, "power_play_points": 1, "blocked_shots": 3,
    "plus_minus": -2, "hits": 5, "faceoffs_won": 9, "time_on_ice_seconds": 3720,
    "saves": 27, "goals_against": 3,
}


@pytest.mark.parametrize(("market", "expected"), [
    (NhlLineOnlyMarket.SHOTS_ON_GOAL, 4.0),
    (NhlLineOnlyMarket.POINTS, 2.0),
    (NhlLineOnlyMarket.ASSISTS, 1.0),
    (NhlLineOnlyMarket.GOALS, 1.0),
    (NhlLineOnlyMarket.POWER_PLAY_POINTS, 1.0),
    (NhlLineOnlyMarket.BLOCKED_SHOTS, 3.0),
    (NhlLineOnlyMarket.PLUS_MINUS, -2.0),
    (NhlLineOnlyMarket.HITS, 5.0),
    (NhlLineOnlyMarket.FACEOFFS_WON, 9.0),
    (NhlLineOnlyMarket.TIME_ON_ICE, 62.0),
    (NhlLineOnlyMarket.GOALIE_SAVES, 27.0),
    (NhlLineOnlyMarket.GOALS_ALLOWED, 3.0),
])
def test_each_market_reads_its_column(market: NhlLineOnlyMarket, expected: float) -> None:
    assert nhl_stat_value(market, ROW) == expected


def test_every_market_has_a_column() -> None:
    for market in NhlLineOnlyMarket:
        assert nhl_stat_value(market, ROW) is not None


def test_time_on_ice_rounds_to_hundredths_of_a_minute() -> None:
    assert nhl_stat_value(NhlLineOnlyMarket.TIME_ON_ICE, {"time_on_ice_seconds": 1111}) == 18.52


@pytest.mark.parametrize("market", list(NhlLineOnlyMarket))
def test_a_null_stat_is_none_not_zero(market: NhlLineOnlyMarket) -> None:
    assert nhl_stat_value(market, {key: None for key in ROW}) is None


def test_zero_is_a_real_value() -> None:
    assert nhl_stat_value(NhlLineOnlyMarket.GOALS, {"goals": 0}) == 0.0


def test_goalie_markets_and_history_floor() -> None:
    assert GOALIE_MARKETS == {NhlLineOnlyMarket.GOALIE_SAVES, NhlLineOnlyMarket.GOALS_ALLOWED}
    assert NHL_FIRST_HISTORY_SEASON == 2023


D = dt.date


def test_a_named_date_is_honored_even_with_no_lines() -> None:
    assert player_props_date(D(2026, 11, 4), D(2026, 11, 2), []) == D(2026, 11, 4)
    assert player_props_date(D(2026, 11, 4), D(2026, 11, 2), [D(2026, 11, 2)]) == D(2026, 11, 4)


def test_default_wins_when_the_player_has_lines_then() -> None:
    assert player_props_date(None, D(2026, 11, 2), [D(2026, 10, 30), D(2026, 11, 2), D(2026, 11, 3)]) == D(2026, 11, 2)


def test_latest_earlier_date_when_default_has_none() -> None:
    assert player_props_date(None, D(2026, 11, 2), [D(2026, 10, 28), D(2026, 10, 30), D(2026, 11, 3)]) == D(2026, 10, 30)


def test_earliest_later_date_when_nothing_is_earlier() -> None:
    assert player_props_date(None, D(2026, 11, 2), [D(2026, 11, 5), D(2026, 11, 3)]) == D(2026, 11, 3)


def test_default_when_the_player_has_no_lines_at_all() -> None:
    assert player_props_date(None, D(2026, 11, 2), []) == D(2026, 11, 2)
