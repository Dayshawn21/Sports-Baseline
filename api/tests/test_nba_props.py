import datetime as dt

from app.core.nba_line_only import LINE_ONLY_COLUMNS
from app.core.nba_projection_backtest import NbaHistoryRow
from app.services.nba.props import props_response

UTC = dt.timezone.utc
FETCHED = dt.datetime(2026, 10, 20, 15, 0, tzinfo=UTC)
START = dt.date(2025, 10, 21)


def _line(player_id: int, name: str, market: str, line: float, odds_type: str = "standard") -> dict[str, object]:
    return {"player_id": player_id, "player_name": name, "position": "G", "team": "NYK", "market": market,
            "odds_type": odds_type, "line": line, "fetched_at": FETCHED}


def _prior(player_id: int, games: int, minutes: float = 32.0, **stats: int) -> list[NbaHistoryRow]:
    values: dict[str, int | bool | None] = {column: 1 for column in LINE_ONLY_COLUMNS}
    values.update({"points": 20, "rebounds": 6, "assists": 5, "did_not_play": False, **stats})
    return [
        NbaHistoryRow(player_id=player_id, game_id=day, season=2025, game_date=START + dt.timedelta(days=day),
                      game_type="REG", did_not_play=False, minutes=minutes, stats=values)
        for day in range(games)
    ]


def _box(player_id: int, day: int, **stats: int) -> dict[str, object]:
    base: dict[str, object] = {column: 0 for column in LINE_ONLY_COLUMNS}
    return {**base, **stats, "player_id": player_id, "game_date": dt.date(2026, 4, day), "opponent": "BOS",
            "did_not_play": False}


def test_lines_order_by_market_then_player_then_line() -> None:
    lines = [_line(2, "Zed", "points", 20.5), _line(1, "Amy", "assists", 4.5),
             _line(1, "Amy", "points", 25.5, "demon"), _line(1, "Amy", "points", 18.5, "goblin")]
    response = props_response(21320, lines, {1: _prior(1, 20), 2: _prior(2, 20)}, [])
    assert [(line.market, line.player_name, line.line) for line in response.lines] == [
        ("points", "Amy", 18.5), ("points", "Amy", 25.5), ("points", "Zed", 20.5), ("assists", "Amy", 4.5)]
    assert response.model_version == "nba-reference-v1"
    assert {line.team for line in response.lines} == {"NY"}


def test_an_eligible_line_carries_the_projection_block() -> None:
    response = props_response(21320, [_line(1, "Amy", "assists", 4.5), _line(1, "Amy", "points", 18.5)],
                              {1: _prior(1, 20)}, [])
    points, assists = response.lines
    assert (points.projection, points.gap, points.games_in_sample, points.prior_minutes) == (20.0, 1.5, 20, 32.0)
    assert points.p_over is None and points.flags == ["no_over_probability"]
    assert assists.projection == 5.0 and assists.p_over is not None
    assert assists.over_probability_version == "nba-pover-v1" and assists.flags == []


def test_an_ineligible_or_unknown_player_gets_no_projection() -> None:
    response = props_response(
        21320, [_line(1, "Amy", "points", 18.5), _line(2, "Bea", "points", 9.5), _line(3, "Cat", "points", 5.5)],
        {1: _prior(1, 9), 2: _prior(2, 15, minutes=12.0)}, [])
    amy, bea, cat = response.lines
    assert (amy.projection, amy.gap, amy.flags) == (None, None, ["few_prior_games"])
    assert (bea.projection, bea.prior_minutes, bea.flags) == (None, 12.0, ["low_minutes"])
    assert (cat.projection, cat.games_in_sample, cat.flags) == (None, 0, ["few_prior_games"])


def test_recent_values_are_the_players_settled_market_newest_first() -> None:
    rows = [_box(1, 12, points=30, assists=4), _box(1, 10, points=12, assists=9), _box(2, 11, points=40)]
    response = props_response(21320, [_line(1, "Amy", "points_assists", 30.5)], {1: _prior(1, 20)}, rows)
    assert [(str(game.game_date), game.opponent, game.value) for game in response.lines[0].recent] == [
        ("2026-04-12", "BOS", 34.0), ("2026-04-10", "BOS", 21.0)]


def test_response_serializes_camel_case() -> None:
    payload = props_response(21320, [_line(1, "Amy", "assists", 4.5)], {1: _prior(1, 20)}, []).model_dump(by_alias=True)
    assert {"gameId", "modelVersion", "lines"} == payload.keys()
    assert {"playerId", "gamesInSample", "priorMinutes", "pOver", "pUnder", "overProbabilityVersion", "flags",
            "recent", "gap", "projection", "fetchedAt"} <= payload["lines"][0].keys()


def test_no_lines_is_an_empty_list() -> None:
    assert props_response(17568, [], {}, []).lines == []
