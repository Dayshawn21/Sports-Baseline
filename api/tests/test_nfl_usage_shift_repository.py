import asyncio
from typing import cast

from sqlalchemy import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.core.nfl_usage_shift import UsageShiftPlayer
from app.repositories.nfl import get_usage_shift_players


class _Result:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self) -> list[RowMapping]:
        return cast(list[RowMapping], self.rows)


class _Session:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(self, statement: TextClause, params: dict[str, object]) -> _Result:
        self.calls.append((" ".join(str(statement).split()), params))
        return _Result(self.rows)


def _row(player_id: int, **overrides: object) -> dict[str, object]:
    return {
        "player_id": player_id, "team_id": 11, "position": "RB", "depth_rank": 1, "is_out": False,
        "fresh": True, "games": 6, "carries": 14.5, "targets": 2.0, **overrides,
    }


def _load(rows: list[dict[str, object]]) -> tuple[dict, _Session]:
    session = _Session(rows)
    result = asyncio.run(get_usage_shift_players(cast(AsyncSession, session), 2024, 7))
    return result, session


def test_volume_reads_only_this_seasons_reg_weeks_before_the_week() -> None:
    _, session = _load([])

    sql, params = session.calls[0]
    assert params == {"season": 2024, "week": 7}
    volume = sql.split("volume AS (")[1].split("), last_game")[0]
    assert "g.season = :season AND g.week < :week AND g.game_type = 'REG'" in volume
    assert "position IN ('RB', 'WR', 'TE')" in sql
    assert "i.report_status = 'Out'" in sql


def test_rows_group_by_team_and_position_as_usage_shift_players() -> None:
    result, _ = _load([
        _row(1, is_out=True),
        _row(2, depth_rank=2, carries=6.0),
        _row(3, position="WR", depth_rank=None, is_out=True, fresh=False, games=0, carries=None, targets=None),
    ])

    assert result == {
        (11, "RB"): [
            UsageShiftPlayer(1, 1, True, True, 14.5, 2.0, 6),
            UsageShiftPlayer(2, 2, False, True, 6.0, 2.0, 6),
        ],
        (11, "WR"): [UsageShiftPlayer(3, None, True, False, None, None, 0)],
    }
