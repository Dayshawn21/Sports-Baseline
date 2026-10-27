"""Execute the display reads over fixed data using portable SQL window functions."""
import asyncio
import json
from collections.abc import Iterator
from datetime import date
from typing import cast

import pytest
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.repositories import nhl

DAY = "2026-10-23"
OPEN = "2026-10-23T12:00:00+00:00"
LATE = "2026-10-23T15:00:00+00:00"
START = "2026-10-23T20:00:00+00:00"


class _Session:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.calls = 0

    async def execute(self, statement: TextClause, params: dict[str, object] | None = None) -> CursorResult:
        self.calls += 1
        return self.connection.execute(statement, params or {})


@pytest.fixture
def session() -> Iterator[_Session]:
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        for statement in (
            "CREATE TABLE sport_teams (id INTEGER, sport TEXT, team_code TEXT, name TEXT)",
            """CREATE TABLE sport_games (id INTEGER, sport TEXT, season INTEGER, week INTEGER,
                game_type TEXT, game_date TEXT, start_utc TEXT, status TEXT, away_score INTEGER,
                home_score INTEGER, end_period TEXT, away_team_id INTEGER, home_team_id INTEGER)""",
            """CREATE TABLE sport_game_odds (id INTEGER, sport TEXT, provider TEXT, game_id INTEGER,
                book TEXT, market TEXT, line NUMERIC, first_side TEXT, first_odds INTEGER,
                second_odds INTEGER, first_market_prob NUMERIC, fetched_at TEXT)""",
            "CREATE TABLE sport_players (id INTEGER, sport TEXT, name TEXT, position TEXT)",
            """CREATE TABLE sport_prop_lines (id INTEGER, sport TEXT, provider TEXT, provider_prop_id TEXT,
                game_id INTEGER, player_id INTEGER, segment TEXT, market TEXT, odds_type TEXT,
                line NUMERIC, fetched_at TEXT, raw_json TEXT)""",
        ):
            connection.execute(text(statement))
        for team in (dict(id=1, sport="nhl", team_code="MTL", name="Montreal"),
                     dict(id=2, sport="nhl", team_code="CHI", name="Chicago"),
                     dict(id=3, sport="nba", team_code="CHI", name="Bulls")):
            _insert(connection, "sport_teams", team)
        for player in (dict(id=7, sport="nhl", name="Player A", position="C"),
                       dict(id=8, sport="nba", name="Wrong Sport", position="C")):
            _insert(connection, "sport_players", player)
        for game_id, overrides in (
            (1, {}), (2, {"game_type": "PST"}), (3, {"sport": "nba"}),
            (4, {"game_type": "PRE"}), (5, {"home_team_id": 3}),
            (6, {"start_utc": None}), (7, {"status": "completed", "end_period": "SO",
                                       "away_score": 3, "home_score": 2}),
        ):
            _insert(connection, "sport_games", {
                "id": game_id, "sport": "nhl", "season": 2026, "week": 1, "game_type": "REG",
                "game_date": DAY, "start_utc": START, "status": "scheduled", "away_score": None,
                "home_score": None, "end_period": None, "away_team_id": 1, "home_team_id": 2, **overrides,
            })
        yield _Session(connection)
    engine.dispose()


def _insert(connection: Connection, table: str, row: dict[str, object]) -> None:
    connection.execute(text(
        f"INSERT INTO {table} ({', '.join(row)}) VALUES ({', '.join(':' + key for key in row)})"
    ), row)


def _odds(session: _Session, row_id: int, **overrides: object) -> None:
    _insert(session.connection, "sport_game_odds", {
        "id": row_id, "sport": "nhl", "provider": "odds_api_io", "game_id": 1,
        "book": "draftkings", "market": "spread", "line": -1.5, "first_side": "home",
        "first_odds": -110, "second_odds": 100, "first_market_prob": 0.52,
        "fetched_at": OPEN, **overrides,
    })


def _prop(session: _Session, row_id: int, **overrides: object) -> None:
    _insert(session.connection, "sport_prop_lines", {
        "id": row_id, "sport": "nhl", "provider": "prizepicks", "provider_prop_id": "offer-a",
        "game_id": 1, "player_id": 7, "segment": "full_game", "market": "time_on_ice",
        "odds_type": "standard", "line": 20.5, "fetched_at": OPEN,
        "raw_json": json.dumps({"player_team": "MTL"}), **overrides,
    })


def test_served_games_dates_scores_and_null_start_order(session: _Session) -> None:
    games = asyncio.run(nhl.get_games_on(cast(AsyncSession, session), date(2026, 10, 23)))
    assert [g["game_id"] for g in games] == [1, 2, 7, 6]
    assert games[2]["end_period"] == "SO" and games[2]["away_score"] == 3
    assert games[-1]["start_utc"] is None
    assert list(asyncio.run(nhl.get_game_dates(cast(AsyncSession, session)))) == [DAY]
    assert asyncio.run(nhl.get_games_on(cast(AsyncSession, session), date(2026, 10, 24))) == []


@pytest.mark.parametrize("game_id", [3, 4, 5, 999])
def test_wrong_sport_preseason_wrong_team_and_absent_game(session: _Session, game_id: int) -> None:
    assert asyncio.run(nhl.get_game(cast(AsyncSession, session), game_id)) is None


