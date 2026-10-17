import json
from pathlib import Path

from app.core.nfl_odds_io import parse_io_game_markets

EVENT = json.loads((Path(__file__).parent / "fixtures" / "odds_api_io_nfl_event.json").read_text())


def _by_market(book: str, home_is_stored_home: bool = True) -> dict[str, object]:
    return {row.market: row for row in parse_io_game_markets(EVENT["bookmakers"][book], home_is_stored_home)}


def test_draftkings_tb_at_dal_matches_the_recorded_prices() -> None:
    rows = _by_market("DraftKings")

    assert set(rows) == {"moneyline", "spread", "total"}
    assert (rows["moneyline"].first_odds, rows["moneyline"].second_odds) == (-476, 360)
    assert (rows["spread"].line, rows["spread"].first_odds, rows["spread"].second_odds) == (-8.5, -116, -105)
    assert (rows["total"].line, rows["total"].first_side, rows["total"].second_side) == (47.5, "over", "under")
    assert abs(rows["spread"].first_market_prob + rows["spread"].second_market_prob - 1) < 1e-9


def test_bet365s_main_spread_is_the_least_vigged_rung_of_its_ladder() -> None:
    spread = _by_market("Bet365")["spread"]

    assert (spread.line, spread.first_odds, spread.second_odds) == (-9.5, -108, -114)
    assert spread.raw_market["rungs"] == 77
    assert spread.raw_market["odds"] == [{"hdp": -9.5, "home": "1.93", "away": "1.88"}]
    assert spread.raw_market["updatedAt"] is not None


def test_half_time_markets_are_ignored() -> None:
    assert all(row.market in {"moneyline", "spread", "total"} for row in parse_io_game_markets(EVENT["bookmakers"]["Bet365"], True))


def test_a_flipped_home_swaps_prices_and_restates_the_spread() -> None:
    rows = _by_market("DraftKings", home_is_stored_home=False)

    assert (rows["moneyline"].first_odds, rows["moneyline"].second_odds) == (360, -476)
    assert (rows["spread"].line, rows["spread"].first_odds, rows["spread"].second_odds) == (8.5, -105, -116)
    assert rows["total"].line == 47.5 and rows["total"].first_odds == -116


def test_missing_zero_and_one_sided_prices_are_skipped() -> None:
    markets = [
        {"name": "ML", "odds": [{"home": "0", "away": "2.10"}]},
        {"name": "Spread", "odds": [{"hdp": -3, "home": "1.91"}, {"hdp": -3.5, "home": "1.00", "away": "1.91"}]},
        {"name": "Totals", "odds": [{"over": "1.91", "under": "1.91"}]},
    ]

    assert parse_io_game_markets(markets, True) == []


def test_a_one_sided_rung_never_beats_a_priced_one() -> None:
    markets = [{"name": "Spread", "odds": [{"hdp": -3, "home": "1.91"}, {"hdp": -2.5, "home": "1.80", "away": "2.02"}]}]

    assert [row.line for row in parse_io_game_markets(markets, True)] == [-2.5]
