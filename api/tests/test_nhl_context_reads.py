"""Execute NHL context selection SQL over isolated portable fixtures."""
from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from typing import cast

import pytest
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.core.nhl_context import NhlGoalieObservation, NhlInjuryEntry
from app.core.nhl_context_snapshots import GoalieSnapshot, InjurySnapshot
from app.repositories import nhl_context as repo

DAY = date(2026, 10, 24)
START = datetime(2026, 10, 24, 20, tzinfo=timezone.utc)
NOW = START - timedelta(hours=1)
FETCH = START - timedelta(hours=2)


def _value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat(" ")
    return value.isoformat() if isinstance(value, date) else value


class ContextSession:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.calls = 0

    async def execute(self, statement: TextClause, params: dict[str, object]) -> CursorResult:
        assert str(statement).strip().startswith("WITH"), "context reads must not mutate data"
        self.calls += 1
        return self.connection.execute(statement, {key: _value(value) for key, value in params.items()})

    def insert(self, table: str, values: dict[str, object]) -> None:
        self.connection.exec_driver_sql("PRAGMA query_only = OFF")
        self.connection.execute(text(f"INSERT INTO {table} ({', '.join(values)}) VALUES "
                                     f"({', '.join(':' + key for key in values)})"),
                                {key: _value(value) for key, value in values.items()})
        self.connection.exec_driver_sql("PRAGMA query_only = ON")


@contextmanager
def context_session() -> Iterator[ContextSession]:
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        for sql in (
            "CREATE TABLE sport_teams (id INTEGER, sport TEXT, team_code TEXT)",
            """CREATE TABLE sport_games (id INTEGER, sport TEXT, game_type TEXT, game_date TEXT,
                start_utc TEXT, away_team_id INTEGER, home_team_id INTEGER)""",
            """CREATE TABLE nhl_context_snapshots (id INTEGER, source TEXT, kind TEXT, scope_date TEXT,
                fetched_at TEXT, source_timestamp TEXT, entry_count INTEGER)""",
            """CREATE TABLE nhl_player_injuries (snapshot_id INTEGER, espn_team_id TEXT, team_code TEXT,
                espn_athlete_id TEXT, player_name TEXT, status TEXT, detail TEXT, source_updated_at TEXT,
                return_date TEXT, athlete_team_id TEXT, player_id INTEGER, link_reason TEXT)""",
            """CREATE TABLE nhl_goalie_observations (snapshot_id INTEGER, espn_event_id TEXT, event_date TEXT,
                start_utc TEXT, time_valid BOOLEAN, home_team TEXT, away_team TEXT, espn_team_id TEXT,
                team_code TEXT, espn_athlete_id TEXT, player_name TEXT, status TEXT, raw_status TEXT,
                athlete_team_id TEXT, source_position TEXT, player_id INTEGER, player_link_reason TEXT,
                game_id INTEGER, game_link_reason TEXT)""",
        ):
            connection.execute(text(sql))
        session = ContextSession(connection)
        for row in [(1, "nhl", "TBL"), (2, "nhl", "CHI"), (3, "nba", "CHI")]:
            session.insert("sport_teams", dict(zip(("id", "sport", "team_code"), row)))
        for game_id, sport, kind, home, start in [
            (1, "nhl", "REG", 2, START), (2, "nhl", "PST", 2, START),
            (3, "nba", "REG", 2, START), (4, "nhl", "PRE", 2, START),
            (5, "nhl", "REG", 3, START), (6, "nhl", "REG", 2, None),
        ]:
            session.insert("sport_games", {"id": game_id, "sport": sport, "game_type": kind,
                                          "game_date": DAY, "start_utc": start, "away_team_id": 1, "home_team_id": home})
        yield session
    engine.dispose()


@pytest.fixture
def session() -> Iterator[ContextSession]:
    with context_session() as value:
        yield value


def batch(session: ContextSession, snapshot_id: int, kind: str = "injuries", fetched: datetime = FETCH,
          **overrides: object) -> None:
    session.insert("nhl_context_snapshots", {"id": snapshot_id, "source": "ESPN", "kind": kind,
                                           "scope_date": DAY if kind == "goalies" else None,
                                           "fetched_at": fetched, "source_timestamp": fetched,
                                           "entry_count": 0, **overrides})


def injury(session: ContextSession, snapshot_id: int, **overrides: object) -> None:
    entry = NhlInjuryEntry("20", "TBL", "123", "Source injury name", "Out", "Ankle", FETCH, None, "20")
    session.insert("nhl_player_injuries", {"snapshot_id": snapshot_id, **asdict(entry),
                                         "player_id": None, "link_reason": "no_candidate", **overrides})


def goalies(session: ContextSession, snapshot_id: int, *, game_id: int = 1, event: str = "555",
            status: str = "confirmed", source_start: datetime = START) -> None:
    for team_id, team in [("20", "TBL"), ("4", "CHI")]:
        row = NhlGoalieObservation(event, DAY, source_start, True, "CHI", "TBL", team_id, team,
                                  team_id + "123", team + " source goalie", "confirmed", "Confirmed", team_id, "G")
        if status == "not_reported":
            row = replace(row, espn_athlete_id=None, player_name=None, status="not_reported",
                          raw_status=None, athlete_team_id=None, source_position=None)
        session.insert("nhl_goalie_observations", {"snapshot_id": snapshot_id, **asdict(row),
                                                   "player_id": None,
                                                   "player_link_reason": "not_reported" if status == "not_reported" else "no_candidate",
                                                   "game_id": game_id, "game_link_reason": "matched"})


