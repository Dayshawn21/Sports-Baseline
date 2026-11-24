import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.core.nhl_odds import event_start, match_nhl_game, parse_nhl_game_markets, provider_team_code

EVENT = json.loads((Path(__file__).parent / "fixtures" / "odds_api_io_nhl_event.json").read_text())
START = datetime(2026, 10, 24, tzinfo=UTC)
GAME = {"game_id": 7, "start_utc": START, "home_team": "MTL", "away_team": "CHI"}


@pytest.mark.parametrize(("name", "code"), [
    ("Anaheim Ducks", "ANA"), ("Boston Bruins", "BOS"), ("Buffalo Sabres", "BUF"),
    ("Calgary Flames", "CGY"), ("Carolina Hurricanes", "CAR"), ("Chicago Blackhawks", "CHI"),
    ("Colorado Avalanche", "COL"), ("Columbus Blue Jackets", "CBJ"), ("Dallas Stars", "DAL"),
    ("Detroit Red Wings", "DET"), ("Edmonton Oilers", "EDM"), ("Florida Panthers", "FLA"),
    ("Los Angeles Kings", "LAK"), ("Minnesota Wild", "MIN"), ("Montréal Canadiens", "MTL"),
    ("Nashville Predators", "NSH"), ("New Jersey Devils", "NJD"), ("New York Islanders", "NYI"),
    ("New York Rangers", "NYR"), ("Ottawa Senators", "OTT"), ("Philadelphia Flyers", "PHI"),
    ("Pittsburgh Penguins", "PIT"), ("San Jose Sharks", "SJS"), ("Seattle Kraken", "SEA"),
    ("St. Louis Blues", "STL"), ("Tampa Bay Lightning", "TBL"), ("Toronto Maple Leafs", "TOR"),
    ("Utah Mammoth", "UTA"), ("Vancouver Canucks", "VAN"), ("Vegas Golden Knights", "VGK"),
    ("Washington Capitals", "WSH"), ("Winnipeg Jets", "WPG"),
])
def test_current_team_names(name: str, code: str) -> None:
    assert provider_team_code(f"  {name.upper()}  ") == code


@pytest.mark.parametrize("name", [None, 123, "MTL", "Arizona Coyotes", "Unknown Team", "Utah Hockey Club"])
def test_unknown_names_do_not_guess_a_franchise(name: object) -> None:
    assert provider_team_code(name) is None


def test_matching_preserves_orientation_and_folds_accents() -> None:
    assert match_nhl_game({**EVENT, "home": "  MONTRÉAL   Canadiens "}, [GAME]) == (7, True)
    assert match_nhl_game({**EVENT, "home": EVENT["away"], "away": EVENT["home"]}, [GAME]) == (7, False)


@pytest.mark.parametrize("hours, matched", [(6, True), (-6, True), (6.001, False), (-6.001, False)])
def test_match_window(hours: float, matched: bool) -> None:
    game = {**GAME, "start_utc": START + timedelta(hours=hours)}
    assert (match_nhl_game(EVENT, [game]) is not None) == matched


def test_ambiguous_missing_and_identical_teams_are_rejected() -> None:
    assert match_nhl_game(EVENT, [GAME, {**GAME, "game_id": 8}]) is None
    assert match_nhl_game({**EVENT, "home": EVENT["away"]}, [GAME]) is None
    assert match_nhl_game({**EVENT, "home": "Unknown"}, [GAME]) is None
    for value in (None, "invalid", START.replace(tzinfo=None)):
        assert match_nhl_game(EVENT, [{**GAME, "start_utc": value}]) is None


@pytest.mark.parametrize("league", [None, "usa-nhl", {}, {"slug": "usa-ahl"}])
def test_other_leagues_never_match_nhl_games(league: object) -> None:
    assert match_nhl_game({**EVENT, "league": league}, [GAME]) is None


@pytest.mark.parametrize("value", [None, 123, "bad", "2026-10-24", "2026-10-24T00:00:00"])
def test_event_times_must_be_aware(value: object) -> None:
    assert event_start(value) is None
    assert match_nhl_game({**EVENT, "date": value}, [GAME]) is None


@pytest.mark.parametrize("book", ["Bet365", "DraftKings"])
def test_three_markets_are_paired_and_devigged_per_book(book: str) -> None:
    rows = {row.market: row for row in parse_nhl_game_markets(EVENT["bookmakers"][book], True)}
    assert set(rows) == {"moneyline", "spread", "total"}
    assert rows["moneyline"].line is None
    assert rows["spread"].line == -1.5
    assert rows["total"].first_side == "over"
    assert rows["total"].second_side == "under"
    for row in rows.values():
        assert row.first_market_prob + row.second_market_prob == pytest.approx(1)
        assert 0 < row.first_market_prob < 1
        assert row.raw_market["period"] == "full-game"
    if book == "Bet365":
        assert rows["moneyline"].first_odds == -167
        assert rows["moneyline"].second_odds == 139
        assert rows["moneyline"].first_market_prob == pytest.approx((1 / 1.60) / (1 / 1.60 + 1 / 2.39))
        assert rows["total"].line == 6.5


