import asyncio
from datetime import date
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nhl_player_values import nhl_stat_value
from app.core.nhl_projection_backtest import NhlHistoryRow
from app.nhl.markets import NhlLineOnlyMarket
from app.repositories.nhl import get_projection_history


class _Result:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> list[dict[str, object]]:
        return self._rows


class _RecordingSession:
    """Answers the skater query first and the goalie query second, as the loader asks them."""

    def __init__(self, skaters: list[dict[str, object]], goalies: list[dict[str, object]]) -> None:
        self.answers = [skaters, goalies]
        self.statements: list[str] = []
        self.params: list[dict[str, object]] = []

    async def execute(self, statement: object, params: dict[str, object] | None = None) -> _Result:
        self.statements.append(str(statement))
        self.params.append(params or {})
        return _Result(self.answers[len(self.statements) - 1])


def _skater(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "player_id": 7, "game_id": 11, "season": 2024, "game_date": date(2024, 10, 9), "game_type": "REG",
        "position": "C", "started": True, "goals": 1, "assists": 0, "points": 1, "shots": 4,
        "power_play_points": 0, "blocked_shots": 1, "plus_minus": -1, "hits": 2, "faceoffs_won": 9,
        "time_on_ice_seconds": 1110,
    }
    return {**row, **overrides}


def _goalie(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "player_id": 30, "game_id": 11, "season": 2024, "game_date": date(2024, 10, 9), "game_type": "REG",
        "position": "G", "started": True, "saves": 28, "goals_against": 2, "time_on_ice_seconds": 3600,
    }
    return {**row, **overrides}


def test_history_reads_served_nhl_games_of_the_named_seasons() -> None:
    session = _RecordingSession([], [])

    assert asyncio.run(get_projection_history(cast(AsyncSession, session), (2023, 2024))) == []

    assert len(session.statements) == 2
    assert "FROM nhl_skater_game_stats s" in session.statements[0]
    assert "FROM nhl_goalie_game_stats s" in session.statements[1]
    for statement in session.statements:
        assert "g.sport = 'nhl'" in statement and "p.sport = 'nhl'" in statement
        assert "g.game_type IN ('REG', 'PST')" in statement and "PRE" not in statement
        assert "g.season = ANY(:seasons)" in statement
        assert "ORDER BY g.game_date, g.id, s.player_id" in statement
    assert session.params == [{"seasons": [2023, 2024]}, {"seasons": [2023, 2024]}]


def test_history_has_no_default_seasons() -> None:
    try:
        asyncio.run(get_projection_history(cast(AsyncSession, _RecordingSession([], []))))  # type: ignore[call-arg]
    except TypeError:
        return
    raise AssertionError("the loader must not default its seasons")


def test_rows_carry_stats_that_settle_like_the_player_page() -> None:
    session = _RecordingSession([_skater(), _skater(player_id=8, shots=None, time_on_ice_seconds=None)], [_goalie()])

    skater, other, goalie = asyncio.run(get_projection_history(cast(AsyncSession, session), (2024,)))

    assert isinstance(skater, NhlHistoryRow) and not skater.is_goalie and skater.position == "C"
    assert nhl_stat_value(NhlLineOnlyMarket.SHOTS_ON_GOAL, skater.stats) == 4
    assert nhl_stat_value(NhlLineOnlyMarket.TIME_ON_ICE, skater.stats) == 18.5
    assert nhl_stat_value(NhlLineOnlyMarket.SHOTS_ON_GOAL, other.stats) is None
    assert nhl_stat_value(NhlLineOnlyMarket.TIME_ON_ICE, other.stats) is None
    assert goalie.is_goalie and goalie.started
    assert nhl_stat_value(NhlLineOnlyMarket.GOALIE_SAVES, goalie.stats) == 28
    assert nhl_stat_value(NhlLineOnlyMarket.GOALS_ALLOWED, goalie.stats) == 2


def test_skaters_and_goalies_are_merged_oldest_first() -> None:
    session = _RecordingSession(
        [_skater(game_id=12, game_date=date(2024, 10, 10))],
        [_goalie(), _goalie(player_id=31, started=False, game_id=12, game_date=date(2024, 10, 10))],
    )

    rows = asyncio.run(get_projection_history(cast(AsyncSession, session), (2024,)))

    assert [(row.game_date.day, row.is_goalie, row.player_id) for row in rows] == [(9, True, 30), (10, False, 7), (10, True, 31)]
    assert rows[2].started is False
