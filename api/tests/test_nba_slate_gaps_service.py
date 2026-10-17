import datetime as dt

from app.core.nba_line_only import LINE_ONLY_COLUMNS
from app.core.nba_projection_backtest import NbaHistoryRow
from app.services.nba.props import props_response
from app.services.nba.slate_gaps import _not_tipped, slate_gaps_response

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 20, 18, 0, tzinfo=UTC)
DATE = dt.date(2026, 10, 20)
FETCHED = dt.datetime(2026, 10, 20, 15, 0, tzinfo=UTC)


def _game(game_id: int, hours: float = 5, status: str = "scheduled") -> dict[str, object]:
    return {"game_id": game_id, "start_utc": NOW + dt.timedelta(hours=hours), "status": status,
            "away_team": "BOS", "home_team": "NY"}


def _line(player_id: int, name: str, market: str, line: float, odds_type: str = "standard") -> dict[str, object]:
    return {"player_id": player_id, "player_name": name, "position": "G", "team": "NYK", "market": market,
            "odds_type": odds_type, "line": line, "fetched_at": FETCHED}


def _prior(player_id: int, points: int, assists: int = 5) -> list[NbaHistoryRow]:
    values: dict[str, int | bool | None] = {column: 1 for column in LINE_ONLY_COLUMNS}
    values.update({"points": points, "rebounds": 6, "assists": assists, "did_not_play": False})
    return [
        NbaHistoryRow(player_id=player_id, game_id=day, season=2025, game_date=dt.date(2025, 10, 21) + dt.timedelta(days=day),
                      game_type="REG", did_not_play=False, minutes=32.0, stats=values)
        for day in range(20)
    ]


LINES = {
    1: [_line(1, "Amy", "points", 18.5), _line(1, "Amy", "assists", 3.5), _line(2, "Bea", "points", 25.5, "goblin")],
    2: [_line(3, "Cat", "points", 9.5), _line(4, "Dee", "points", 30.5)],
}
PRIOR = {1: _prior(1, 20, assists=6), 2: _prior(2, 30), 3: _prior(3, 12), 4: _prior(4, 26)}


def test_each_item_matches_the_game_page_props_line() -> None:
    response = slate_gaps_response(DATE, [_game(1), _game(2)], LINES, PRIOR, NOW)
    assert response.items
    for item in response.items:
        page = props_response(item.game_id, LINES[item.game_id], PRIOR, []).lines
        served = next(line for line in page if line.player_id == item.player_id and line.market == item.market)
        assert (item.line, item.projection, item.gap) == (served.line, served.projection, served.gap)


def test_items_rank_by_gap_share_one_per_player_and_skip_goblins() -> None:
    response = slate_gaps_response(DATE, [_game(1), _game(2)], LINES, PRIOR, NOW)
    assert [(item.player_name, item.market) for item in response.items] == [
        ("Amy", "assists"), ("Cat", "points"), ("Dee", "points")]
    assert response.items[0].gap_share == 2.5 / 3.5
    assert (response.items[0].away_team, response.items[0].home_team) == ("BOS", "NY")
    assert response.model_version == "nba-reference-v1"


def test_a_tipped_or_unscheduled_game_contributes_nothing() -> None:
    response = slate_gaps_response(DATE, [_game(1, hours=-1), _game(2, status="postponed")], LINES, PRIOR, NOW)
    assert response.items == []
    assert not _not_tipped(_game(1, hours=-1), NOW)
    assert not _not_tipped({**_game(1), "start_utc": None}, NOW)
    assert _not_tipped(_game(1), NOW)


def test_no_games_gives_an_empty_digest_in_camel_case() -> None:
    payload = slate_gaps_response(DATE, [], {}, {}, NOW).model_dump(by_alias=True, mode="json")
    assert payload == {"date": "2026-10-20", "modelVersion": "nba-reference-v1", "items": []}
