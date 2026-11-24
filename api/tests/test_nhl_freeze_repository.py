import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.core.nhl_prop_predictions import NhlFreezeLine
from app.core.prop_ranking_check import FrozenLine
from app.nhl.markets import NhlLineOnlyMarket
from app.repositories.nhl import (
    get_current_week, get_finished_weeks, get_frozen_coverage, get_frozen_gradeable_lines, get_week_freeze_lines,
    get_week_games,
)

NOW = datetime(2026, 10, 24, 17, 0, tzinfo=UTC)


class _Result:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self) -> list[dict[str, object]]:
        return self.rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return [tuple(row.values()) for row in self.rows]

    def fetchone(self) -> tuple[object, ...] | None:
        return tuple(self.rows[0].values()) if self.rows else None


class _RecordingSession:
    def __init__(self, *results: list[dict[str, object]]) -> None:
        self.results = list(results)
        self.statements: list[str] = []
        self.params: dict[str, object] = {}

    async def execute(self, statement: TextClause, params: dict[str, object] | None = None) -> _Result:
        self.statements.append(str(statement))
        self.params = params or {}
        return _Result(self.results.pop(0) if self.results else [])


def _session(*results: list[dict[str, object]]) -> tuple[_RecordingSession, AsyncSession]:
    session = _RecordingSession(*results)
    return session, cast(AsyncSession, session)


def test_the_current_week_is_the_next_unstarted_regular_season_game() -> None:
    session, db = _session([{"season": 2026, "week": 3}])

    assert asyncio.run(get_current_week(db, NOW)) == (2026, 3)
    assert len(session.statements) == 1 and session.params == {"now": NOW}
    statement = session.statements[0]
    assert "sport = 'nhl'" in statement and "game_type = 'REG'" in statement
    assert "week IS NOT NULL" in statement and "start_utc > :now" in statement


def test_the_current_week_falls_back_to_the_latest_loaded_week_then_none() -> None:
    session, db = _session([], [{"season": 2026, "week": 28}])
    assert asyncio.run(get_current_week(db, NOW)) == (2026, 28)
    assert "ORDER BY season DESC, week DESC" in session.statements[1]

    _, empty = _session([], [])
    assert asyncio.run(get_current_week(empty, NOW)) is None


def test_week_lines_keep_the_boards_filters_and_only_regular_season_games() -> None:
    session, db = _session([])

    assert asyncio.run(get_week_freeze_lines(db, 2026, 3)) == []

    statement = session.statements[0]
    assert session.params["season"] == 2026 and session.params["week"] == 3
    assert sorted(cast(list[str], session.params["markets"])) == sorted(m.value for m in NhlLineOnlyMarket)
    for fragment in (
        "l.sport = 'nhl'", "g.sport = 'nhl'", "p.sport = 'nhl'", "l.provider = 'prizepicks'",
        "l.segment = 'full_game'", "l.provider_prop_id IS NOT NULL", "g.game_type = 'REG'",
        "g.week = :week", "g.season = :season", "l.market IN (__[POSTCOMPILE_markets])", "l.fetched_at < g.start_utc",
        "PARTITION BY l.game_id, l.provider, l.provider_prop_id ORDER BY l.fetched_at DESC, l.id DESC",
    ):
        assert fragment in statement
    assert "PRE" not in statement


def test_week_lines_map_into_freeze_lines() -> None:
    start = datetime(2026, 10, 24, 23, 0, tzinfo=UTC)
    fetched = datetime(2026, 10, 24, 16, 59, tzinfo=UTC)
    row: dict[str, object] = {
        "line_id": 91, "game_id": 5, "game_date": date(2026, 10, 24), "start_utc": start, "player_id": 7,
        "team": "BOS", "position": "C", "market": "shots_on_goal", "odds_type": "demon", "line": Decimal("3.5"),
        "fetched_at": fetched,
    }
    _, db = _session([row])

    assert asyncio.run(get_week_freeze_lines(db, 2026, 3)) == [NhlFreezeLine(
        line_id=91, game_id=5, game_date=date(2026, 10, 24), start_utc=start, player_id=7, team="BOS",
        position="C", market="shots_on_goal", odds_type="demon", line=3.5, fetched_at=fetched,
    )]


def test_week_games_read_the_weeks_regular_season_games() -> None:
    session, db = _session([{"game_id": 5}])

    assert asyncio.run(get_week_games(db, 2026, 3)) == [{"game_id": 5}]
    assert session.params == {"season": 2026, "week": 3}
    assert "g.sport = 'nhl'" in session.statements[0] and "g.game_type = 'REG'" in session.statements[0]


