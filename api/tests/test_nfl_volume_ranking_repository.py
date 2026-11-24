"""Exercise the volume ranking predicates and latest-row selection on synthetic data."""
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

from app.core.nfl_volume_anchor import NFL_VOLUME_ANCHOR_VERSION
from app.core.nfl_volume_projection import NFL_VOLUME_MODEL_VERSION
from app.core.prop_ranking_check import FrozenLine
from app.repositories import nfl_volume_ranking as repo
from tests.helpers.nfl_targets_repository import _Result, _Session

KICKOFF = "2026-11-08T18:00:00"
V4 = "opponent-dvp-tg-blend-usage-snap-v4"


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
    # SQLite has no arrays: the bound payout list is the same three values inline.
    return converted.replace("= ANY(CAST(:odds_types AS text[]))", "IN ('standard', 'goblin', 'demon')")


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
                model_version TEXT, over_probability_version TEXT, generated_at TEXT, p_over REAL, p_under REAL,
                feature_snapshot TEXT);
            CREATE TABLE nfl_player_weekly_stats (player_id INTEGER, game_id INTEGER, receptions REAL);
            CREATE TABLE nfl_player_snap_counts (player_id INTEGER, game_id INTEGER, offense_snaps INTEGER);
            INSERT INTO sport_games VALUES (50, 'nfl', 2026, 9, 'REG', 'completed', '2026-11-08T18:00:00');
            INSERT INTO sport_players VALUES (7, 'nfl', 'WR'), (9, 'nfl', 'TE');
            INSERT INTO nfl_player_weekly_stats VALUES (7, 50, 6);
        """)
        self.calls: list[str] = []

    def line(self, line_id: int = 1, **overrides: object) -> None:
        values = {
            "id": line_id, "sport": "nfl", "provider": "prizepicks", "provider_prop_id": "prop-1",
            "player_id": 7, "game_id": 50, "market": "receptions", "segment": "full_game",
            "odds_type": "standard", "line": 4.5, "fetched_at": "2026-11-07T12:00:00",
        } | overrides
        self.connection.execute(
            f"INSERT INTO sport_prop_lines ({', '.join(values)}) VALUES ({', '.join('?' for _ in values)})",
            tuple(values.values()),
        )

    def prediction(self, prediction_id: int = 1, **overrides: object) -> None:
        values = {
            "id": prediction_id, "sport": "nfl", "prop_line_id": 1,
            "model_version": NFL_VOLUME_MODEL_VERSION, "over_probability_version": NFL_VOLUME_ANCHOR_VERSION,
            "generated_at": "2026-11-07T13:00:00", "p_over": 0.55, "p_under": 0.45,
            "feature_snapshot": '{"q_vol": 0.62, "p_push": 0.0}',
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


def _volume(session: _SqliteSession) -> list[repo.VolumeFrozenLine]:
    return asyncio.run(repo.get_frozen_volume_lines(cast(AsyncSession, session), 2026))


def _frozen(session: _SqliteSession) -> list[FrozenLine]:
    return asyncio.run(repo.get_frozen_gradeable_lines(cast(AsyncSession, session), 2026))


def _coverage(session: _SqliteSession) -> dict[int, tuple[int, int]]:
    return asyncio.run(repo.get_frozen_coverage(cast(AsyncSession, session), 2026))


def test_queries_bind_the_volume_identity_and_filter_before_latest_selection() -> None:
    for loader in (repo.get_frozen_volume_lines, repo.get_frozen_coverage):
        recorded = _Session([])
        asyncio.run(loader(cast(AsyncSession, recorded), 2026))
        ((sql, params),) = recorded.calls
        assert params == {
            "season": 2026, "market": "receptions", "model_version": "nfl-volume-v1",
            "over_probability_version": "nfl-volume-anchor-v1", "odds_types": ["standard", "goblin", "demon"],
        }
        eligible, remaining = re.split(r"\)\s*,", sql, maxsplit=1)
        for condition in (
            "g.sport = 'nfl'", "pl.sport = 'nfl'", "l.sport = 'nfl'", "l.market = :market",
            "l.segment = 'full_game'", "l.odds_type = ANY(CAST(:odds_types AS text[]))", "pl.position IN ('RB', 'WR', 'TE')",
            "g.season = :season", "g.week BETWEEN 1 AND 18", "g.game_type = 'REG'", "g.status = 'completed'",
            "l.fetched_at < g.start_utc",
        ):
            assert condition in eligible
        assert "p.sport = 'nfl'" in remaining
        assert "p.model_version = :model_version" in remaining
        assert "p.over_probability_version = :over_probability_version" in remaining
        assert "p.generated_at < l.start_utc" in remaining
    assert remaining.count("l.player_id = latest.player_id") == 1
    assert "l.game_id = latest.game_id AND l.market = latest.market" in remaining


def test_the_identity_filter_comes_before_the_newest_row_is_picked() -> None:
    recorded = _Session([])
    asyncio.run(repo.get_frozen_volume_lines(cast(AsyncSession, recorded), 2026))
    ((sql, _),) = recorded.calls
    assert sql.index("p.model_version = :model_version") < sql.index("ORDER BY l.provider, l.provider_prop_id")


def test_no_eligible_lines_is_an_empty_record_not_a_query_failure(session: _SqliteSession) -> None:
    assert _frozen(session) == []
    assert _coverage(session) == {}
    assert len(session.calls) == 2


def test_a_newer_unfrozen_line_keeps_the_earlier_frozen_call_and_counts_coverage(session: _SqliteSession) -> None:
    session.line()
    session.prediction()
    session.line(2, line=7.5, fetched_at="2026-11-08T12:00:00")

    ((item),) = _volume(session)
    frozen = item.frozen

    assert (frozen.line_id, frozen.period, frozen.player_id, frozen.game_id) == (1, 9, 7, 50)
    assert frozen.outcome == "over"
    assert (frozen.model_version, frozen.over_probability_version, frozen.p_over, frozen.p_under) == (
        "nfl-volume-v1", "nfl-volume-anchor-v1", 0.55, 0.45,
    )
    assert item.q_vol == pytest.approx(0.62)
    assert _coverage(session) == {9: (1, 1)}


def test_latest_line_and_prediction_ties_are_deterministic(session: _SqliteSession) -> None:
    session.line()
    session.prediction()
    session.line(2, line=8.5)
    session.prediction(2, prop_line_id=2)
    session.prediction(3, prop_line_id=2, generated_at="2026-11-07T14:00:00", feature_snapshot='{"q_vol": 0.4}')

    ((item),) = _volume(session)

    assert (item.frozen.line_id, item.frozen.outcome, item.q_vol) == (2, "under", pytest.approx(0.4))
    assert "p.generated_at DESC, p.id DESC" in session.calls[0]
    assert _coverage(session) == {9: (1, 1)}


@pytest.mark.parametrize("change", [
    {"model_version": V4},
    {"model_version": "nfl-targets-v1"},
    {"model_version": "nfl-volume-v2"},
    {"over_probability_version": None},
    {"over_probability_version": "nfl-pover-v1"},
    {"over_probability_version": ""},
    {"sport": "nba"},
    {"generated_at": KICKOFF},
    {"generated_at": "2026-11-08T19:00:00"},
])
def test_another_models_row_cannot_displace_or_cover_a_volume_row(
    session: _SqliteSession, change: dict[str, object],
) -> None:
    session.line()
    session.prediction(**change)
    assert _volume(session) == []
    assert _coverage(session) == {9: (1, 0)}

    session.prediction(2)
    session.line(2, fetched_at="2026-11-08T12:00:00")
    session.prediction(3, prop_line_id=2, **change)
    assert [item.frozen.line_id for item in _volume(session)] == [1]
    assert _coverage(session) == {9: (1, 1)}


def test_a_later_v4_row_on_the_same_line_does_not_replace_the_volume_row(session: _SqliteSession) -> None:
    session.line()
    session.prediction()
    session.prediction(2, model_version=V4, over_probability_version="nfl-pover-v1", generated_at="2026-11-07T15:00:00")

    ((item),) = _volume(session)

    assert item.frozen.model_version == "nfl-volume-v1" and item.frozen.p_over == 0.55
    assert _coverage(session) == {9: (1, 1)}


@pytest.mark.parametrize("change", [
    {"sport": "nba"}, {"market": "receiving_yards"}, {"market": "receiving_targets"}, {"segment": "first_half"},
    {"odds_type": "alternate"}, {"odds_type": "flex"}, {"odds_type": None}, {"player_id": None},
    {"provider_prop_id": None}, {"fetched_at": KICKOFF}, {"fetched_at": "2026-11-08T19:00:00"},
])
def test_ineligible_lines_are_absent_from_grading_and_coverage(session: _SqliteSession, change: dict[str, object]) -> None:
    session.line(**change)
    session.prediction()
    assert _volume(session) == []
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
    assert _volume(session) == []
    assert _coverage(session) == {}


@pytest.mark.parametrize("column, value", [("sport", "nba"), ("position", "QB"), ("position", None)])
def test_ineligible_players_are_absent_from_grading_and_coverage(
    session: _SqliteSession, column: str, value: object,
) -> None:
    session.connection.execute(f"UPDATE sport_players SET {column} = ? WHERE id = 7", (value,))
    session.line()
    session.prediction()
    assert _volume(session) == []
    assert _coverage(session) == {}


@pytest.mark.parametrize("changed_identity", [{"player_id": 9}, {"game_id": 51}])
def test_coverage_cannot_borrow_a_frozen_row_from_another_player_or_game(
    session: _SqliteSession, changed_identity: dict[str, object],
) -> None:
    session.connection.execute(
        "INSERT INTO sport_games SELECT 51, sport, season, week, game_type, status, start_utc FROM sport_games"
    )
    session.line()
    session.prediction()
    session.line(2, fetched_at="2026-11-08T12:00:00", **changed_identity)
    assert _coverage(session) == {9: (1, 0)}


def test_provider_names_separate_equal_provider_prop_ids(session: _SqliteSession) -> None:
    session.line()
    session.line(2, provider="other")
    session.prediction()
    assert _coverage(session) == {9: (2, 1)}


def test_goblin_and_demon_rungs_load_as_their_own_frozen_rows_and_count_in_coverage(session: _SqliteSession) -> None:
    for line_id, odds, prop in ((1, "standard", "p-std"), (2, "goblin", "p-gob"), (3, "demon", "p-dem")):
        session.line(line_id, odds_type=odds, provider_prop_id=prop, line=4.5 if odds == "standard" else 2.5)
        session.prediction(line_id, prop_line_id=line_id, p_over=0.5 + line_id / 20, p_under=0.5 - line_id / 20)

    loaded = _volume(session)

    assert sorted((item.frozen.line_id, item.frozen.odds_type, item.frozen.outcome) for item in loaded) == [
        (1, "standard", "over"), (2, "goblin", "over"), (3, "demon", "over"),
    ]
    assert _coverage(session) == {9: (3, 3)}


def test_a_v4_or_targets_row_on_a_rung_cannot_displace_or_cover_a_volume_rung_row(session: _SqliteSession) -> None:
    session.line(1, odds_type="demon", provider_prop_id="p-dem", line=7.5)
    session.prediction(1, model_version=V4, over_probability_version="nfl-pover-v1")
    session.prediction(2, model_version="nfl-targets-v1", over_probability_version=None)
    assert _volume(session) == [] and _coverage(session) == {9: (1, 0)}

    session.prediction(3)
    session.prediction(4, model_version=V4, over_probability_version="nfl-pover-v1", generated_at="2026-11-07T15:00:00")
    ((item),) = _volume(session)
    assert (item.frozen.odds_type, item.frozen.model_version) == ("demon", "nfl-volume-v1")
    assert _coverage(session) == {9: (1, 1)}


def test_one_player_games_rungs_are_separate_provider_props(session: _SqliteSession) -> None:
    session.line(1, odds_type="goblin", provider_prop_id="p-gob-a", line=2.5)
    session.line(2, odds_type="goblin", provider_prop_id="p-gob-b", line=3.5)
    session.prediction(1, prop_line_id=1)
    session.prediction(2, prop_line_id=2)

    assert sorted(item.frozen.line_id for item in _volume(session)) == [1, 2]
    assert _coverage(session) == {9: (2, 2)}


def _row(**overrides: object) -> RowMapping:
    return cast(RowMapping, {
        "id": 70, "season": 2026, "week": 9, "player_id": 7, "game_id": 50, "market": "receptions",
        "segment": "full_game", "odds_type": "standard", "line": 4.5, "fetched_at": "2026-11-07T12:00:00",
        "receptions": 6, "player_has_stats": True, "offense_snaps": 40, "game_has_stats": True,
        "p_over": 0.55, "p_under": 0.45, "model_version": "nfl-volume-v1",
        "over_probability_version": "nfl-volume-anchor-v1", "q_vol": "0.62",
    } | overrides)


@pytest.mark.parametrize("receptions, snaps, game_stats, line, outcome", [
    (6, 40, True, 4.5, "over"), (0, None, True, 4.5, "under"), (4, 40, True, 4, "push"),
    (None, 40, True, 4.5, "under"), (None, None, True, 4.5, "void_dnp"), (None, 40, False, 4.5, "week_not_loaded"),
    (-1, 40, True, 4.5, "stat_unavailable"), (float("nan"), 40, True, 4.5, "stat_unavailable"),
    (6, 40, True, None, "invalid_line"), (6, 40, True, -1, "invalid_line"),
])
def test_settlement_uses_receptions_with_the_nfl_zero_and_void_conventions(
    receptions: float | None, snaps: int | None, game_stats: bool, line: float | None, outcome: str,
) -> None:
    item = repo._volume_line(_row(receptions=receptions, offense_snaps=snaps, game_has_stats=game_stats, line=line))
    assert item.frozen.outcome == outcome


@pytest.mark.parametrize("q_vol", [None, "", "abc", "nan", "inf", "0", "1", "-0.2", "1.5"])
def test_a_missing_or_invalid_q_vol_fails_closed_to_an_exclusion(q_vol: object) -> None:
    item = repo._volume_line(_row(q_vol=q_vol))
    assert item.frozen.outcome == repo.Q_VOL_UNAVAILABLE


@pytest.mark.parametrize("p_over, p_under", [(None, 0.45), (0.55, None), (float("nan"), 0.45), (1.2, 0.1), (0.0, 0.0)])
def test_a_missing_or_invalid_served_probability_fails_closed_to_an_exclusion(
    p_over: float | None, p_under: float | None,
) -> None:
    item = repo._volume_line(_row(p_over=p_over, p_under=p_under))
    assert item.frozen.outcome == repo.PROBABILITY_UNAVAILABLE


def test_the_raw_projection_chance_is_carried_as_a_number() -> None:
    item = repo._volume_line(_row(q_vol="0.62"))
    assert item.q_vol == pytest.approx(0.62) and item.frozen.p_over == 0.55
