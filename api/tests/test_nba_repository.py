import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.core.nba_line_only import LINE_ONLY_COLUMNS
from app.core.nba_projection_backtest import NbaHistoryRow
from app.core.nba_prop_predictions import NbaFreezeLine
from app.core.prop_ranking_check import FrozenLine
from app.repositories.nba import (
    NBA_MODELLED_MARKET_FILTER, get_current_week, get_finished_weeks, get_frozen_coverage, get_frozen_gradeable_lines,
    get_date_line_only_lines, get_date_modelled_lines,
    get_line_only_lines, get_modelled_lines, get_prior_games, get_projection_history, get_week_modelled_lines,
)


class _Result:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self) -> list[dict[str, object]]:
        return self.rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return [tuple(row.values()) for row in self.rows]


class _RecordingSession:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.statement = ""
        self.params: dict[str, object] = {}

    async def execute(self, statement: TextClause, params: dict[str, object] | None = None) -> _Result:
        self.statement = str(statement)
        self.params = params or {}
        return _Result(self.rows)


def _row(**overrides: object) -> dict[str, object]:
    stats: dict[str, object] = {column: 0 for column in LINE_ONLY_COLUMNS}
    return {
        "player_id": 7, "game_id": 11, "season": 2024, "game_date": date(2024, 10, 22), "game_type": "REG",
        "did_not_play": False, "minutes": 31.5, **stats, "points": 24, **overrides,
    }


def test_projection_history_reads_served_nba_games_of_the_seasons() -> None:
    session = _RecordingSession([])

    assert asyncio.run(get_projection_history(cast(AsyncSession, session), (2024, 2025))) == []

    assert session.params == {"seasons": [2024, 2025]}
    assert "g.sport = 'nba'" in session.statement
    assert "g.game_type IN ('REG', 'PIN', 'PST')" in session.statement
    assert "PRE" not in session.statement
    assert "g.season = ANY(:seasons)" in session.statement
    assert "ORDER BY g.game_date, g.id, s.player_id" in session.statement
    # DNP rows stay in: the replay must see that a player sat.
    assert "did_not_play" in session.statement and "NOT s.did_not_play" not in session.statement


def test_projection_history_maps_rows_with_stats_readable_by_settlement() -> None:
    session = _RecordingSession([_row(), _row(player_id=8, did_not_play=True, minutes=None, points=None)])

    played, sat = asyncio.run(get_projection_history(cast(AsyncSession, session), (2024,)))

    assert isinstance(played, NbaHistoryRow)
    assert (played.player_id, played.game_id, played.season, played.game_type) == (7, 11, 2024, "REG")
    assert played.minutes == 31.5 and played.stats["points"] == 24 and played.stats["did_not_play"] is False
    assert set(played.stats) == {"did_not_play", *LINE_ONLY_COLUMNS}
    assert sat.did_not_play and sat.minutes is None and sat.stats["points"] is None


def test_the_modelled_filter_names_the_nine_projected_markets_only() -> None:
    assert NBA_MODELLED_MARKET_FILTER.startswith("l.market IN (")
    assert "'points_rebounds_assists'" in NBA_MODELLED_MARKET_FILTER and "'blocks'" in NBA_MODELLED_MARKET_FILTER
    assert NBA_MODELLED_MARKET_FILTER.count("'") == 18
    assert "double_double" not in NBA_MODELLED_MARKET_FILTER


def test_modelled_lines_read_nba_full_game_pre_tip_lines_in_modelled_markets() -> None:
    session = _RecordingSession([])

    assert asyncio.run(get_modelled_lines(cast(AsyncSession, session), 21320)) == []

    assert session.params == {"game_id": 21320}
    for alias in ("l", "g", "p"):
        assert f"{alias}.sport = 'nba'" in session.statement
    assert NBA_MODELLED_MARKET_FILTER in session.statement
    assert "double_double" not in session.statement
    assert "l.segment = 'full_game'" in session.statement
    assert "(g.start_utc IS NULL OR l.fetched_at < g.start_utc)" in session.statement
    assert "g.game_type IN ('REG', 'PIN', 'PST')" in session.statement


