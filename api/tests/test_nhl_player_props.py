import asyncio
import datetime as dt
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import nhl
from app.repositories import nhl_context as context_repo
from app.schemas.nhl_context import (
    NhlGameContextSchema, NhlGoalieContext, NhlGoalieSide, NhlInjuryContext, NhlInjurySchema,
)
from app.services.nhl.player_props import build_player_props, player_props_response

D = dt.date
FETCHED = dt.datetime(2026, 11, 2, 15, tzinfo=dt.timezone.utc)
PLAYER = {"player_id": 7, "name": "Test Skater", "position": "C"}
GAME = {
    "game_id": 90, "game_type": "REG", "away_team": "BOS", "home_team": "TBL",
    "start_utc": dt.datetime(2026, 11, 2, 23, tzinfo=dt.timezone.utc), "status": "scheduled",
}


def line(market: str, value: float, odds_type: str = "standard", team: str | None = "TB") -> dict[str, object]:
    return {"market": market, "line": value, "odds_type": odds_type, "fetched_at": FETCHED, "team": team}


def row(day: int, opponent: str | None = "BOS", **stats: int | None) -> dict[str, object]:
    return {"game_date": D(2026, 10, day), "opponent": opponent, **stats}


def injury(player_id: int | None) -> NhlInjurySchema:
    return NhlInjurySchema(
        espn_athlete_id="1", player_id=player_id, player_name="X", team="TBL", status="Out", detail=None,
        source_updated_at=None, return_date=None, link_reason="matched", team_mismatch=False,
    )


def context(injuries: list[NhlInjurySchema]) -> NhlGameContextSchema:
    return NhlGameContextSchema(
        injuries=NhlInjuryContext(fetched_at=FETCHED, freshness="fresh", home=injuries),
        goalies=NhlGoalieContext(away=NhlGoalieSide(team="BOS"), home=NhlGoalieSide(team="TBL")),
    )


def test_markets_and_rungs_come_in_market_then_line_order() -> None:
    lines = [
        line("points", 1.5, "demon"), line("shots_on_goal", 3.5), line("points", 0.5, "goblin"),
        line("points", 1.5), line("goals", 0.5),
    ]
    response = player_props_response(PLAYER, D(2026, 11, 2), GAME, lines, [], [], context([]))
    assert [m.market for m in response.markets] == ["shots_on_goal", "points", "goals"]
    points = response.markets[1]
    assert [(r.line, r.odds_type) for r in points.lines] == [(0.5, "goblin"), (1.5, "standard"), (1.5, "demon")]


def test_goalie_markets_read_goalie_columns() -> None:
    lines = [line("goalie_saves", 25.5), line("goals_allowed", 2.5)]
    rows = [row(30, saves=31, goals_against=2), row(28, saves=22, goals_against=4)]
    response = player_props_response(PLAYER, D(2026, 11, 2), GAME, lines, rows, [], None)
    saves, allowed = response.markets
    assert [g.value for g in saves.recent] == [31.0, 22.0]
    assert [g.value for g in allowed.recent] == [2.0, 4.0]


def test_a_null_stat_is_null_not_zero_and_time_is_minutes() -> None:
    lines = [line("hits", 1.5), line("time_on_ice", 18.5)]
    rows = [row(30, hits=None, time_on_ice_seconds=1200), row(28, hits=0, time_on_ice_seconds=None)]
    hits, toi = player_props_response(PLAYER, D(2026, 11, 2), GAME, lines, rows, [], None).markets
    assert [g.value for g in hits.recent] == [None, 0.0]
    assert [g.value for g in toi.recent] == [20.0, None]


def test_recent_is_capped_at_ten_newest_first_and_last_five_is_a_prefix() -> None:
    rows = [row(day, points=day % 3) for day in range(1, 16)]
    market = player_props_response(PLAYER, D(2026, 11, 2), GAME, [line("points", 0.5)], rows, [], None).markets[0]
    dates = [g.game_date for g in market.recent]
    assert len(dates) == 10
    assert dates == sorted(dates, reverse=True) and dates[0] == D(2026, 10, 15)
    assert [g.value for g in market.recent[:5]] == [float(g.game_date.day % 3) for g in market.recent[:5]]


def test_opponent_comes_from_the_other_side_and_carries_games() -> None:
    against = [row(3, points=1), row(1, points=2)]
    response = player_props_response(PLAYER, D(2026, 11, 2), GAME, [line("points", 0.5)], [], against, None)
    assert (response.team, response.opponent) == ("TBL", "BOS")
    assert [g.game_date for g in response.markets[0].opponent_games] == [D(2026, 10, 3), D(2026, 10, 1)]


