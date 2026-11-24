import asyncio
import re
from datetime import UTC, date, datetime
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.ingest.nhl_api import NhlGame
from app.repositories.nhl import upsert_games


class _Result:
    def __init__(self, rows: list[tuple[str, int]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[str, int]]:
        return self.rows


class _RecordingSession:
    def __init__(self) -> None:
        self.statements: list[str] = []

    async def execute(self, statement: TextClause, params: object = None) -> _Result:
        self.statements.append(str(statement))
        return _Result([("2025020001", 41)])


GAME = NhlGame(
    game_id="2025020001", season=2025, week=1, game_type="REG", game_date=date(2025, 10, 7),
    start_utc=datetime(2025, 10, 7, 23, 0, tzinfo=UTC), home_team="TOR", home_team_name="Toronto",
    away_team="MTL", away_team_name="Montreal", home_score=None, away_score=None, status="scheduled",
    end_period=None,
)


def _conflict_clause() -> str:
    session = _RecordingSession()
    ids = asyncio.run(upsert_games(cast(AsyncSession, session), [GAME], {"TOR": 1, "MTL": 2}))
    assert ids == {"2025020001": 41}
    return session.statements[0].split("ON CONFLICT", 1)[1]


def test_a_conflict_keeps_a_known_start_time() -> None:
    assert "start_utc = COALESCE(EXCLUDED.start_utc, sport_games.start_utc)" in _conflict_clause()


def test_a_conflict_never_changes_the_season() -> None:
    assert re.search(r"\bseason\s*=", _conflict_clause()) is None


def test_a_conflict_still_refreshes_status_and_end_period() -> None:
    clause = _conflict_clause()
    assert "status = EXCLUDED.status" in clause
    assert "end_period = EXCLUDED.end_period" in clause
