"""Exercise targets query predicates and latest-row selection on synthetic data."""
from __future__ import annotations

import asyncio
import re
import sqlite3
from collections.abc import Iterator
from typing import cast

import pytest
from sqlalchemy import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.core.nfl_targets_projection import NFL_TARGETS_MODEL_VERSION
from app.core.prop_ranking_check import FrozenLine
from app.repositories import nfl_targets_ranking as repo
from tests.test_nfl_targets_repository import _Result, _Session

KICKOFF = "2026-10-18T17:00:00"


def _sqlite_query(sql: str) -> str:
    # SQLite lacks DISTINCT ON; the equivalent window keeps the production WHERE and ordering.
    pattern = r"SELECT DISTINCT ON \((.*?)\)\s+(.*?)\s+FROM(.*?)ORDER BY(.*?)(?=\n    \))"

    def window(match: re.Match[str]) -> str:
        keys, columns, source, order = match.groups()
        return (
            f"SELECT * FROM (SELECT {columns}, ROW_NUMBER() OVER "
            f"(PARTITION BY {keys} ORDER BY {order}) AS selection_rank FROM {source}) "
            "WHERE selection_rank = 1"
        )

    converted, count = re.subn(pattern, window, sql, flags=re.DOTALL)
    assert count == 1
    return converted