def test_a_team_matching_neither_side_has_no_opponent_and_no_opponent_games() -> None:
    against = [row(3, points=1)]
    response = player_props_response(PLAYER, D(2026, 11, 2), GAME, [line("points", 0.5, team="NYR")], [], against, None)
    assert (response.team, response.opponent) == (None, None)
    assert response.markets[0].opponent_games == []


def test_no_game_or_no_lines_is_an_empty_page() -> None:
    for game, lines in ((None, [line("points", 0.5)]), (GAME, [])):
        response = player_props_response(PLAYER, D(2026, 11, 2), game, lines, [], [], context([injury(7)]))
        assert response.game is None and response.markets == [] and response.goalies is None
        assert response.injury.entry is None


def test_the_players_injury_is_found_by_player_id_only() -> None:
    lines = [line("points", 0.5)]
    mine, other = injury(7), injury(8)
    found = player_props_response(PLAYER, D(2026, 11, 2), GAME, lines, [], [], context([other, mine]))
    assert found.injury.entry == mine and found.injury.freshness == "fresh"
    absent = player_props_response(PLAYER, D(2026, 11, 2), GAME, lines, [], [], context([other]))
    assert absent.injury.entry is None and absent.injury.freshness == "fresh"
    assert absent.goalies is not None and absent.goalies.home.team == "TBL"


TODAY = D(2026, 11, 2)
DB = cast(AsyncSession, object())


def _mock_repository(monkeypatch: pytest.MonkeyPatch, *, lines: list[dict[str, object]], dates: list[dt.date]) -> None:
    monkeypatch.setattr(context_repo, "get_injury_snapshots", AsyncMock(return_value={}))
    monkeypatch.setattr(context_repo, "get_goalie_snapshots", AsyncMock(return_value={}))
    full_game = {
        **GAME, "season": 2026, "week": 5, "game_date": TODAY, "away_team_name": "Boston",
        "home_team_name": "Tampa Bay", "away_score": None, "home_score": None, "end_period": None,
    }
    for name, result in {
        "get_player": PLAYER, "get_game_dates": [TODAY], "get_player_line_dates": dates,
        "get_player_lines": lines, "get_game": full_game, "get_latest_market_rows": [], "get_line_movement": [],
        "get_prop_line_counts": {90: 1}, "get_player_played_games": [row(30, points=1)],
    }.items():
        monkeypatch.setattr(nhl, name, AsyncMock(return_value=result))


def test_service_composes_reads_and_asks_for_the_opponent_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_repository(monkeypatch, lines=[{**line("points", 0.5), "game_id": 90}], dates=[TODAY])
    response = asyncio.run(build_player_props(DB, 7, None, TODAY))
    assert response is not None and response.game is not None and response.opponent == "BOS"
    assert response.goalies is not None and response.goalies.home.team == "TBL"
    calls = nhl.get_player_played_games.await_args_list
    assert [call.kwargs.get("opponent") for call in calls] == [None, "BOS"]
    assert calls[0].kwargs["limit"] == 10 and calls[0].kwargs["goalie"] is False
    assert calls[0].kwargs["before"] == TODAY and calls[0].kwargs["first_season"] == 2023


def test_service_reads_goalie_games_for_goalie_markets(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_repository(monkeypatch, lines=[{**line("goalie_saves", 24.5), "game_id": 90}], dates=[TODAY])
    asyncio.run(build_player_props(DB, 7, None, TODAY))
    assert all(call.kwargs["goalie"] is True for call in nhl.get_player_played_games.await_args_list)


def test_service_skips_the_opponent_read_when_the_team_matches_neither_side(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_repository(monkeypatch, lines=[{**line("points", 0.5, team="NYR"), "game_id": 90}], dates=[TODAY])
    response = asyncio.run(build_player_props(DB, 7, None, TODAY))
    assert response is not None and response.opponent is None
    assert nhl.get_player_played_games.await_count == 1


def test_unknown_player_is_none_and_reads_nothing_else(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_repository(monkeypatch, lines=[], dates=[])
    monkeypatch.setattr(nhl, "get_player", AsyncMock(return_value=None))
    assert asyncio.run(build_player_props(DB, 7, None, TODAY)) is None
    nhl.get_player_lines.assert_not_awaited()


def test_a_named_date_with_no_lines_is_an_empty_page(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_repository(monkeypatch, lines=[], dates=[TODAY])
    response = asyncio.run(build_player_props(DB, 7, D(2026, 11, 9), TODAY))
    assert response is not None and response.date == D(2026, 11, 9)
    assert response.game is None and response.markets == []
    nhl.get_player_played_games.assert_not_awaited()
