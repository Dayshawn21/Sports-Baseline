import asyncio
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, call, patch

from app.services.nfl.other_markets import RECENT_GAMES, build_other_markets, build_player_other_markets, opponent_code

FETCHED = datetime(2026, 10, 25, 16, tzinfo=UTC)


def _line(market: str, line: float, odds_type: str | None = "standard", game_id: int = 91) -> dict:
    return {"market": market, "odds_type": odds_type, "line": line, "fetched_at": FETCHED, "game_id": game_id}


def _row(season: int, week: int, opponent: str | None = "LV", **stats: int | None) -> dict:
    columns = {"passing_tds": 0, "interceptions": 0, "rushing_yards": 0, "receiving_yards": 0, "passing_yards": 0,
               "touchdowns": 0, "fg_made": 0, "pat_made": 0, "punts": 0}
    return {"season": season, "week": week, "game_date": date(season, 9, week), "opponent": opponent, **columns, **stats}


def test_one_market_keeps_every_rung_in_line_order_with_the_games_behind_it() -> None:
    lines = [_line("passing_touchdowns", 2.5, "demon"), _line("passing_touchdowns", 1.5), _line("passing_touchdowns", 0.5, "goblin")]
    recent = [_row(2026, 6, passing_tds=3), _row(2026, 7, passing_tds=1)]

    result = build_other_markets(7, 2026, 8, "BUF", lines, recent, [])

    [market] = result.markets
    assert [(rung.line, rung.odds_type) for rung in market.lines] == [(0.5, "goblin"), (1.5, "standard"), (2.5, "demon")]
    assert market.game_id == 91
    assert [(game.week, game.value) for game in market.recent] == [(7, 1.0), (6, 3.0)]


def test_a_kicker_reads_field_goals_and_kicking_points_from_the_same_rows() -> None:
    lines = [_line("kicking_points", 7.5), _line("field_goals_made", 1.5)]
    recent = [_row(2026, 7, fg_made=2, pat_made=3)]

    result = build_other_markets(8, 2026, 8, None, lines, recent, [])

    assert [market.market for market in result.markets] == ["field_goals_made", "kicking_points"]
    assert [market.recent[0].value for market in result.markets] == [2.0, 9.0]


def test_a_punter_reads_punts() -> None:
    result = build_other_markets(9, 2026, 8, None, [_line("punts", 4.5)], [_row(2026, 7, punts=5)], [])

    assert [game.value for game in result.markets[0].recent] == [5.0]


def test_a_stat_that_was_not_loaded_is_null_not_zero() -> None:
    result = build_other_markets(8, 2026, 8, None, [_line("kicking_points", 7.5)], [_row(2026, 7, fg_made=None, pat_made=2)], [])

    assert result.markets[0].recent[0].value is None


def test_a_team_matching_neither_side_has_no_opponent_and_no_opponent_games() -> None:
    assert opponent_code("TB", "BUF", "CHI") is None
    result = build_other_markets(7, 2026, 8, opponent_code("TB", "BUF", "CHI"), [_line("interceptions", 0.5)], [_row(2026, 7)], [_row(2025, 3)])

    assert result.opponent is None
    assert result.markets[0].opponent_games == []


def test_opponent_code_is_the_other_side_of_the_game() -> None:
    assert [opponent_code("BUF", "BUF", "CHI"), opponent_code("CHI", "BUF", "CHI")] == ["CHI", "BUF"]


def test_a_player_with_no_earlier_games_has_empty_history() -> None:
    result = build_other_markets(7, 2026, 1, "CHI", [_line("passing_touchdowns", 1.5)], [], [])

    assert (result.markets[0].recent, result.markets[0].opponent_games) == ([], [])


def test_games_are_newest_first_with_their_dates_and_recent_stops_at_ten() -> None:
    recent = [_row(2025, week, passing_tds=week) for week in range(1, 13)]
    meetings = [_row(2024, 3, "CHI", passing_tds=2), _row(2025, 9, "CHI", passing_tds=1)]

    result = build_other_markets(7, 2026, 8, "CHI", [_line("passing_touchdowns", 1.5)], recent, meetings)

    market = result.markets[0]
    assert len(market.recent) == RECENT_GAMES
    assert [game.week for game in market.recent] == list(range(12, 2, -1))
    assert market.recent[0].game_date == date(2025, 9, 12)
    assert [(game.season, game.week, game.value) for game in market.opponent_games] == [(2025, 9, 1.0), (2024, 3, 2.0)]


def test_the_response_serializes_in_camel_case() -> None:
    body = build_other_markets(7, 2026, 8, "CHI", [_line("punts", 3.5)], [_row(2026, 7, punts=4)], []).model_dump(by_alias=True)

    assert set(body) == {"playerId", "season", "week", "opponent", "markets"}
    assert set(body["markets"][0]) == {"market", "gameId", "lines", "recent", "opponentGames"}
    assert set(body["markets"][0]["recent"][0]) == {"season", "week", "gameDate", "opponent", "value"}


def _repo_lines(team: str = "BUF") -> list[dict]:
    return [_line("passing_touchdowns", 1.5) | {"team": team, "home_team": "BUF", "away_team": "CHI"}]


def _service(repo_overrides: dict):
    with patch("app.services.nfl.other_markets.nfl_repo") as repo:
        repo.player_exists = AsyncMock(return_value=True)
        repo.get_player_week_line_only_lines = AsyncMock(return_value=[])
        repo.get_player_line_only_history = AsyncMock(return_value=[])
        for name, value in repo_overrides.items():
            setattr(repo, name, value)
        result = asyncio.run(build_player_other_markets(None, 7, 2026, 8))  # type: ignore[arg-type]
        return result, repo


def test_an_unknown_player_is_none_and_reads_nothing_else() -> None:
    result, repo = _service({"player_exists": AsyncMock(return_value=False)})

    assert result is None
    repo.get_player_week_line_only_lines.assert_not_awaited()


def test_a_player_with_no_line_only_lines_gets_an_empty_list_and_no_history_reads() -> None:
    result, repo = _service({})

    assert result is not None and (result.markets, result.opponent) == ([], None)
    repo.get_player_line_only_history.assert_not_awaited()


def test_history_is_read_before_the_week_and_again_for_the_opponent() -> None:
    history = AsyncMock(side_effect=[[_row(2026, 7, passing_tds=2)], [_row(2025, 9, "CHI", passing_tds=1)]])
    result, repo = _service({"get_player_week_line_only_lines": AsyncMock(return_value=_repo_lines()), "get_player_line_only_history": history})

    assert result is not None and result.opponent == "CHI"
    assert repo.get_player_line_only_history.await_args_list == [
        call(None, 7, 2026, 8, limit=10), call(None, 7, 2026, 8, opponent="CHI"),
    ]
    assert [game.value for game in result.markets[0].opponent_games] == [1.0]


def test_a_team_matching_neither_side_skips_the_opponent_read() -> None:
    result, repo = _service({"get_player_week_line_only_lines": AsyncMock(return_value=_repo_lines("TB"))})

    assert result is not None and result.opponent is None
    assert repo.get_player_line_only_history.await_count == 1