def test_frozen_lines_read_each_props_latest_pre_puck_drop_row_on_completed_regular_season_games() -> None:
    session, db = _session([])

    assert asyncio.run(get_frozen_gradeable_lines(db, 2026)) == []

    statement = session.statements[0]
    assert session.params["season"] == 2026
    assert sorted(cast(list[str], session.params["markets"])) == sorted(m.value for m in NhlLineOnlyMarket)
    for alias in ("p", "l", "g"):
        assert f"{alias}.sport = 'nhl'" in statement
    for fragment in (
        "g.game_type = 'REG' AND g.week IS NOT NULL", "g.status = 'completed'", "l.segment = 'full_game'",
        "l.market IN (__[POSTCOMPILE_markets])", "l.fetched_at < g.start_utc AND p.generated_at < g.start_utc",
        "DISTINCT ON (l.provider, l.provider_prop_id)",
        "l.fetched_at DESC, l.id DESC, p.generated_at DESC, p.id DESC",
        "LEFT JOIN nhl_skater_game_stats sk ON sk.player_id = frozen.player_id AND sk.game_id = frozen.game_id",
        "LEFT JOIN nhl_goalie_game_stats gk ON gk.player_id = frozen.player_id AND gk.game_id = frozen.game_id",
    ):
        assert fragment in statement
    assert "FROM nhl_skater_game_stats" in statement and "FROM nhl_goalie_game_stats" in statement


def _frozen_row(**overrides: object) -> dict[str, object]:
    skater = {f"s_{c}": None for c in (
        "shots", "points", "assists", "goals", "power_play_points", "blocked_shots", "plus_minus", "hits",
        "faceoffs_won", "time_on_ice_seconds",
    )}
    goalie = {f"g_{c}": None for c in ("saves", "goals_against", "started", "time_on_ice_seconds")}
    return {
        "id": 501, "market": "shots_on_goal", "odds_type": "standard", "line": "2.5", "player_id": 7, "game_id": 9,
        "week": 3, "p_over": 0.41, "p_under": 0.59, "model_version": "nhl-reference-v1",
        "over_probability_version": "nhl-pover-v1", "has_skater_row": False, "has_goalie_row": False,
        "game_has_box_scores": True, **skater, **goalie, **overrides,
    }


def _settled(**overrides: object) -> FrozenLine:
    _, db = _session([_frozen_row(**overrides)])
    (line,) = asyncio.run(get_frozen_gradeable_lines(db, 2026))
    return line


def test_a_skater_row_settles_the_frozen_line_and_keeps_what_was_served() -> None:
    line = _settled(has_skater_row=True, s_shots=4)

    assert line == FrozenLine(
        line_id=501, period=3, player_id=7, game_id=9, market="shots_on_goal", odds_type="standard",
        outcome="over", p_over=0.41, p_under=0.59, model_version="nhl-reference-v1",
        over_probability_version="nhl-pover-v1",
    )


def test_a_goalie_row_settles_a_goalie_line_and_a_non_start_is_void() -> None:
    saves = {"market": "goalie_saves", "line": "24.5", "has_goalie_row": True, "g_saves": 20, "g_started": True}

    assert _settled(**saves).outcome == "under"
    assert _settled(**{**saves, "g_started": False}).outcome == "void_dnp"


def test_a_loaded_game_without_the_player_is_void_and_an_unloaded_game_is_not_a_call() -> None:
    assert _settled().outcome == "void_dnp"
    assert _settled(game_has_box_scores=False).outcome == "stats_not_loaded"


def test_a_row_missing_the_stat_is_not_a_call() -> None:
    assert _settled(has_skater_row=True, s_shots=None).outcome == "missing_stat"


def test_finished_weeks_need_every_game_done_and_every_completed_game_loaded() -> None:
    session, db = _session([{"week": 1}, {"week": 2}])

    assert asyncio.run(get_finished_weeks(db, 2026)) == {1, 2}

    statement = session.statements[0]
    assert "g.sport = 'nhl'" in statement and "g.game_type = 'REG'" in statement
    assert "bool_and(g.status IN ('completed', 'postponed', 'canceled'))" in statement
    assert "g.status <> 'completed'" in statement
    assert "EXISTS (SELECT 1 FROM nhl_skater_game_stats s WHERE s.game_id = g.id)" in statement
    assert "EXISTS (SELECT 1 FROM nhl_goalie_game_stats s WHERE s.game_id = g.id)" in statement


def test_frozen_coverage_counts_gradeable_lines_and_those_with_a_frozen_pre_start_row() -> None:
    session, db = _session([{"week": 1, "lines": 10, "frozen": 9}, {"week": 2, "lines": 4, "frozen": 4}])

    assert asyncio.run(get_frozen_coverage(db, 2026)) == {1: (10, 9), 2: (4, 4)}

    statement = session.statements[0]
    assert sorted(cast(list[str], session.params["markets"])) == sorted(m.value for m in NhlLineOnlyMarket)
    for fragment in (
        "l.sport = 'nhl'", "g.game_type = 'REG'", "g.status = 'completed'", "l.segment = 'full_game'",
        "l.market IN (__[POSTCOMPILE_markets])", "l.fetched_at < g.start_utc",
        "p.sport = 'nhl'", "p.generated_at < fg.start_utc", "fl.fetched_at < fg.start_utc",
    ):
        assert fragment in statement
