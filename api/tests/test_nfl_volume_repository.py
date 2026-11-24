import asyncio
import re
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.core.nfl_volume_projection import VOLUME_FIRST_HISTORY_SEASON
from app.core.nfl_volume_backtest import VOLUME_STATS, VolumeHistory
from app.repositories.nfl_volume import get_volume_history


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


def _player_row(**overrides: object) -> dict[str, object]:
    return {
        "player_id": 7, "game_id": 50, "season": 2019, "week": 3, "position": "WR", "team_id": 11,
        "home_team_id": 11, **{stat: None for stat in VOLUME_STATS},
        "targets": 8, "receptions": 0, "receiving_yards": Decimal("0"), "target_share": 0.25, "offense_snaps": 51,
    } | overrides


def _team_row(**overrides: object) -> dict[str, object]:
    return {
        "game_id": 50, "team_id": 11, "season": 2019, "week": 3, "is_home": True,
        "pass_attempts": Decimal("36"), "rush_attempts": Decimal("24"), "plays": 63,
        "spread_line": Decimal("-3.5"), "total_line": Decimal("44.5"),
    } | overrides


def _load(session: _Session, first: int = 2018, last: int = 2025) -> VolumeHistory:
    return asyncio.run(get_volume_history(cast(AsyncSession, session), first, last))


def _sql() -> tuple[str, str]:
    session = _Session([], [])
    _load(session)
    return session.calls[0][0], session.calls[1][0]


def test_every_shared_table_alias_is_filtered_to_nfl() -> None:
    for sql in _sql():
        for alias in re.findall(r"(?:sport_games|sport_players|sport_teams) (\w+)", sql):
            assert f"{alias}.sport = 'nfl'" in sql


def test_both_queries_read_completed_regular_season_games_in_the_season_range() -> None:
    session = _Session([], [])
    _load(session, 2018, 2024)

    for sql, params in session.calls:
        assert "g.game_type = 'REG'" in sql and "g.status = 'completed'" in sql
        assert "g.season BETWEEN :first_season AND :last_season" in sql
        assert params["first_season"] == 2018 and params["last_season"] == 2024


def test_the_player_query_reads_only_modelled_positions() -> None:
    session = _Session([], [])
    _load(session)

    assert session.calls[0][1]["positions"] == ["QB", "RB", "TE", "WR"]


def test_the_team_comes_from_the_game_week_roster_unless_it_is_not_in_the_game() -> None:
    player_sql, _ = _sql()

    assert "r.player_id = s.player_id AND r.season = g.season AND r.week = g.week" in player_sql
    assert "CASE WHEN r.team_id IN (g.home_team_id, g.away_team_id) THEN r.team_id ELSE s.team_id END" in player_sql


def test_nullable_stats_are_never_coalesced_and_stay_none() -> None:
    player_sql, team_sql = _sql()
    assert "coalesce" not in (player_sql + team_sql).lower()

    history = _load(_Session([_player_row(offense_snaps=None, target_share=None)], [_team_row(plays=None)]))
    game = history.player_games[0]
    assert game.stats["passing_attempts"] is None and game.stats["receptions"] == 0.0
    assert game.target_share is None and game.offense_snaps is None
    assert history.team_games[0].plays is None


def test_rows_are_typed_with_home_side_and_closing_lines() -> None:
    history = _load(_Session([_player_row(team_id=12)], [_team_row(team_id=12, is_home=False)]))

    player = history.player_games[0]
    assert (player.team_id, player.is_home, player.stats["targets"]) == (12, False, 8.0)
    team = history.team_games[0]
    assert (team.pass_attempts, team.rush_attempts, team.plays) == (36.0, 24.0, 63)
    assert (team.home_spread_margin, team.total, team.is_home) == (-3.5, 44.5, False)


def test_a_player_with_two_rows_in_one_game_raises() -> None:
    with pytest.raises(ValueError, match="more than one row"):
        _load(_Session([_player_row(), _player_row()], []))


def test_a_first_season_before_the_floor_or_after_the_last_is_refused() -> None:
    with pytest.raises(ValueError, match="history floor"):
        _load(_Session(), VOLUME_FIRST_HISTORY_SEASON - 1, 2025)
    with pytest.raises(ValueError):
        _load(_Session(), 2024, 2023)