@pytest.mark.parametrize("bad", [
    {"sport": "nba"}, {"provider": "the_odds_api_us"}, {"book": "pinnacle"},
    {"book": "DraftKings"}, {"game_id": 3}, {"game_id": 4}, {"market": "regulation"},
    {"fetched_at": START}, {"fetched_at": "2026-10-23T21:00:00+00:00"},
])
def test_market_isolation_and_strict_cutoff(session: _Session, bad: dict[str, object]) -> None:
    _odds(session, 1, **bad)
    db = cast(AsyncSession, session)
    assert asyncio.run(nhl.get_latest_market_rows(db, [1, 3, 4])) == []
    assert asyncio.run(nhl.get_line_movement(db, [1, 3, 4])) == []
    assert asyncio.run(nhl.get_game_line_history(db, 1)) == []


def test_one_book_latest_movement_and_history_have_identical_selection(session: _Session) -> None:
    _odds(session, 1, line=1.5, first_side="away")
    _odds(session, 2, fetched_at=LATE, line=1.5)
    _odds(session, 3, fetched_at=LATE, line=-1.5)
    _odds(session, 4, book="bet365", fetched_at=LATE, line=8.5)
    _odds(session, 5, book="bet365", market="total", line=6.5)
    db = cast(AsyncSession, session)
    latest = asyncio.run(nhl.get_latest_market_rows(db, [1]))
    movement = asyncio.run(nhl.get_line_movement(db, [1]))
    history = asyncio.run(nhl.get_game_line_history(db, 1))
    assert [(r["market"], r["book"], r["line"]) for r in latest] == [
        ("spread", "draftkings", -1.5), ("total", "bet365", 6.5),
    ]
    assert [(r["open_line"], r["current_line"]) for r in movement] == [(-1.5, -1.5), (6.5, 6.5)]
    assert [(r["book"], r["line"]) for r in history] == [
        ("draftkings", -1.5), ("draftkings", 1.5), ("draftkings", -1.5), ("bet365", 6.5),
    ]
    assert history[-1]["fetched_at"] == OPEN


def test_ineligible_draftkings_does_not_hide_bet365(session: _Session) -> None:
    _odds(session, 1, fetched_at=START)
    _odds(session, 2, book="bet365")
    assert asyncio.run(nhl.get_latest_market_rows(cast(AsyncSession, session), [1]))[0]["book"] == "bet365"


def test_fanduel_is_read_when_draftkings_has_no_eligible_row(session: _Session) -> None:
    _odds(session, 1, fetched_at=START)
    _odds(session, 2, book="fanduel")
    assert asyncio.run(nhl.get_latest_market_rows(cast(AsyncSession, session), [1]))[0]["book"] == "fanduel"


def test_missing_start_has_latest_prices_but_no_movement_claim(session: _Session) -> None:
    _odds(session, 1, game_id=6, fetched_at=START)
    db = cast(AsyncSession, session)
    assert len(asyncio.run(nhl.get_latest_market_rows(db, [6]))) == 1
    assert asyncio.run(nhl.get_line_movement(db, [6])) == []
    assert asyncio.run(nhl.get_game_line_history(db, 6)) == []


@pytest.mark.parametrize("bad", [
    {"sport": "nba"}, {"provider": "other"}, {"segment": "p1"}, {"provider_prop_id": None},
    {"player_id": None}, {"player_id": 8}, {"game_id": 3}, {"game_id": 4},
    {"market": "unsupported"}, {"fetched_at": START},
])
def test_props_and_count_share_all_eligibility_guards(session: _Session, bad: dict[str, object]) -> None:
    _prop(session, 1, **bad)
    db = cast(AsyncSession, session)
    assert asyncio.run(nhl.get_line_only_lines(db, 1)) == []
    assert asyncio.run(nhl.get_prop_line_counts(db, [1, 3, 4])) == {}


def test_latest_offerings_preserve_alternates_units_team_and_count_parity(session: _Session) -> None:
    _prop(session, 1)
    _prop(session, 2, fetched_at=LATE, line=21.5)
    _prop(session, 3, fetched_at=LATE, line=22.5)
    _prop(session, 4, fetched_at=START, line=99)
    _prop(session, 5, provider_prop_id="offer-b", odds_type="demon", line=22.5)
    _prop(session, 6, provider_prop_id="offer-c", market="plus_minus", line=-0.5, raw_json="{}")
    _prop(session, 7, game_id=2, provider_prop_id="offer-d", line=0)
    db = cast(AsyncSession, session)
    lines = asyncio.run(nhl.get_line_only_lines(db, 1))
    offers = {r["provider_prop_id"]: r for r in lines}
    assert offers["offer-a"]["line"] == 22.5 and offers["offer-a"]["team"] == "MTL"
    assert offers["offer-b"]["odds_type"] == "demon"
    assert offers["offer-c"]["line"] == -0.5 and offers["offer-c"]["team"] is None
    assert asyncio.run(nhl.get_prop_line_counts(db, [1, 2])) == {1: len(lines), 2: 1}


def test_empty_batches_do_not_query(session: _Session) -> None:
    db = cast(AsyncSession, session)
    assert asyncio.run(nhl.get_latest_market_rows(db, [])) == []
    assert asyncio.run(nhl.get_line_movement(db, [])) == []
    assert asyncio.run(nhl.get_prop_line_counts(db, [])) == {}
    assert session.calls == 0