def test_line_only_lines_read_double_double_only() -> None:
    session = _RecordingSession([])

    asyncio.run(get_line_only_lines(cast(AsyncSession, session), 21318))

    assert "l.market IN ('double_double')" in session.statement
    assert NBA_MODELLED_MARKET_FILTER not in session.statement


DateLineReader = Callable[[AsyncSession, date], Awaitable[dict[int, list[dict[str, object]]]]]
GameLineReader = Callable[[AsyncSession, int], Awaitable[list[dict[str, object]]]]


def _prop_row(game_id: int = 11, player_id: int = 7) -> dict[str, object]:
    return {
        "player_id": player_id, "player_name": "Test Player", "position": "G", "team": "BOS",
        "market": "assists", "odds_type": "standard", "line": "4.5",
        "fetched_at": datetime(2026, 10, 20, 16, 30, tzinfo=UTC), "game_id": game_id,
    }


@pytest.mark.parametrize(("reader", "market_filter"), [
    (get_date_modelled_lines, NBA_MODELLED_MARKET_FILTER),
    (get_date_line_only_lines, "l.market IN ('double_double')"),
])
def test_date_lines_bind_date_and_keep_serving_filters(reader: DateLineReader, market_filter: str) -> None:
    session = _RecordingSession([])

    assert asyncio.run(reader(cast(AsyncSession, session), date(2026, 10, 20))) == {}

    assert session.params == {"game_date": date(2026, 10, 20)}
    assert "g.game_date = :game_date" in session.statement
    assert ":game_id" not in session.statement
    for alias in ("l", "g", "p"):
        assert f"{alias}.sport = 'nba'" in session.statement
    assert "l.segment = 'full_game'" in session.statement
    assert "g.game_type IN ('REG', 'PIN', 'PST')" in session.statement
    assert "(g.start_utc IS NULL OR l.fetched_at < g.start_utc)" in session.statement
    assert market_filter in session.statement
    assert "DISTINCT ON (l.provider, l.provider_prop_id)" in session.statement
    assert "ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC" in session.statement


@pytest.mark.parametrize("reader", [get_date_modelled_lines, get_date_line_only_lines])
def test_date_lines_group_games_preserve_line_order_and_strip_game_id(reader: DateLineReader) -> None:
    rows = [_prop_row(), _prop_row(game_id=12, player_id=8), _prop_row(player_id=9)]
    session = _RecordingSession(rows)

    grouped = asyncio.run(reader(cast(AsyncSession, session), date(2026, 10, 20)))

    assert grouped == {
        11: [{key: 4.5 if key == "line" else value for key, value in row.items() if key != "game_id"}
             for row in (rows[0], rows[2])],
        12: [{key: 4.5 if key == "line" else value for key, value in rows[1].items() if key != "game_id"}],
    }


@pytest.mark.parametrize("reader", [get_modelled_lines, get_line_only_lines])
def test_game_lines_keep_their_original_keys_and_numeric_line(reader: GameLineReader) -> None:
    row = _prop_row()

    lines = asyncio.run(reader(cast(AsyncSession, _RecordingSession([row])), 11))

    assert lines == [{key: 4.5 if key == "line" else value for key, value in row.items() if key != "game_id"}]


def test_prior_games_read_the_last_twenty_played_games_of_any_season() -> None:
    session = _RecordingSession([])

    assert asyncio.run(get_prior_games(cast(AsyncSession, session), [7], date(2026, 10, 20))) == {}

    assert session.params == {"player_ids": [7], "before": date(2026, 10, 20), "limit": 20}
    assert "g.sport = 'nba'" in session.statement
    assert "g.game_type IN ('REG', 'PIN', 'PST')" in session.statement
    assert "g.game_date < :before" in session.statement
    assert "NOT s.did_not_play" in session.statement
    assert "recency <= :limit" in session.statement
    # Serving uses every stored season (the depth 20g1 was scored on), so no season filter.
    assert "season =" not in session.statement and ":seasons" not in session.statement
    assert "ORDER BY player_id, recency DESC" in session.statement