def test_reversal_swaps_team_prices_probabilities_and_spread_but_not_raw_or_totals() -> None:
    normal = parse_nhl_game_markets(EVENT["bookmakers"]["DraftKings"], True)
    flipped = parse_nhl_game_markets(EVENT["bookmakers"]["DraftKings"], False)
    for before, after in zip(normal, flipped, strict=True):
        assert before.raw_market == after.raw_market
        if before.market == "total":
            assert before == after
        else:
            assert after.first_odds == before.second_odds
            assert after.second_odds == before.first_odds
            assert after.first_market_prob == before.second_market_prob
    assert flipped[1].line == 1.5


@pytest.mark.parametrize("price", [None, 0, 1, -2, "bad", "nan", "inf", True, {}, "1e308"])
def test_invalid_prices_never_form_a_pair(price: object) -> None:
    assert parse_nhl_game_markets([{"name": "ML", "odds": [{"home": price, "away": "1.91"}]}], True) == []


@pytest.mark.parametrize("line", [None, "nan", "inf", 0, -6, True])
def test_total_requires_a_positive_finite_line(line: object) -> None:
    assert parse_nhl_game_markets([{"name": "Totals", "odds": [{"hdp": line, "over": "1.91", "under": "1.91"}]}], True) == []


def test_one_sided_rungs_never_combine_and_alternate_puck_lines_do_not_substitute() -> None:
    markets = [
        {"name": "ML", "odds": [{"home": "1.91"}, {"away": "1.91"}]},
        {"name": "Spread", "odds": [{"hdp": -2.5, "home": "1.91", "away": "1.91"}]},
    ]
    assert parse_nhl_game_markets(markets, True) == []


@pytest.mark.parametrize("metadata", [
    {"period": "1"}, {"segment": "regulation"}, {"scope": "60 minutes"},
    {"draw": "3.10"}, {"tie": None},
])
def test_draw_and_partial_game_metadata_are_rejected(metadata: dict[str, object]) -> None:
    market = {"name": "ML", "odds": [{"home": "1.91", "away": "1.91"}]}
    assert parse_nhl_game_markets([{**market, **metadata}], True) == []
    market["odds"][0].update(metadata)
    assert parse_nhl_game_markets([market], True) == []


def test_exact_market_allowlist_and_malformed_siblings() -> None:
    markets = [None, 5, {}, {"name": []}, {"name": "ML", "odds": "invalid"}]
    for name in ("Draw No Bet", "ML 1st Period", "Totals HT", "Team Totals", "Player Goals"):
        markets.append({"name": name, "odds": [{"home": "1.91", "away": "1.91"}]})
    assert parse_nhl_game_markets(markets, True) == []


def test_duplicates_cannot_silently_choose_conflicting_prices() -> None:
    market = EVENT["bookmakers"]["DraftKings"][0]
    assert len(parse_nhl_game_markets([market, copy.deepcopy(market)], True)) == 1
    conflict = copy.deepcopy(market)
    conflict["odds"][0]["home"] = "1.80"
    assert parse_nhl_game_markets([market, conflict, market], True) == []


def test_total_selection_uses_complete_valid_rungs_and_stable_ties() -> None:
    market = {"name": "Totals", "odds": [
        {"hdp": "nan", "over": "5", "under": "5"},
        {"hdp": 5.5, "over": "1.91"},
        {"hdp": 6.5, "over": "1.91", "under": "1.91"},
        {"hdp": 7.5, "over": "1.91", "under": "1.91"},
    ]}
    assert parse_nhl_game_markets([market], True)[0].line == 6.5


def test_fanduel_ladders_resolve_to_the_main_puck_line_and_total() -> None:
    rows = {row.market: row for row in parse_nhl_game_markets(EVENT["bookmakers"]["FanDuel"], True)}
    assert set(rows) == {"moneyline", "spread", "total"}  # the regulation 3-Way Result is not a moneyline
    assert (rows["moneyline"].first_odds, rows["moneyline"].second_odds) == (-102, -118)
    assert (rows["spread"].line, rows["spread"].first_odds, rows["spread"].second_odds) == (1.5, -260, 205)
    assert (rows["total"].line, rows["total"].first_odds, rows["total"].second_odds) == (5.5, -130, 106)
