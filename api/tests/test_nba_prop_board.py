import asyncio
import datetime as dt
from typing import cast
from unittest.mock import AsyncMock, Mock, call

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_line_only import LINE_ONLY_COLUMNS
from app.core.nba_projection_backtest import NbaHistoryRow
from app.repositories import nba as nba_repo
from app.repositories import nba_injuries as injury_repo
from app.services.nba.line_only_props import line_only_props
from app.services.nba.prop_board import build_prop_board, prop_board_response
from app.services.nba.props import props_response

DATE = dt.date(2026, 10, 20)
PREVIOUS = DATE - dt.timedelta(days=1)
NEXT = DATE + dt.timedelta(days=2)
FETCHED = dt.datetime(2026, 10, 20, 15, tzinfo=dt.UTC)


def _game(game_id: int, status: str = "scheduled", start: dt.datetime | None = FETCHED) -> dict[str, object]:
    return {"game_id": game_id, "away_team": "NY", "home_team": "BOS", "start_utc": start,
            "status": status, "season": 2026, "game_date": DATE}


def _line(player_id: int, name: str, market: str, line: float, odds_type: str = "standard") -> dict[str, object]:
    return {"player_id": player_id, "player_name": name, "position": "G", "team": "NYK",
            "market": market, "odds_type": odds_type, "line": line, "fetched_at": FETCHED}


def _prior() -> list[NbaHistoryRow]:
    return [
        NbaHistoryRow(player_id=1, game_id=day, season=2025, game_date=dt.date(2026, 4, day), game_type="REG",
                      did_not_play=False, minutes=32.0, stats={"points": 20, "rebounds": 6, "assists": 5})
        for day in range(1, 21)
    ]


def _box(player_id: int, points: int | None) -> dict[str, object]:
    return {**{column: 0 for column in LINE_ONLY_COLUMNS}, "player_id": player_id, "points": points,
            "rebounds": 10, "assists": 5, "game_date": dt.date(2026, 4, 20), "opponent": "BOS",
            "did_not_play": False}


def test_board_lines_match_game_page_builders_for_each_game() -> None:
    games = [_game(20, "completed"), _game(10)]
    modelled = {
        20: [_line(2, "Zed", "points", 20.5), _line(1, "Amy", "assists", 4.5),
             _line(1, "Amy", "points", 25.5, "demon"), _line(1, "Amy", "points", 18.5, "goblin")],
        10: [_line(3, "Bea", "rebounds", 8.5)],
    }
    line_only = {20: [_line(2, "Zed", "double_double", 0.5), _line(1, "Amy", "double_double", 0.5)],
                 10: [_line(3, "Bea", "double_double", 0.5)]}
    prior = {1: _prior()}
    recent = [_box(1, 20), _box(2, None), _box(3, 10)]

    response = prop_board_response(DATE, PREVIOUS, NEXT, games, modelled, line_only, prior, recent)

    for game in response.games:
        assert game.lines == props_response(game.game_id, modelled[game.game_id], prior, recent).lines
        assert game.line_only_lines == line_only_props(game.game_id, line_only[game.game_id], recent).lines
    assert [(line.player_name, line.line) for line in response.games[0].lines] == [
        ("Amy", 18.5), ("Amy", 25.5), ("Zed", 20.5), ("Amy", 4.5)]
    assert response.games[0].lines[-1].p_over is not None
    assert response.games[0].line_only_lines[1].recent[0].value is None
    assert response.games[1].lines[0].projection is None


def test_board_preserves_game_order_status_and_nullable_start() -> None:
    games = [_game(20, "completed"), _game(10, "postponed", None), _game(30, "canceled")]

    response = prop_board_response(DATE, PREVIOUS, NEXT, games, {}, {}, {}, [])

    assert [game.game_id for game in response.games] == [20, 10, 30]
    assert [game.status for game in response.games] == ["completed", "postponed", "canceled"]
    assert response.games[1].start_utc is None
    assert all(game.away_team == "NY" and game.home_team == "BOS" for game in response.games)
    assert all(game.lines == [] and game.line_only_lines == [] for game in response.games)


def test_board_keeps_each_line_kind_when_the_other_is_absent() -> None:
    response = prop_board_response(
        DATE, None, None, [_game(10), _game(20)], {10: [_line(1, "Amy", "points", 18.5)]},
        {20: [_line(2, "Zed", "double_double", 0.5)]}, {}, [],
    )

    assert len(response.games[0].lines) == 1 and response.games[0].line_only_lines == []
    assert response.games[1].lines == [] and len(response.games[1].line_only_lines) == 1


def test_empty_board_preserves_date_navigation_and_version() -> None:
    payload = prop_board_response(DATE, PREVIOUS, NEXT, [], {}, {}, {}, []).model_dump(mode="json", by_alias=True)

    assert payload == {"date": "2026-10-20", "previousDate": "2026-10-19", "nextDate": "2026-10-22",
                       "modelVersion": "nba-reference-v1", "games": []}


