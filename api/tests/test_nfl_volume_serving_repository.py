import asyncio
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.core.nfl_volume_backtest import VOLUME_STATS
from app.core.nfl_volume_projection import NFL_VOLUME_V1_PARAMETERS, VOLUME_FIRST_HISTORY_SEASON
from app.repositories.nfl_volume_serving import (
    VOLUME_SERVING_POSITIONS,
    VolumeServingLine,
    get_volume_serving_lines,
)

KICKOFF = datetime(2026, 11, 8, 18, tzinfo=UTC)
FETCHED = datetime(2026, 11, 5, 12, tzinfo=UTC)


class _Result:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self) -> list[RowMapping]:
        return cast(list[RowMapping], self.rows)


class _Session:
    def __init__(self, *responses: list[dict[str, object]]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(self, statement: TextClause, params: dict[str, object]) -> _Result:
        self.calls.append((" ".join(str(statement).split()), params))
        return _Result(self.responses.pop(0))


def _line_row(**overrides: object) -> dict[str, object]:
    return {
        "id": 900, "game_id": 50, "player_id": 7, "player_name": "A Receiver", "position": "WR",
        "market": "receptions", "segment": "full_game", "odds_type": "standard", "line": Decimal("5.5"),
        "provider": "prizepicks", "fetched_at": FETCHED, "season": 2026, "week": 10, "start_utc": KICKOFF,
        "home_team_id": 11, "away_team_id": 12, "spread_line": Decimal("-3.5"), "total_line": Decimal("44.5"),
        "player_team_id": 11,
    } | overrides


def _history_row(**overrides: object) -> dict[str, object]:
    return {
        "player_id": 7, "game_id": 40, "season": 2026, "week": 9, **{stat: None for stat in VOLUME_STATS},
        "targets": Decimal("8"), "receptions": Decimal("0"),
        "pass_attempts": Decimal("34"), "rush_attempts": Decimal("26"),
    } | overrides


def _load(session: _Session, season: int = 2026, week: int = 10) -> list[VolumeServingLine]:
    return asyncio.run(get_volume_serving_lines(cast(AsyncSession, session), season, week))


def _sql() -> tuple[str, str]:
    session = _Session([_line_row()], [])
    _load(session)
    return session.calls[0][0], session.calls[1][0]


def test_every_shared_table_alias_is_filtered_to_nfl() -> None:
    for sql in _sql():
        for alias in re.findall(r"(?:sport_games|sport_players|sport_prop_lines) (\w+)", sql):
            assert f"{alias}.sport = 'nfl'" in sql


def test_only_standard_full_game_receptions_lines_of_modelled_positions_before_kickoff() -> None:
    session = _Session([])
    _load(session)
    sql, params = session.calls[0]

    assert "l.market = :market" in sql and "l.segment = 'full_game'" in sql and "l.odds_type = 'standard'" in sql
    assert "g.game_type = 'REG'" in sql and "g.week BETWEEN 1 AND 18" in sql
    assert "(g.start_utc IS NULL OR l.fetched_at < g.start_utc)" in sql
    assert "l.player_id IS NOT NULL" in sql
    assert "ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC" in sql
    assert params["market"] == "receptions" and params["positions"] == ["RB", "WR", "TE"]
    assert (params["season"], params["week"]) == (2026, 10)


def test_serving_positions_are_exactly_the_ones_nfl_volume_v1_fits() -> None:
    fitted = {position for position, _ in NFL_VOLUME_V1_PARAMETERS.position_rate}
    assert set(VOLUME_SERVING_POSITIONS) == fitted


def test_history_is_batched_once_for_every_player_with_the_named_floor() -> None:
    session = _Session([_line_row(), _line_row(id=901, player_id=8)], [])
    _load(session)

    assert len(session.calls) == 2
    sql, params = session.calls[1]
    assert params["player_ids"] == [7, 8]
    assert params["first_history_season"] == 2025
    assert "g.season BETWEEN :first_history_season AND :season" in sql
    assert "ANY(CAST(:player_ids AS bigint[]))" in sql


def test_the_history_floor_never_drops_below_the_named_constant() -> None:
    session = _Session([_line_row()], [])
    _load(session, season=2019)
    assert session.calls[1][1]["first_history_season"] == VOLUME_FIRST_HISTORY_SEASON


def test_history_excludes_the_current_and_future_weeks_and_incomplete_games() -> None:
    sql = _sql()[1]
    assert "g.game_type = 'REG' AND g.status = 'completed'" in sql
    assert "(g.season < :season OR g.week < :week)" in sql
    assert "g.week <= :week" not in sql


def test_team_attempts_follow_the_game_week_roster_unless_it_is_not_in_the_game() -> None:
    sql = _sql()[1]
    assert "r.player_id = s.player_id AND r.season = g.season AND r.week = g.week" in sql
    assert "CASE WHEN r.team_id IN (g.home_team_id, g.away_team_id) THEN r.team_id ELSE s.team_id END" in sql
    assert "SUM(s.passing_attempts) AS pass_attempts" in sql and "SUM(s.rushing_attempts) AS rush_attempts" in sql


def test_nothing_is_coalesced_and_null_stats_stay_none() -> None:
    sql_lines, sql_history = _sql()
    assert "coalesce" not in (sql_lines + sql_history).lower()

    [line] = _load(_Session([_line_row()], [_history_row()]))
    game = line.history[0]
    assert game.stats["passing_attempts"] is None and game.stats["receptions"] == 0.0
    assert (game.team_pass_attempts, game.team_rush_attempts) == (34.0, 26.0)


def test_a_future_scheduled_game_loads_without_outcome_stats() -> None:
    [line] = _load(_Session([_line_row(start_utc=KICKOFF)], []))
    assert line.history == () and line.line == 5.5 and line.start_utc == KICKOFF


def test_a_history_game_without_team_attempts_is_left_out() -> None:
    [line] = _load(_Session([_line_row()], [_history_row(pass_attempts=None), _history_row(game_id=41, week=8)]))
    assert [game.week for game in line.history] == [8]


def test_a_player_with_two_rows_in_one_game_raises() -> None:
    with pytest.raises(ValueError, match="more than one row"):
        _load(_Session([_line_row()], [_history_row(), _history_row()]))


def test_rows_are_typed_with_the_home_side_and_the_game_lines() -> None:
    [home] = _load(_Session([_line_row()], []))
    assert (home.is_home, home.opponent_team_id, home.home_spread_margin, home.total) == (True, 12, -3.5, 44.5)

    [away] = _load(_Session([_line_row(player_team_id=12)], []))
    assert (away.is_home, away.opponent_team_id) == (False, 11)


def test_a_player_not_in_the_game_has_no_side_and_a_missing_game_line_stays_none() -> None:
    [line] = _load(_Session([_line_row(player_team_id=99, spread_line=None, total_line=None)], []))
    assert (line.is_home, line.opponent_team_id, line.home_spread_margin, line.total) == (None, None, None, None)


def test_no_lines_means_no_history_query() -> None:
    session = _Session([])
    assert _load(session) == []
    assert len(session.calls) == 1
