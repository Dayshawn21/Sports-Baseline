import asyncio
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch

from app.services.nfl.line_only_props import build_line_only_props, line_only_props

FETCHED = datetime(2026, 10, 5, 18, tzinfo=UTC)
GAME = {"game_id": 64, "season": 2026, "week": 4, "game_date": date(2026, 10, 5),
        "start_utc": datetime(2026, 10, 6, 0, 15, tzinfo=UTC), "away_team": "ATL", "home_team": "NO", "status": "scheduled"}


def _line(player_id: int, name: str, market: str, line: float, odds_type: str = "standard") -> dict:
    return {"player_id": player_id, "player_name": name, "position": "K", "team": "NO", "market": market,
            "odds_type": odds_type, "line": line, "fetched_at": FETCHED}


def _stats(player_id: int, week: int, fg: int | None, pat: int | None) -> dict:
    return {"player_id": player_id, "season": 2026, "week": week, "opponent": "LV", "fg_made": fg, "pat_made": pat}


def test_kicking_points_come_out_as_three_per_field_goal_plus_extra_points() -> None:
    props = line_only_props(64, [_line(7, "Kicker", "kicking_points", 7.5)], [_stats(7, 3, 2, 3), _stats(7, 2, None, 1)])

    [line] = props.lines
    assert [(item.week, item.value) for item in line.recent] == [(3, 9.0), (2, None)]


def test_lines_are_ordered_by_market_then_player_and_keep_their_own_history() -> None:
    lines = [_line(8, "Zed", "field_goals_made", 1.5), _line(7, "Abe", "kicking_points", 7.5),
             _line(7, "Abe", "field_goals_made", 2.5, "demon")]
    props = line_only_props(64, lines, [_stats(7, 3, 1, 2)])

    assert [(line.market, line.player_name) for line in props.lines] == [
        ("field_goals_made", "Abe"), ("field_goals_made", "Zed"), ("kicking_points", "Abe"),
    ]
    assert [line.recent for line in props.lines if line.player_name == "Zed"] == [[]]


def test_the_response_serializes_in_camel_case() -> None:
    body = line_only_props(64, [_line(7, "Kicker", "punts", 3.5)], []).model_dump(by_alias=True)
    assert body["gameId"] == 64
    assert body["lines"][0]["playerName"] == "Kicker" and body["lines"][0]["oddsType"] == "standard"


def test_an_unknown_game_is_none_and_reads_nothing_else() -> None:
    with patch("app.services.nfl.line_only_props.nfl_repo") as repo:
        repo.get_game = AsyncMock(return_value=None)
        repo.get_line_only_lines = AsyncMock()
        assert asyncio.run(build_line_only_props(None, 999)) is None  # type: ignore[arg-type]
        repo.get_line_only_lines.assert_not_awaited()


def test_a_game_without_lines_skips_the_stats_query() -> None:
    with patch("app.services.nfl.line_only_props.nfl_repo") as repo:
        repo.get_game = AsyncMock(return_value=GAME)
        repo.get_line_only_lines = AsyncMock(return_value=[])
        repo.get_recent_stat_rows = AsyncMock()
        props = asyncio.run(build_line_only_props(None, 64))  # type: ignore[arg-type]
        assert props is not None and props.lines == []
        repo.get_recent_stat_rows.assert_not_awaited()


def test_recent_stats_are_read_before_the_games_own_week() -> None:
    with patch("app.services.nfl.line_only_props.nfl_repo") as repo:
        repo.get_game = AsyncMock(return_value=GAME)
        repo.get_line_only_lines = AsyncMock(return_value=[_line(7, "Kicker", "punts", 3.5)])
        repo.get_recent_stat_rows = AsyncMock(return_value=[])
        asyncio.run(build_line_only_props(None, 64))  # type: ignore[arg-type]
        repo.get_recent_stat_rows.assert_awaited_once_with(None, [7], 2026, 4)
