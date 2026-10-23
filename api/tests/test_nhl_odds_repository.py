import asyncio
import json
from datetime import UTC, datetime, timedelta, timezone
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.core.nhl_odds import parse_nhl_game_markets
from app.repositories.nhl import get_upcoming_games, insert_game_odds_snapshot

NOW = datetime(2026, 10, 23, 20, tzinfo=UTC)


class _Result:
    def __init__(self, rows: list[dict[str, object]], result_id: int | None) -> None:
        self.rows = rows
        self.result_id = result_id

    def mappings(self) -> list[dict[str, object]]:
        return self.rows

    def scalar_one_or_none(self) -> int | None:
        return self.result_id


class _RecordingSession:
    def __init__(self, rows: list[dict[str, object]] | None = None, result_id: int | None = None) -> None:
        self.rows = rows or []
        self.result_id = result_id
        self.statement = ""
        self.params: dict[str, object] = {}

    async def execute(self, statement: TextClause, params: dict[str, object]) -> _Result:
        self.statement = " ".join(str(statement).split())
        self.params = params
        return _Result(self.rows, self.result_id)


def test_upcoming_games_use_aware_utc_bounds_and_nhl_scheduled_reg_pst_only() -> None:
    rows = [{"game_id": 7, "start_utc": NOW + timedelta(hours=4), "home_team": "MTL", "away_team": "CHI"}]
    session = _RecordingSession(rows)
    local_now = NOW.astimezone(timezone(timedelta(hours=-5)))

    assert asyncio.run(get_upcoming_games(cast(AsyncSession, session), now=local_now)) == rows

    assert session.params == {"now": NOW, "until": NOW + timedelta(days=2)}
    assert session.params["now"].tzinfo is UTC
    for guard in (
        "g.sport = 'nhl'", "home.sport = 'nhl'", "away.sport = 'nhl'",
        "g.game_type IN ('REG', 'PST')", "g.status = 'scheduled'",
        "g.start_utc > :now", "g.start_utc <= :until", "ORDER BY g.start_utc, g.id",
    ):
        assert guard in session.statement


@pytest.mark.parametrize("days", [0, -1, 15, True, 1.5])
def test_invalid_window_fails_before_querying(days: int) -> None:
    session = _RecordingSession()
    with pytest.raises(ValueError, match="days_ahead"):
        asyncio.run(get_upcoming_games(cast(AsyncSession, session), days, now=NOW))
    assert session.statement == ""


def test_naive_reference_fails_before_querying() -> None:
    session = _RecordingSession()
    with pytest.raises(ValueError, match="timezone-aware"):
        asyncio.run(get_upcoming_games(cast(AsyncSession, session), now=NOW.replace(tzinfo=None)))
    assert session.statement == ""


@pytest.mark.parametrize("days", [1, 14])
def test_window_boundaries_and_empty_results(days: int) -> None:
    session = _RecordingSession()
    assert asyncio.run(get_upcoming_games(cast(AsyncSession, session), days, now=NOW)) == []
    assert session.params["until"] == NOW + timedelta(days=days)


@pytest.mark.parametrize("name, rung", [
    ("ML", {"home": "1.60", "away": "2.39"}),
    ("Spread", {"hdp": -1.5, "home": "2.50", "away": "1.60"}),
    ("Totals", {"hdp": 6.5, "over": "1.91", "under": "1.91"}),
])
def test_insert_preserves_parsed_shape_and_raw_provider_orientation(name: str, rung: dict[str, object]) -> None:
    market = parse_nhl_game_markets([{"name": name, "odds": [rung]}], False)[0]
    session = _RecordingSession(result_id=501)

    assert asyncio.run(insert_game_odds_snapshot(
        cast(AsyncSession, session), 7, "bet365", market, event_id=1001,
    )) == 501

    assert session.params == {
        "game_id": 7, "book": "bet365", "market": market.market, "line": market.line,
        "first_side": market.first_side, "second_side": market.second_side,
        "first_odds": market.first_odds, "second_odds": market.second_odds,
        "first_market_prob": market.first_market_prob, "second_market_prob": market.second_market_prob,
        "raw_json": json.dumps({**market.raw_market, "event_id": 1001}, allow_nan=False),
    }
    assert "SELECT 'nhl', g.id, 'odds_api_io'" in session.statement
    assert "g.id = :game_id AND g.sport = 'nhl'" in session.statement
    assert "g.game_type IN ('REG', 'PST') AND g.status = 'scheduled'" in session.statement
    assert "g.start_utc > statement_timestamp()" in session.statement
    assert "CAST(:raw_json AS jsonb), statement_timestamp()" in session.statement
    assert "UPDATE" not in session.statement and "DELETE" not in session.statement
    assert "event_id" not in market.raw_market


def test_ineligible_game_returns_none_without_an_inserted_id() -> None:
    market = parse_nhl_game_markets([{"name": "ML", "odds": [{"home": "1.60", "away": "2.39"}]}], True)[0]
    session = _RecordingSession()
    assert asyncio.run(insert_game_odds_snapshot(
        cast(AsyncSession, session), 999, "draftkings", market, event_id=1001,
    )) is None


@pytest.mark.parametrize("book", ["pinnacle", "Bet365", "", "draft_kings"])
def test_unconfigured_books_cannot_write(book: str) -> None:
    market = parse_nhl_game_markets([{"name": "ML", "odds": [{"home": "1.60", "away": "2.39"}]}], True)[0]
    session = _RecordingSession()
    with pytest.raises(ValueError, match="book"):
        asyncio.run(insert_game_odds_snapshot(cast(AsyncSession, session), 7, book, market, event_id=1001))
    assert session.statement == ""
