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
from app.services.nba.player_props import OPPONENT_GAMES_LIMIT, player_props_response
from app.services.nba.player_props_service import build_player_props
from app.services.nba.props import props_response

UTC = dt.timezone.utc
FETCHED = dt.datetime(2026, 10, 20, 15, 0, tzinfo=UTC)
START = dt.date(2025, 10, 21)
DATE = dt.date(2026, 4, 20)
PLAYER = {"player_id": 1, "name": "Amy", "position": "G", "team": "NY"}
GAME = {"game_id": 7, "away_team": "BOS", "home_team": "NY", "start_utc": FETCHED, "status": "scheduled"}


def _line(market: str, line: float, odds_type: str = "standard", team: str | None = "NYK") -> dict[str, object]:
    return {"player_id": 1, "player_name": "Amy", "position": "G", "team": team, "market": market,
            "odds_type": odds_type, "line": line, "fetched_at": FETCHED}


def _prior(games: int = 20) -> list[NbaHistoryRow]:
    values: dict[str, int | bool | None] = {column: 1 for column in LINE_ONLY_COLUMNS}
    values.update({"points": 20, "rebounds": 6, "assists": 5, "did_not_play": False})
    return [
        NbaHistoryRow(player_id=1, game_id=day, season=2025, game_date=START + dt.timedelta(days=day),
                      game_type="REG", did_not_play=False, minutes=32.0, stats=values)
        for day in range(games)
    ]


def _box(day: int, **stats: int | None) -> dict[str, object]:
    base: dict[str, object] = {column: 0 for column in LINE_ONLY_COLUMNS}
    return {**base, **stats, "player_id": 1, "game_date": dt.date(2026, 4, day), "opponent": "BOS",
            "did_not_play": False}


def _build(modelled: list[dict[str, object]], line_only: list[dict[str, object]] | None = None,
           recent: list[dict[str, object]] | None = None, opponent: list[dict[str, object]] | None = None,
           game: dict[str, object] | None = GAME, player: dict[str, object] = PLAYER):
    return player_props_response(player, DATE, game, modelled, line_only or [], {1: _prior()},
                                 recent or [], opponent or [])


def test_a_modelled_market_matches_props_response_rung_for_rung() -> None:
    lines = [_line("assists", 4.5), _line("assists", 6.0, "demon"), _line("assists", 3.5, "goblin")]
    recent = [_box(day, assists=day) for day in (19, 18, 17)]
    expected = props_response(7, lines, {1: _prior()}, recent).lines
    (market,) = _build(lines, recent=recent).markets
    by_line = {line.line: line for line in expected}
    assert market.kind == "modelled" and [rung.line for rung in market.lines] == [3.5, 4.5, 6.0]
    assert market.projection == expected[0].projection and market.games_in_sample == expected[0].games_in_sample
    for rung in market.lines:
        source = by_line[rung.line]
        assert (rung.gap, rung.p_over, rung.p_under, rung.flags) == (source.gap, source.p_over, source.p_under, source.flags)
        assert rung.over_probability_version == source.over_probability_version


def test_flags_belong_to_the_rung_not_the_market() -> None:
    (market,) = _build([_line("assists", 4.5), _line("assists", 5.0, "demon")]).markets
    half, whole = market.lines
    assert half.flags == [] and whole.flags == ["integer_line"] and whole.p_over is None


def test_a_double_double_market_has_no_model_fields() -> None:
    (market,) = _build([], [_line("double_double", 0.5)]).markets
    rung = market.lines[0]
    assert market.kind == "line-only" and market.projection is None and market.games_in_sample is None
    assert (rung.gap, rung.p_over, rung.p_under, rung.over_probability_version, rung.flags) == (None, None, None, None, [])


def test_markets_are_in_nba_order_with_modelled_first() -> None:
    response = _build([_line("assists", 4.5), _line("points", 18.5)], [_line("double_double", 0.5)])
    assert [market.market for market in response.markets] == ["points", "assists", "double_double"]


def test_a_stat_not_loaded_is_null_never_zero() -> None:
    recent = [_box(19, assists=None), _box(18, assists=4)]
    (market,) = _build([_line("assists", 4.5)], recent=recent).markets
    assert [game.value for game in market.recent] == [None, 4.0]


def test_last_five_is_the_front_of_recent_and_recent_is_capped_at_ten() -> None:
    recent = [_box(day, assists=day) for day in range(19, 4, -1)]
    (market,) = _build([_line("assists", 4.5)], recent=recent).markets
    board = props_response(7, [_line("assists", 4.5)], {1: _prior()}, recent).lines[0].recent
    assert len(market.recent) == 10
    assert [(g.game_date, g.value) for g in market.recent[:5]] == [(r.game_date, r.value) for r in board[:5]]