def test_board_serializes_game_and_line_fields_in_camel_case() -> None:
    response = prop_board_response(
        DATE, None, None, [_game(10)], {10: [_line(1, "Amy", "assists", 4.5)]},
        {10: [_line(1, "Amy", "double_double", 0.5)]}, {}, [],
    )
    payload = response.model_dump(mode="json", by_alias=True)

    assert payload["previousDate"] is None and payload["nextDate"] is None
    assert payload["modelVersion"] == "nba-reference-v1"
    game = payload["games"][0]
    assert game.keys() == {"gameId", "awayTeam", "homeTeam", "startUtc", "status", "lines", "lineOnlyLines",
                           "injuryReport", "teamStats"}
    assert game["startUtc"] == "2026-10-20T15:00:00Z"
    assert {"playerId", "playerName", "fetchedAt", "gamesInSample", "pOver"} <= game["lines"][0].keys()
    assert {"playerId", "playerName", "fetchedAt", "recent"} <= game["lineOnlyLines"][0].keys()


def _repository(monkeypatch: pytest.MonkeyPatch, **results: object) -> Mock:
    repository = Mock()
    monkeypatch.setattr(injury_repo, "get_game_snapshots", AsyncMock(return_value={}))
    results.setdefault("get_team_box_games", [])
    for name, result in results.items():
        reader = AsyncMock(return_value=result)
        repository.attach_mock(reader, name)
        monkeypatch.setattr(nba_repo, name, reader)
    return repository


def test_service_reads_date_lines_then_all_players_once(monkeypatch: pytest.MonkeyPatch) -> None:
    modelled = {20: [_line(2, "Zed", "points", 20.5), _line(1, "Amy", "assists", 4.5)],
                10: [_line(1, "Amy", "points", 18.5)]}
    line_only = {10: [_line(3, "Bea", "double_double", 0.5)]}
    prior, recent = {1: _prior()}, [_box(1, 20), _box(3, 10)]
    games = [_game(20), _game(10)]
    repository = _repository(
        monkeypatch, get_game_dates=[PREVIOUS, DATE, NEXT], get_games_on=games,
        get_date_modelled_lines=modelled, get_date_line_only_lines=line_only,
        get_prior_games=prior, get_recent_box_scores=recent,
    )
    db = cast(AsyncSession, object())

    response = asyncio.run(build_prop_board(db, None, DATE))

    assert repository.mock_calls == [
        call.get_game_dates(db), call.get_games_on(db, DATE), call.get_date_modelled_lines(db, DATE),
        call.get_date_line_only_lines(db, DATE), call.get_prior_games(db, [1, 2, 3], DATE),
        call.get_recent_box_scores(db, [1, 2, 3], DATE),
        call.get_team_box_games(db, 2026, DATE),
    ]
    expected = prop_board_response(DATE, PREVIOUS, NEXT, games, modelled, line_only, prior, recent)
    assert [game.model_dump(exclude={"team_stats"}) for game in response.games] == [
        game.model_dump(exclude={"team_stats"}) for game in expected.games
    ]
    assert all(game.team_stats is not None and game.team_stats.before_date == DATE for game in response.games)


@pytest.mark.parametrize(("requested", "today", "resolved", "previous", "following", "has_games"), [
    (None, NEXT - dt.timedelta(days=1), NEXT, DATE, None, True),
    (NEXT - dt.timedelta(days=1), DATE, NEXT - dt.timedelta(days=1), DATE, NEXT, False),
    (None, NEXT + dt.timedelta(days=1), NEXT, DATE, None, True),
])
def test_service_resolves_navigation_and_skips_player_reads_without_lines(
    monkeypatch: pytest.MonkeyPatch, requested: dt.date | None, today: dt.date, resolved: dt.date,
    previous: dt.date | None, following: dt.date | None, has_games: bool,
) -> None:
    games = [{**_game(10), "game_date": resolved}] if has_games else []
    repository = _repository(
        monkeypatch, get_game_dates=[PREVIOUS, DATE, NEXT], get_games_on=games,
        get_date_modelled_lines={}, get_date_line_only_lines={},
        get_prior_games={}, get_recent_box_scores=[],
    )
    db = cast(AsyncSession, object())

    response = asyncio.run(build_prop_board(db, requested, today))

    assert repository.mock_calls == [
        call.get_game_dates(db), call.get_games_on(db, resolved), call.get_date_modelled_lines(db, resolved),
        call.get_date_line_only_lines(db, resolved),
    ] + ([call.get_team_box_games(db, 2026, resolved)] if has_games else [])
    assert response.date == resolved and response.previous_date == previous and response.next_date == following
    assert all(game.lines == [] and game.line_only_lines == [] and game.team_stats is not None for game in response.games)