def read(
    session: ContextSession, kind: str, ids: list[int] | None = None, as_of: datetime = NOW,
) -> dict[int, InjurySnapshot] | dict[int, GoalieSnapshot]:
    reader = repo.get_injury_snapshots if kind == "injuries" else repo.get_goalie_snapshots
    return asyncio.run(reader(cast(AsyncSession, session), ids if ids is not None else [1], as_of))


@pytest.mark.parametrize("kind", ["injuries", "goalies"])
@pytest.mark.parametrize("fetched", [START, START + timedelta(seconds=1), NOW + timedelta(seconds=1)])
def test_strict_start_and_response_clock_cutoffs(session: ContextSession, kind: str, fetched: datetime) -> None:
    batch(session, 1, kind, fetched)
    assert read(session, kind) == {}


@pytest.mark.parametrize("kind", ["injuries", "goalies"])
def test_response_clock_inclusive_and_historical_context_is_pre_start(session: ContextSession, kind: str) -> None:
    batch(session, 1, kind, NOW)
    batch(session, 2, kind, START)
    assert read(session, kind)[1].fetched_at == NOW
    assert read(session, kind, as_of=START + timedelta(days=10))[1].fetched_at == NOW


@pytest.mark.parametrize("kind", ["injuries", "goalies"])
def test_empty_success_is_selected_instead_of_previous_entries(session: ContextSession, kind: str) -> None:
    batch(session, 1, kind)
    injury(session, 1) if kind == "injuries" else goalies(session, 1)
    batch(session, 2, kind, FETCH + timedelta(minutes=30))
    selected = read(session, kind)[1]
    assert selected.fetched_at == FETCH + timedelta(minutes=30)
    assert (selected.injuries if kind == "injuries" else selected.observations) == ()


def test_latest_goalie_batch_is_selected_before_event_and_no_older_starter_returns(session: ContextSession) -> None:
    batch(session, 1, "goalies")
    goalies(session, 1)
    batch(session, 2, "goalies", FETCH + timedelta(minutes=30))
    goalies(session, 2, game_id=2)
    assert read(session, "goalies")[1].observations == ()


@pytest.mark.parametrize("kind", ["injuries", "goalies"])
def test_timestamp_ties_use_header_id_before_reading_entries(session: ContextSession, kind: str) -> None:
    batch(session, 1, kind)
    injury(session, 1) if kind == "injuries" else goalies(session, 1)
    batch(session, 2, kind)
    assert (read(session, kind)[1].injuries if kind == "injuries" else read(session, kind)[1].observations) == ()


def test_wrong_source_kind_scope_and_sport_cannot_contribute(session: ContextSession) -> None:
    batch(session, 1, "injuries", source="other")
    batch(session, 2, "goalies", scope_date=DAY - timedelta(days=1))
    assert read(session, "injuries", [1, 2, 3, 4, 5, 6, 999]) == {}
    assert read(session, "goalies", [1, 2, 3, 4, 5, 6, 999]) == {}
    batch(session, 3)
    assert set(read(session, "injuries", [1, 2, 3, 4, 5, 6, 999])) == {1, 2}


def test_frozen_links_and_source_teams_do_not_read_current_players(session: ContextSession) -> None:
    batch(session, 1)
    injury(session, 1, player_id=777, link_reason="matched")
    injury(session, 1, team_code="BOS", espn_athlete_id="999")
    snapshot = read(session, "injuries")[1]
    assert len(snapshot.injuries) == 1
    assert snapshot.injuries[0].player.player_id == 777
    assert snapshot.injuries[0].entry.team_code == "TBL"
    # No sport_players table exists in this fixture; a current-roster join would fail.


def test_not_reported_goalie_rows_survive_with_null_source_player(session: ContextSession) -> None:
    batch(session, 1, "goalies")
    goalies(session, 1, status="not_reported")
    rows = read(session, "goalies")[1].observations
    assert len(rows) == 2 and all(row.observation.status == "not_reported" for row in rows)
    assert all(row.observation.player_name is None for row in rows)


def test_feeds_are_independent_and_use_two_queries_for_a_whole_slate(session: ContextSession) -> None:
    batch(session, 1)
    batch(session, 2, "goalies", FETCH + timedelta(minutes=20))
    assert read(session, "injuries", [1, 2])[1].fetched_at == FETCH
    assert read(session, "goalies", [1, 2])[1].fetched_at == FETCH + timedelta(minutes=20)
    assert session.calls == 2


def test_empty_ids_skip_sql_and_naive_clock_is_rejected(session: ContextSession) -> None:
    assert read(session, "injuries", []) == {} and read(session, "goalies", []) == {}
    assert session.calls == 0
    with pytest.raises(ValueError, match="timezone-aware"):
        read(session, "injuries", as_of=NOW.replace(tzinfo=None))
