import asyncio
import datetime as dt
from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nhl_projection_backtest import NhlHistoryRow
from app.core.nhl_prop_predictions import NhlFreezeLine
from app.core.prop_predictions import freeze_rows
from app.nhl.markets import NhlLineOnlyMarket
from app.repositories import nhl
from app.schemas.nhl_context import NhlGameContextSchema, NhlGoalieContext, NhlGoalieSide, NhlInjuryContext
from app.services.nhl import prop_predictions as service
from app.services.nhl.projections import ProjectionInputs, line_projection

NOW = dt.datetime(2026, 10, 24, 17, 0, tzinfo=dt.UTC)
FETCHED = dt.datetime(2026, 10, 24, 16, 59, tzinfo=dt.UTC)
SKATER, GOALIE = 7, 20
DAY_ONE, DAY_TWO = dt.date(2026, 10, 24), dt.date(2026, 10, 26)
DB = cast(AsyncSession, object())


def _game(game_id: int, game_date: dt.date, start: dt.datetime) -> dict[str, object]:
    return {
        "game_id": game_id, "game_date": game_date, "season": 2026, "week": 3, "game_type": "REG",
        "start_utc": start, "status": "scheduled", "away_team": "TBL", "home_team": "CHI",
        "away_team_name": "Tampa Bay Lightning", "home_team_name": "Chicago Blackhawks",
        "away_score": None, "home_score": None, "end_period": None,
    }


def _line(
    line_id: int, game_id: int, game_date: dt.date, start: dt.datetime, player_id: int, market: str, line: float,
) -> NhlFreezeLine:
    return NhlFreezeLine(
        line_id=line_id, game_id=game_id, game_date=game_date, start_utc=start, player_id=player_id, team="TBL",
        position="G" if player_id == GOALIE else "C", market=market, odds_type="standard", line=line,
        fetched_at=FETCHED,
    )


def _skater_rows(shots: int, count: int = 12) -> list[NhlHistoryRow]:
    stats = {"shots": shots, "time_on_ice_seconds": 1200}
    return [
        NhlHistoryRow(SKATER, i, 2026, dt.date(2026, 10, 1) + dt.timedelta(days=i), "REG", "C", False, True, stats)
        for i in range(count)
    ]


def _goalie_rows() -> list[NhlHistoryRow]:
    stats = {"saves": 26, "goals_against": 2, "time_on_ice_seconds": 3600}
    return [
        NhlHistoryRow(GOALIE, 50 + i, 2026, dt.date(2026, 10, 1) + dt.timedelta(days=i), "REG", "G", True, True, stats)
        for i in range(6)
    ]


def _context(status: str = "confirmed") -> NhlGameContextSchema:
    return NhlGameContextSchema(
        injuries=NhlInjuryContext(fetched_at=FETCHED, freshness="fresh"),
        goalies=NhlGoalieContext(
            fetched_at=FETCHED, freshness="fresh",
            away=NhlGoalieSide(team="TBL", player_id=GOALIE, status=status),
            home=NhlGoalieSide(team="CHI", status="not_reported"),
        ),
    )


def _patch(
    monkeypatch: pytest.MonkeyPatch, lines: list[NhlFreezeLine], games: list[dict[str, object]],
    history: dict[dt.date, dict[int, list[NhlHistoryRow]]], contexts: AsyncMock,
) -> None:
    monkeypatch.setattr(nhl, "get_week_freeze_lines", AsyncMock(return_value=lines))
    monkeypatch.setattr(nhl, "get_week_games", AsyncMock(return_value=games))
    monkeypatch.setattr(nhl, "get_prior_history", AsyncMock(side_effect=lambda db, ids, before: history[before]))
    monkeypatch.setattr(service, "load_contexts", contexts)