def test_opponent_games_use_the_markets_stat_and_are_capped() -> None:
    rows = [_box(day % 28 + 1, points=day) for day in range(30)]
    response = _build([_line("points", 18.5), _line("assists", 4.5)], opponent=rows)
    points, assists = response.markets
    assert response.opponent == "BOS"
    assert len(points.opponent_games) == OPPONENT_GAMES_LIMIT and points.opponent_games[1].value == 1.0
    assert assists.opponent_games[0].value == 0.0


def test_a_team_on_neither_side_has_no_opponent_and_no_opponent_games() -> None:
    response = _build([_line("points", 18.5, team="LAL")], opponent=[_box(3, points=9)])
    assert response.opponent is None and response.markets[0].opponent_games == []


def test_a_player_with_no_game_is_an_empty_response() -> None:
    response = _build([], game=None)
    assert response.game is None and response.markets == [] and response.opponent is None
    assert response.team == "NY" and response.name == "Amy"


def test_the_team_falls_back_to_the_stored_player_team_without_a_provider_team() -> None:
    response = _build([_line("points", 18.5, team=None)])
    assert response.team == "NY" and response.opponent == "BOS"


def test_serializes_camel_case() -> None:
    dumped = _build([_line("points", 18.5)]).model_dump(by_alias=True)
    assert {"playerId", "modelVersion", "injuryReport", "teamStats", "markets"} <= set(dumped)
    assert {"gamesInSample", "opponentGames", "lines", "recent"} <= set(dumped["markets"][0])


def _service_repository(monkeypatch: pytest.MonkeyPatch, **results: object) -> Mock:
    repository = Mock()
    monkeypatch.setattr(injury_repo, "get_game_snapshots", AsyncMock(return_value={}))
    results.setdefault("get_team_box_games", [])
    for name, result in results.items():
        reader = AsyncMock(return_value=result)
        repository.attach_mock(reader, name)
        monkeypatch.setattr(nba_repo, name, reader)
    return repository


def _served_game() -> dict[str, object]:
    return {**GAME, "season": 2026, "game_date": DATE}


def test_service_reads_only_this_players_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    modelled = [{**_line("assists", 4.5), "game_id": 7}]
    line_only = [{**_line("double_double", 0.5), "game_id": 7}]
    opponent = [_box(3, assists=2)]
    repository = _service_repository(
        monkeypatch, get_player=PLAYER, get_game_dates=[DATE], get_player_date_modelled_lines=modelled,
        get_player_date_line_only_lines=line_only, get_games_on=[_served_game()],
        get_prior_games={1: _prior()}, get_recent_box_scores=[_box(19, assists=4)],
        get_player_games_against=opponent,
    )
    db = cast(AsyncSession, object())

    response = asyncio.run(build_player_props(db, 1, None, DATE))

    assert response is not None and response.opponent == "BOS" and response.team == "NY"
    assert [market.market for market in response.markets] == ["assists", "double_double"]
    assert response.markets[0].opponent_games[0].value == 2.0
    assert repository.mock_calls == [
        call.get_player(db, 1), call.get_game_dates(db), call.get_player_date_modelled_lines(db, 1, DATE),
        call.get_player_date_line_only_lines(db, 1, DATE), call.get_games_on(db, DATE),
        call.get_prior_games(db, [1], DATE), call.get_recent_box_scores(db, [1], DATE, limit=10),
        call.get_player_games_against(db, 1, "BOS", DATE, 20), call.get_team_box_games(db, 2026, DATE),
    ]


def test_service_returns_none_for_an_unknown_player(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = _service_repository(monkeypatch, get_player=None)
    db = cast(AsyncSession, object())

    assert asyncio.run(build_player_props(db, 9, None, DATE)) is None
    assert repository.mock_calls == [call.get_player(db, 9)]


def test_service_gives_empty_markets_for_a_date_without_a_line(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = _service_repository(
        monkeypatch, get_player=PLAYER, get_game_dates=[DATE], get_player_date_modelled_lines=[],
        get_player_date_line_only_lines=[],
    )
    db = cast(AsyncSession, object())

    response = asyncio.run(build_player_props(db, 1, DATE, DATE))

    assert response is not None and response.game is None and response.markets == [] and response.date == DATE
    assert repository.mock_calls == [
        call.get_player(db, 1), call.get_game_dates(db), call.get_player_date_modelled_lines(db, 1, DATE),
        call.get_player_date_line_only_lines(db, 1, DATE),
    ]
