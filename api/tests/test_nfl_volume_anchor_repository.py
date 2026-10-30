import asyncio
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.core.nfl_volume_projection import VOLUME_FIRST_HISTORY_SEASON
from app.nfl.markets import STANDARD_ODDS_TYPE
from app.repositories.nfl_volume_anchor import AnchorLine, get_anchor_history, get_anchor_lines

FETCHED = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)


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


def _row(**overrides: object) -> dict[str, object]:
    return {
        "line_id": 900, "player_id": 7, "game_id": 50, "season": 2026, "week": 5, "position": "WR",
        "team_id": 11, "home_team_id": 11, "line": Decimal("5.5"), "fetched_at": FETCHED, "receptions": Decimal("6"),
    } | overrides


def _lines(session: _Session, season: int = 2026, first: int = 1, last: int = 8) -> list[AnchorLine]:
    return asyncio.run(get_anchor_lines(cast(AsyncSession, session), season, first, last))


def _sql() -> str:
    session = _Session([])
    _lines(session)
    return session.calls[0][0]


def test_every_shared_table_alias_is_filtered_to_nfl() -> None:
    sql = _sql()
    aliases = re.findall(r"(?:sport_games|sport_players|sport_prop_lines) (\w+)", sql)
    assert sorted(aliases) == ["g", "l", "p"]
    for alias in aliases:
        assert f"{alias}.sport = 'nfl'" in sql


def test_only_standard_full_game_receptions_lines_before_kickoff() -> None:
    session = _Session([])
    _lines(session)
    sql, params = session.calls[0]

    assert "l.segment = 'full_game'" in sql and "l.odds_type = :odds_type" in sql and "l.market = :market" in sql
    assert "l.fetched_at < g.start_utc" in sql and "g.game_type = 'REG'" in sql
    assert params["market"] == "receptions" and params["odds_type"] == STANDARD_ODDS_TYPE
    assert (params["season"], params["first_week"], params["last_week"]) == (2026, 1, 8)


def test_one_row_per_player_game_keeps_the_newest_snapshot() -> None:
    sql = _sql()
    assert "DISTINCT ON (l.player_id, l.game_id)" in sql
    assert "ORDER BY l.player_id, l.game_id, l.fetched_at DESC, l.id DESC" in sql


def test_results_count_only_once_the_game_is_completed_and_are_never_coalesced() -> None:
    sql = _sql()
    assert "CASE WHEN g.status = 'completed' THEN s.receptions END" in sql
    assert "coalesce" not in sql.lower()


def test_a_null_result_stays_null_and_rows_are_typed() -> None:
    lines = _lines(_Session([_row(receptions=None, team_id=12)]))

    assert lines == [AnchorLine(
        line_id=900, player_id=7, game_id=50, season=2026, week=5, team_id=12, is_home=False,
        position="WR", line=5.5, fetched_at=FETCHED, receptions=None,
    )]
    assert _lines(_Session([_row()]))[0].receptions == 6.0


def test_a_missing_team_leaves_the_home_side_unknown() -> None:
    line = _lines(_Session([_row(team_id=None)]))[0]
    assert line.team_id is None and line.is_home is None


def test_the_roster_side_team_wins_unless_it_is_not_in_the_game() -> None:
    assert "CASE WHEN r.team_id IN (g.home_team_id, g.away_team_id) THEN r.team_id ELSE s.team_id END" in _sql()


def test_seasons_before_2026_and_reversed_weeks_are_refused() -> None:
    with pytest.raises(ValueError, match="before 2026"):
        _lines(_Session(), season=2025)
    with pytest.raises(ValueError, match="last_week"):
        _lines(_Session(), first=8, last=1)


def test_history_is_read_from_the_named_floor_through_the_fit_season() -> None:
    session = _Session([], [])
    asyncio.run(get_anchor_history(cast(AsyncSession, session), 2026))

    for sql, params in session.calls:
        assert "g.season BETWEEN :first_season AND :last_season" in sql
        assert (params["first_season"], params["last_season"]) == (VOLUME_FIRST_HISTORY_SEASON, 2026)
    with pytest.raises(ValueError, match="before 2026"):
        asyncio.run(get_anchor_history(cast(AsyncSession, _Session()), 2025))