def test_a_started_game_is_skipped_and_an_upcoming_one_is_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    started, upcoming = NOW - dt.timedelta(hours=1), NOW + dt.timedelta(hours=6)
    lines = [
        _line(1, 1, DAY_ONE, started, SKATER, "shots_on_goal", 2.5),
        _line(2, 2, DAY_ONE, upcoming, SKATER, "shots_on_goal", 2.5),
    ]
    _patch(monkeypatch, lines, [_game(1, DAY_ONE, started), _game(2, DAY_ONE, upcoming)],
           {DAY_ONE: {SKATER: _skater_rows(3)}}, AsyncMock(return_value={}))

    rows, counts = freeze_rows(asyncio.run(service.week_freezable_games(DB, 2026, 3, NOW)), NOW)

    assert [row.prop_line_id for row in rows] == [2]
    assert counts["kicked_off"] == 1 and counts["frozen"] == 1


def test_each_game_reads_only_the_games_before_its_own_date(monkeypatch: pytest.MonkeyPatch) -> None:
    start_one, start_two = NOW + dt.timedelta(hours=6), NOW + dt.timedelta(days=2, hours=6)
    lines = [
        _line(1, 1, DAY_ONE, start_one, SKATER, "shots_on_goal", 2.5),
        _line(2, 2, DAY_TWO, start_two, SKATER, "shots_on_goal", 2.5),
    ]
    history = {DAY_ONE: {SKATER: _skater_rows(2)}, DAY_TWO: {SKATER: _skater_rows(5)}}
    _patch(monkeypatch, lines, [_game(1, DAY_ONE, start_one), _game(2, DAY_TWO, start_two)], history,
           AsyncMock(return_value={}))

    rows, _ = freeze_rows(asyncio.run(service.week_freezable_games(DB, 2026, 3, NOW)), NOW)

    assert [row.projection for row in rows] == [2.0, 5.0]
    assert nhl.get_prior_history.await_count == 2


def test_a_failed_context_read_freezes_goalies_unreported_and_skaters_ungated(monkeypatch: pytest.MonkeyPatch) -> None:
    start = NOW + dt.timedelta(hours=6)
    lines = [
        _line(1, 1, DAY_ONE, start, SKATER, "shots_on_goal", 2.5),
        _line(2, 1, DAY_ONE, start, GOALIE, "goalie_saves", 24.5),
    ]
    _patch(monkeypatch, lines, [_game(1, DAY_ONE, start)],
           {DAY_ONE: {SKATER: _skater_rows(3), GOALIE: _goalie_rows()}}, AsyncMock(side_effect=HTTPException(503)))

    skater, goalie = freeze_rows(asyncio.run(service.week_freezable_games(DB, 2026, 3, NOW)), NOW)[0]

    assert skater.projection == 3.0 and skater.quality_flags == [] and skater.p_over is not None
    assert goalie.projection is None and goalie.quality_flags == ["no_goalie_report"]


@pytest.mark.parametrize(("market", "player_id", "value"), [
    ("shots_on_goal", SKATER, 2.5), ("shots_on_goal", SKATER, 3.0), ("hits", SKATER, 1.5), ("goalie_saves", GOALIE, 24.5),
])
def test_a_frozen_row_is_what_the_board_service_returns_for_the_line(
    monkeypatch: pytest.MonkeyPatch, market: str, player_id: int, value: float,
) -> None:
    start = NOW + dt.timedelta(hours=6)
    history = {SKATER: _skater_rows(3), GOALIE: _goalie_rows()}
    _patch(monkeypatch, [_line(1, 1, DAY_ONE, start, player_id, market, value)], [_game(1, DAY_ONE, start)],
           {DAY_ONE: history}, AsyncMock(return_value={1: _context()}))

    row = freeze_rows(asyncio.run(service.week_freezable_games(DB, 2026, 3, NOW)), NOW)[0][0]
    served = line_projection(
        NhlLineOnlyMarket(market), player_id, value, "G" if player_id == GOALIE else "C", "TBL",
        ProjectionInputs(history, _context()),
    )

    assert (row.model_version, row.projection, row.feature_snapshot["gap"], row.quality_flags) == (
        served.model_version, served.value, served.gap, served.flags,
    )
    expected = None if row.p_over is None else round(row.p_over, 4)
    assert expected == served.p_over