def test_prior_games_group_by_player_oldest_first() -> None:
    rows = [_row(game_id=1, game_date=date(2025, 4, 1)), _row(game_id=2, game_date=date(2025, 10, 22), season=2025),
            _row(player_id=8, game_id=3)]
    session = _RecordingSession(rows)

    prior = asyncio.run(get_prior_games(cast(AsyncSession, session), [7, 8], date(2026, 10, 20)))

    assert [row.game_id for row in prior[7]] == [1, 2]
    assert [row.game_id for row in prior[8]] == [3]
    assert prior[7][0].minutes == 31.5 and prior[7][0].stats["points"] == 24


class _QueuedResult:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self.row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self.row


class _QueuedSession:
    """Answers each statement with the next queued row, recording every statement."""

    def __init__(self, *rows: tuple[object, ...] | None) -> None:
        self.rows = list(rows)
        self.statements: list[str] = []
        self.params: list[dict[str, object]] = []

    async def execute(self, statement: TextClause, params: dict[str, object] | None = None) -> _QueuedResult:
        self.statements.append(str(statement))
        self.params.append(params or {})
        return _QueuedResult(self.rows.pop(0))


NOW = datetime(2026, 10, 20, 16, 30, tzinfo=UTC)


def test_current_week_is_the_next_untipped_regular_season_game() -> None:
    session = _QueuedSession((2026, 1))

    assert asyncio.run(get_current_week(cast(AsyncSession, session), NOW)) == (2026, 1)

    (statement,) = session.statements
    assert session.params == [{"now": NOW}]
    assert "sport = 'nba'" in statement and "game_type = 'REG'" in statement
    assert "week IS NOT NULL" in statement
    # No grace after tip-off: freezing skips started games itself.
    assert "start_utc > :now" in statement and "cutoff" not in statement


def test_current_week_falls_back_to_the_latest_loaded_week() -> None:
    session = _QueuedSession(None, (2025, 25))

    assert asyncio.run(get_current_week(cast(AsyncSession, session), NOW)) == (2025, 25)
    assert "ORDER BY season DESC, week DESC" in session.statements[1]
    assert "sport = 'nba'" in session.statements[1] and "game_type = 'REG'" in session.statements[1]


def test_current_week_is_none_with_no_schedule() -> None:
    assert asyncio.run(get_current_week(cast(AsyncSession, _QueuedSession(None, None)), NOW)) is None


def test_week_lines_read_the_weeks_linked_pre_tip_modelled_lines() -> None:
    session = _RecordingSession([])

    assert asyncio.run(get_week_modelled_lines(cast(AsyncSession, session), 2026, 1)) == []

    assert session.params == {"season": 2026, "week": 1}
    for alias in ("l", "g"):
        assert f"{alias}.sport = 'nba'" in session.statement
    assert "g.season = :season AND g.week = :week AND g.game_type = 'REG'" in session.statement
    assert "PIN" not in session.statement and "PRE" not in session.statement
    assert "l.player_id IS NOT NULL" in session.statement
    assert "l.segment = 'full_game'" in session.statement
    assert NBA_MODELLED_MARKET_FILTER in session.statement
    assert "(g.start_utc IS NULL OR l.fetched_at < g.start_utc)" in session.statement
    assert "DISTINCT ON (l.provider, l.provider_prop_id)" in session.statement
    assert "ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC" in session.statement


def test_week_lines_map_to_freeze_lines() -> None:
    row = {"id": 501, "game_id": 9, "game_date": date(2026, 10, 20), "start_utc": NOW, "player_id": 7,
           "market": "assists", "odds_type": "standard", "line": "4.5", "fetched_at": NOW}

    (line,) = asyncio.run(get_week_modelled_lines(cast(AsyncSession, _RecordingSession([row])), 2026, 1))

    assert line == NbaFreezeLine(
        line_id=501, game_id=9, game_date=date(2026, 10, 20), start_utc=NOW, player_id=7, market="assists",
        odds_type="standard", line=4.5, fetched_at=NOW,
    )