class _SqliteSession:
    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            CREATE TABLE sport_games (id INTEGER, sport TEXT, season INTEGER, week INTEGER,
                game_type TEXT, status TEXT, start_utc TEXT);
            CREATE TABLE sport_players (id INTEGER, sport TEXT, position TEXT);
            CREATE TABLE sport_prop_lines (id INTEGER, sport TEXT, provider TEXT, provider_prop_id TEXT,
                player_id INTEGER, game_id INTEGER, market TEXT, segment TEXT, odds_type TEXT,
                line REAL, fetched_at TEXT);
            CREATE TABLE sport_prop_predictions (id INTEGER, sport TEXT, prop_line_id INTEGER,
                model_version TEXT, over_probability_version TEXT, generated_at TEXT, p_over REAL, p_under REAL);
            CREATE TABLE nfl_player_weekly_stats (player_id INTEGER, game_id INTEGER, targets REAL);
            CREATE TABLE nfl_player_snap_counts (player_id INTEGER, game_id INTEGER, offense_snaps INTEGER);
            INSERT INTO sport_games VALUES (50, 'nfl', 2026, 6, 'REG', 'completed', '2026-10-18T17:00:00');
            INSERT INTO sport_players VALUES (7, 'nfl', 'WR'), (9, 'nfl', 'TE');
            INSERT INTO nfl_player_weekly_stats VALUES (7, 50, 6);
        """)
        self.calls: list[str] = []

    def line(self, line_id: int = 1, **overrides: object) -> None:
        values = {
            "id": line_id, "sport": "nfl", "provider": "prizepicks", "provider_prop_id": "prop-1",
            "player_id": 7, "game_id": 50, "market": "receiving_targets", "segment": "full_game",
            "odds_type": "standard", "line": 4.5, "fetched_at": "2026-10-17T12:00:00",
        } | overrides
        self.connection.execute(
            f"INSERT INTO sport_prop_lines ({', '.join(values)}) VALUES ({', '.join('?' for _ in values)})",
            tuple(values.values()),
        )

    def prediction(self, prediction_id: int = 1, **overrides: object) -> None:
        values = {
            "id": prediction_id, "sport": "nfl", "prop_line_id": 1,
            "model_version": NFL_TARGETS_MODEL_VERSION, "over_probability_version": None,
            "generated_at": "2026-10-17T13:00:00", "p_over": None, "p_under": None,
        } | overrides
        self.connection.execute(
            f"INSERT INTO sport_prop_predictions ({', '.join(values)}) VALUES ({', '.join('?' for _ in values)})",
            tuple(values.values()),
        )

    async def execute(self, statement: TextClause, params: dict[str, object]) -> _Result:
        self.calls.append(str(statement))
        rows = self.connection.execute(_sqlite_query(str(statement)), params).fetchall()
        return _Result([dict(row) for row in rows])


@pytest.fixture
def session() -> Iterator[_SqliteSession]:
    value = _SqliteSession()
    try:
        yield value
    finally:
        value.connection.close()


def _frozen(session: _SqliteSession) -> list[FrozenLine]:
    return asyncio.run(repo.get_frozen_gradeable_lines(cast(AsyncSession, session), 2026))


def _coverage(session: _SqliteSession) -> dict[int, tuple[int, int]]:
    return asyncio.run(repo.get_frozen_coverage(cast(AsyncSession, session), 2026))


def test_queries_bind_the_targets_identity_and_filter_before_latest_selection() -> None:
    for loader in (repo.get_frozen_gradeable_lines, repo.get_frozen_coverage):
        recorded = _Session([])
        asyncio.run(loader(cast(AsyncSession, recorded), 2026))
        (sql, params), = recorded.calls
        assert params == {"season": 2026, "model_version": NFL_TARGETS_MODEL_VERSION}
        eligible, remaining = re.split(r"\)\s*,", sql, maxsplit=1)
        for condition in (
            "g.sport = 'nfl'", "pl.sport = 'nfl'", "l.sport = 'nfl'",
            "l.market = 'receiving_targets'", "l.segment = 'full_game'", "l.odds_type = 'standard'",
            "pl.position IN ('RB', 'WR', 'TE')", "g.season = :season", "g.week BETWEEN 1 AND 18",
            "g.game_type = 'REG'", "g.status = 'completed'", "l.fetched_at < g.start_utc",
        ):
            assert condition in eligible
        assert "p.sport = 'nfl'" in remaining
        assert "p.model_version = :model_version" in remaining
        assert "p.over_probability_version IS NULL" in remaining
        assert "p.generated_at < l.start_utc" in remaining
    assert remaining.count("l.player_id = latest.player_id") == 1
    assert "l.game_id = latest.game_id AND l.market = latest.market" in remaining


def test_no_eligible_lines_is_an_empty_record_not_a_query_failure(session: _SqliteSession) -> None:
    assert _frozen(session) == []
    assert _coverage(session) == {}
    assert len(session.calls) == 2


def test_a_newer_unfrozen_line_keeps_the_earlier_frozen_call_and_counts_coverage(session: _SqliteSession) -> None:
    session.line()
    session.prediction()
    session.line(2, line=7.5, fetched_at="2026-10-18T12:00:00")

    frozen, = _frozen(session)

    assert (frozen.line_id, frozen.period, frozen.player_id, frozen.game_id) == (1, 6, 7, 50)
    assert frozen.outcome == "over"
    assert (frozen.model_version, frozen.over_probability_version, frozen.p_over, frozen.p_under) == (
        NFL_TARGETS_MODEL_VERSION, None, None, None,
    )
    assert _coverage(session) == {6: (1, 1)}


def test_latest_line_and_prediction_ties_are_deterministic(session: _SqliteSession) -> None:
    session.line()
    session.prediction()
    session.line(2, line=8.5)
    session.prediction(2, prop_line_id=2)
    session.prediction(3, prop_line_id=2, generated_at="2026-10-17T14:00:00")

    frozen, = _frozen(session)

    assert (frozen.line_id, frozen.outcome) == (2, "under")
    sql, = session.calls
    assert "p.generated_at DESC, p.id DESC" in sql
    assert _coverage(session) == {6: (1, 1)}


@pytest.mark.parametrize("change", [
    {"model_version": "opponent-dvp-tg-blend-usage-snap-v4"},
    {"model_version": "nfl-targets-v2"},
    {"over_probability_version": "nfl-targets-pover-v1"},
    {"over_probability_version": ""},
    {"sport": "nba"},
    {"generated_at": KICKOFF},
    {"generated_at": "2026-10-18T18:00:00"},
])
def test_ineligible_predictions_cannot_displace_or_cover_a_targets_row(
    session: _SqliteSession, change: dict[str, object],
) -> None:
    session.line()
    session.prediction(**change)
    assert _frozen(session) == []
    assert _coverage(session) == {6: (1, 0)}

    session.prediction(2)
    session.line(2, fetched_at="2026-10-18T12:00:00")
    session.prediction(3, prop_line_id=2, **change)
    assert [line.line_id for line in _frozen(session)] == [1]
    assert _coverage(session) == {6: (1, 1)}


@pytest.mark.parametrize("change", [
    {"sport": "nba"}, {"market": "receptions"}, {"market": "passing_touchdowns"},
    {"segment": "first_half"}, {"odds_type": "goblin"}, {"odds_type": "demon"},
    {"odds_type": None}, {"player_id": None}, {"provider_prop_id": None},
    {"fetched_at": KICKOFF}, {"fetched_at": "2026-10-18T18:00:00"},
])
def test_ineligible_lines_are_absent_from_grading_and_coverage(
    session: _SqliteSession, change: dict[str, object],
) -> None:
    session.line(**change)
    session.prediction()
    assert _frozen(session) == []
    assert _coverage(session) == {}


@pytest.mark.parametrize("column, value", [
    ("sport", "nba"), ("season", 2025), ("week", 0), ("week", 19),
    ("game_type", "PRE"), ("game_type", "PST"), ("status", "scheduled"), ("start_utc", None),
])
def test_ineligible_games_are_absent_from_grading_and_coverage(
    session: _SqliteSession, column: str, value: object,
) -> None:
    session.connection.execute(f"UPDATE sport_games SET {column} = ?", (value,))
    session.line()
    session.prediction()
    assert _frozen(session) == []
    assert _coverage(session) == {}


@pytest.mark.parametrize("column, value", [("sport", "nba"), ("position", "QB"), ("position", None)])
def test_ineligible_players_are_absent_from_grading_and_coverage(
    session: _SqliteSession, column: str, value: object,
) -> None:
    session.connection.execute(f"UPDATE sport_players SET {column} = ? WHERE id = 7", (value,))
    session.line()
    session.prediction()
    assert _frozen(session) == []
    assert _coverage(session) == {}


@pytest.mark.parametrize("changed_identity", [{"player_id": 9}, {"game_id": 51}])
def test_coverage_cannot_borrow_a_frozen_row_from_another_player_or_game(
    session: _SqliteSession, changed_identity: dict[str, object],
) -> None:
    session.connection.execute("INSERT INTO sport_games SELECT 51, sport, season, week, game_type, status, start_utc FROM sport_games")
    session.line()
    session.prediction()
    session.line(2, fetched_at="2026-10-18T12:00:00", **changed_identity)
    assert _coverage(session) == {6: (1, 0)}


def test_provider_names_separate_equal_provider_prop_ids(session: _SqliteSession) -> None:
    session.line()
    session.line(2, provider="other")
    session.prediction()
    assert _coverage(session) == {6: (2, 1)}


@pytest.mark.parametrize("targets, player_row, snaps, game_stats, line, outcome", [
    (6, True, 40, True, 4.5, "over"), (0, True, None, True, 4.5, "under"),
    (4, True, 40, True, 4, "push"), (None, True, 40, True, 4.5, "stat_unavailable"),
    (-1, True, 40, True, 4.5, "stat_unavailable"),
    (float("nan"), True, 40, True, 4.5, "stat_unavailable"),
    (None, False, 40, True, 4.5, "under"), (None, False, None, True, 4.5, "void_dnp"),
    (None, False, 40, False, 4.5, "week_not_loaded"),
    (6, True, 40, True, None, "invalid_line"),
])
def test_row_mapping_preserves_presence_and_uses_targets_settlement(
    targets: float | None, player_row: bool, snaps: int | None,
    game_stats: bool, line: float | None, outcome: str,
) -> None:
    row = cast(RowMapping, {
        "id": 70, "week": 6, "player_id": 7, "game_id": 50, "market": "receiving_targets",
        "odds_type": "standard", "line": line, "targets": targets, "player_has_stats": player_row,
        "offense_snaps": snaps, "game_has_stats": game_stats, "p_over": None, "p_under": None,
        "model_version": NFL_TARGETS_MODEL_VERSION, "over_probability_version": None,
    })
    result = repo._frozen_line(row)
    assert result.outcome == outcome


def test_game_and_player_stat_presence_are_loaded_without_turning_nulls_into_zeros(session: _SqliteSession) -> None:
    session.line()
    session.prediction()
    session.connection.execute("UPDATE nfl_player_weekly_stats SET targets = NULL")
    session.connection.execute("INSERT INTO nfl_player_snap_counts VALUES (7, 50, 40)")
    assert _frozen(session)[0].outcome == "stat_unavailable"
    session.connection.execute("UPDATE nfl_player_weekly_stats SET player_id = 9")
    assert _frozen(session)[0].outcome == "under"
    session.connection.execute("DELETE FROM nfl_player_weekly_stats")
    assert _frozen(session)[0].outcome == "week_not_loaded"
