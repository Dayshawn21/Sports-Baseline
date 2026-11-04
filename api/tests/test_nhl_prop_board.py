import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import nhl
from app.services.nhl.line_only_props import line_only_props
from app.services.nhl.prop_board import build_prop_board, prop_board_response

DAY = date(2026, 10, 23)
FETCH = datetime(2026, 10, 23, 12, tzinfo=UTC)


def _game(game_id: int, start: datetime | None = FETCH + timedelta(hours=8)) -> dict[str, object]:
    return {
        "game_id": game_id, "season": 2026, "week": 2, "game_type": "REG", "game_date": DAY,
        "start_utc": start, "status": "scheduled", "away_team": "TBL", "home_team": "CHI",
        "away_team_name": "Tampa Bay Lightning", "home_team_name": "Chicago Blackhawks",
        "away_score": None, "home_score": None, "end_period": None,
    }


def _line(game_id: int = 1, **overrides: object) -> dict[str, object]:
    return {
        "game_id": game_id, "provider": "prizepicks", "provider_prop_id": "offer-a", "player_id": 7,
        "player_name": "Player A", "position": "C", "team": "TB", "market": "shots_on_goal",
        "odds_type": "standard", "line": Decimal("2.5"), "fetched_at": FETCH, **overrides,
    }


def test_board_game_lines_equal_the_game_endpoints_lines() -> None:
    rows = [
        _line(provider_prop_id="b", player_name="Zed", market="points"),
        _line(provider_prop_id="a", odds_type="demon", line=Decimal("4.5")),
        _line(provider_prop_id="c", player_id=8, player_name="Amy", team="CHI"),
    ]
    board = prop_board_response(DAY, None, None, [_game(1)], {1: rows})
    assert board.games[0].lines == line_only_props(_game(1), rows).lines
    assert [line.market.value for line in board.games[0].lines][0] == "shots_on_goal"


def test_game_without_lines_is_empty_and_unknown_start_still_serves_lines() -> None:
    board = prop_board_response(DAY, None, None, [_game(1), _game(2, start=None)], {2: [_line(2)]})
    assert board.games[0].lines == []
    assert board.games[1].start_utc is None
    assert len(board.games[1].lines) == 1


def test_each_game_gets_only_its_own_lines() -> None:
    board = prop_board_response(DAY, None, None, [_game(1), _game(2)], {1: [_line(1)], 2: [_line(2, player_id=9)]})
    assert [[line.player_id for line in game.lines] for game in board.games] == [[7], [9]]


@pytest.mark.parametrize("games", [[], [_game(1)]])
def test_builder_reads_lines_once_and_skips_them_for_an_empty_date(
    monkeypatch: pytest.MonkeyPatch, games: list[dict[str, object]],
) -> None:
    monkeypatch.setattr(nhl, "get_game_dates", AsyncMock(return_value=[DAY]))
    monkeypatch.setattr(nhl, "get_games_on", AsyncMock(return_value=games))
    monkeypatch.setattr(nhl, "get_date_line_only_lines", AsyncMock(return_value={1: [_line(1)]}))
    db = cast(AsyncSession, object())
    board = asyncio.run(build_prop_board(db, DAY, DAY))
    assert board.date == DAY and len(board.games) == len(games)
    assert nhl.get_date_line_only_lines.await_count == len(games)