def test_frozen_lines_read_each_props_latest_pre_tip_frozen_row_on_completed_regular_season_games() -> None:
    session = _RecordingSession([])

    assert asyncio.run(get_frozen_gradeable_lines(cast(AsyncSession, session), 2026)) == []

    assert session.params == {"season": 2026}
    for alias in ("p", "l", "g"):
        assert f"{alias}.sport = 'nba'" in session.statement
    assert "g.game_type = 'REG' AND g.week IS NOT NULL" in session.statement
    assert "g.status = 'completed'" in session.statement
    assert "l.segment = 'full_game'" in session.statement and NBA_MODELLED_MARKET_FILTER in session.statement
    assert "l.fetched_at < g.start_utc AND p.generated_at < g.start_utc" in session.statement
    assert "DISTINCT ON (l.provider, l.provider_prop_id)" in session.statement
    assert "l.fetched_at DESC, l.id DESC, p.generated_at DESC, p.id DESC" in session.statement
    assert "LEFT JOIN nba_player_game_stats s ON s.player_id = frozen.player_id AND s.game_id = frozen.game_id" in session.statement


def _frozen_row(**overrides: object) -> dict[str, object]:
    stats: dict[str, object] = {column: 0 for column in LINE_ONLY_COLUMNS}
    return {
        "id": 501, "market": "assists", "odds_type": "standard", "line": "4.5", "player_id": 7, "game_id": 9,
        "week": 1, "p_over": 0.41, "p_under": 0.59, "model_version": "nba-reference-v1",
        "over_probability_version": "nba-pover-v1", "has_box_row": True, "did_not_play": False, **stats,
        "assists": 6, "game_has_box_scores": True, **overrides,
    }


def test_a_frozen_row_maps_to_a_settled_frozen_line() -> None:
    (line,) = asyncio.run(get_frozen_gradeable_lines(cast(AsyncSession, _RecordingSession([_frozen_row()])), 2026))

    assert line == FrozenLine(
        line_id=501, period=1, player_id=7, game_id=9, market="assists", odds_type="standard", outcome="over",
        p_over=0.41, p_under=0.59, model_version="nba-reference-v1", over_probability_version="nba-pover-v1",
    )


def test_frozen_rows_settle_missing_players_and_unloaded_games_apart() -> None:
    rows = [
        _frozen_row(has_box_row=False, did_not_play=None, assists=None),
        _frozen_row(has_box_row=False, did_not_play=None, assists=None, game_has_box_scores=False),
    ]

    lines = asyncio.run(get_frozen_gradeable_lines(cast(AsyncSession, _RecordingSession(rows)), 2026))

    assert [line.outcome for line in lines] == ["void_dnp", "stats_not_loaded"]


def test_finished_weeks_need_every_game_settled_and_every_completed_game_loaded() -> None:
    session = _RecordingSession([{"week": 1}, {"week": 2}])

    assert asyncio.run(get_finished_weeks(cast(AsyncSession, session), 2026)) == {1, 2}

    assert session.params == {"season": 2026}
    assert "g.sport = 'nba'" in session.statement
    assert "g.game_type = 'REG' AND g.week IS NOT NULL" in session.statement
    assert "bool_and(g.status IN ('completed', 'postponed', 'canceled'))" in session.statement
    assert "g.status <> 'completed' OR EXISTS (SELECT 1 FROM nba_player_game_stats s WHERE s.game_id = g.id)" in session.statement


def test_frozen_coverage_counts_gradeable_modelled_lines_per_week() -> None:
    session = _RecordingSession([{"week": 1, "lines": 190, "frozen": 150}])

    assert asyncio.run(get_frozen_coverage(cast(AsyncSession, session), 2026)) == {1: (190, 150)}

    for alias in ("l", "g", "fl", "p"):
        assert f"{alias}.sport = 'nba'" in session.statement
    assert "g.status = 'completed'" in session.statement and "g.game_type = 'REG'" in session.statement
    assert "l.segment = 'full_game'" in session.statement and NBA_MODELLED_MARKET_FILTER in session.statement
    assert "p.generated_at < g.start_utc" in session.statement
