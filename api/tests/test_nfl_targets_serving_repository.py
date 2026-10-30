"""Live targets inputs stay independent of outcomes and preserve pre-week evidence."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from math import isnan
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_baseline import PROJECTION_FIRST_HISTORY_SEASON
from app.core.nfl_availability import NflAvailability
from app.core.nfl_targets_projection import project_targets
from app.repositories.nfl import _AVAILABILITY_CTE, _player_teams_cte
from app.repositories.nfl_targets import get_targets_serving_lines, get_unmatched_targets_lines
from tests.test_nfl_targets_repository import _Session, _history

KICKOFF = datetime(2026, 10, 25, 17, tzinfo=UTC)
FETCHED = datetime(2026, 10, 24, 15, tzinfo=UTC)


def _line(**overrides: object) -> dict[str, object]:
    return {
        "id": 70, "game_id": 50, "player_id": 7, "player_name": "Receiver", "position": "WR",
        "player_team_id": 2, "opponent_team_id": 3, "opponent_team": "BUF", "start_utc": KICKOFF,
        "market": "receiving_targets", "segment": "full_game", "odds_type": "standard",
        "line": Decimal("5.5"), "provider": "prizepicks", "fetched_at": FETCHED,
        "injury_status": None, "practice_status": None, "injury": None,
        "depth_team_id": None, "depth_position": None, "depth_rank": None,
        "previous_depth_team_id": None, "previous_depth_position": None, "previous_depth_rank": None,
    } | overrides


def test_an_empty_targets_board_does_not_load_history() -> None:
    session = _Session([])

    assert asyncio.run(get_targets_serving_lines(cast(AsyncSession, session), 2026, 7)) == []
    assert len(session.calls) == 1 and session.responses == []


def test_serving_selects_eligible_snapshots_before_the_latest_row_without_requiring_results() -> None:
    session = _Session([])
    asyncio.run(get_targets_serving_lines(cast(AsyncSession, session), 2026, 7))

    (sql, params), = session.calls
    assert params == {"season": 2026, "week": 7}
    latest = sql.split("ORDER BY l.provider, l.provider_prop_id", 1)[0]
    for restriction in (
        "g.sport = 'nfl' AND g.id = l.game_id", "p.sport = 'nfl' AND p.id = l.player_id",
        "l.sport = 'nfl' AND l.market = 'receiving_targets'",
        "g.season = :season AND g.week = :week AND g.week BETWEEN 1 AND 18",
        "g.game_type = 'REG' AND l.segment = 'full_game' AND l.odds_type = 'standard'",
        "l.provider_prop_id IS NOT NULL", "p.position IN ('RB', 'WR', 'TE')",
        "g.start_utc IS NULL OR l.fetched_at < g.start_utc",
    ):
        assert restriction in latest
    assert "DISTINCT ON (l.provider, l.provider_prop_id)" in latest
    assert "ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC" in sql
    assert "WHERE l.player_id IS NOT NULL" in sql
    assert "g.status" not in sql and "nfl_player_weekly_stats" not in sql
    assert "actual" not in sql and "home_moneyline" not in sql


def test_serving_reuses_bounded_rosters_and_display_availability() -> None:
    session = _Session([])
    asyncio.run(get_targets_serving_lines(cast(AsyncSession, session), 2026, 7))

    sql, _ = session.calls[0]
    assert " ".join(_player_teams_cte().split()) in sql
    assert " ".join(_AVAILABILITY_CTE.split()) in sql
    assert "WHEN pt.team_id = l.home_team_id THEN away.team_code" in sql
    assert "WHEN pt.team_id = l.away_team_id THEN home.team_code" in sql
    assert "LEFT JOIN player_teams pt" in sql
    assert "home.sport = 'nfl'" in sql and "away.sport = 'nfl'" in sql


def test_serving_maps_future_game_identity_and_availability_without_current_week_stats() -> None:
    session = _Session([_line(
        injury_status="Questionable", practice_status="Limited", injury="Ankle",
        depth_team_id=2, depth_position="WR", depth_rank=1,
        previous_depth_team_id=2, previous_depth_position="WR", previous_depth_rank=2,
    )], [])

    line, = asyncio.run(get_targets_serving_lines(cast(AsyncSession, session), 2026, 7))

    assert (line.line_id, line.game_id, line.player_id, line.player_name, line.position) == (70, 50, 7, "Receiver", "WR")
    assert (line.player_team_id, line.opponent_team_id, line.opponent_team) == (2, 3, "BUF")
    assert (line.market, line.segment, line.odds_type, line.provider) == (
        "receiving_targets", "full_game", "standard", "prizepicks",
    )
    assert (line.start_utc, line.fetched_at, line.line) == (KICKOFF, FETCHED, 5.5)
    assert (line.input.season, line.input.week, line.history, line.input.observations) == (2026, 7, (), ())
    assert line.input.home_market_prob is None and line.input.player_is_home is None
    assert line.availability == NflAvailability("Questionable", 2, "WR", 1, 2, "WR", 2)
    assert (line.practice_status, line.injury) == ("Limited", "Ankle")
    assert not hasattr(line, "actual")


def test_history_is_batched_once_for_distinct_players_and_keeps_opponent_context() -> None:
    session = _Session(
        [_line(player_id=9), _line(), _line(id=71)],
        [_history(season=2026, opponent_team_id=4, opponent_team="DET"),
         _history(player_id=9, season=2025, targets=Decimal("2"), opponent_team_id=None, opponent_team=None)],
    )

    other, first, second = asyncio.run(get_targets_serving_lines(cast(AsyncSession, session), 2026, 7))

    assert len(session.calls) == 2
    sql, params = session.calls[1]
    assert params == {
        "season": 2026, "week": 7, "player_ids": [7, 9], "first_history_season": PROJECTION_FIRST_HISTORY_SEASON,
    }
    assert "g.game_type = 'REG' AND g.status = 'completed'" in sql
    assert "g.sport = 'nfl' AND g.id = s.game_id" in sql
    assert "g.season < :season OR (g.season = :season AND g.week < :week)" in sql
    assert "s.player_id = ANY(CAST(:player_ids AS bigint[]))" in sql
    assert "opponent.sport = 'nfl' AND opponent.id = s.opponent_team_id" in sql
    assert "g.start_utc DESC NULLS LAST, g.id DESC" in sql
    assert "COALESCE" not in sql and "LIMIT" not in sql and "target_share" not in sql
    assert first.history is second.history
    assert first.input.observations == second.input.observations
    assert first.input.observations[0].targets == 4.0 and other.input.observations[0].targets == 2.0
    assert (first.history[0].opponent_team_id, first.history[0].opponent_team) == (4, "DET")
    assert other.history[0].opponent_team is None


def test_invalid_counts_remain_invalid_and_future_weeks_cannot_enter_the_projection() -> None:
    history = [
        _history(season=2026, game_id=index, week=index, targets=value)
        for index, value in enumerate([0, 2, 4, 6, None, -1, float("nan"), float("inf")], start=1)
    ]
    history += [_history(season=2026, week=9, targets=100), _history(season=2027, targets=100)]
    session = _Session([_line()], history)

    line, = asyncio.run(get_targets_serving_lines(cast(AsyncSession, session), 2026, 9))

    values = [observation.targets for observation in line.input.observations]
    assert values[:6] == [0.0, 2.0, 4.0, 6.0, None, -1.0]
    invalid_count = values[6]
    assert invalid_count is not None and isnan(invalid_count)
    assert values[7] == float("inf")
    projection = project_targets(line.input)
    assert (projection.games_in_sample, projection.projection) == (4, 3.0)


@pytest.mark.parametrize("value", [None, Decimal("0"), Decimal("4.5")])
def test_unknown_and_zero_lines_remain_distinguishable(value: Decimal | None) -> None:
    session = _Session([_line(line=value, start_utc=None, player_team_id=None,
                              opponent_team_id=None, opponent_team=None)], [])

    line, = asyncio.run(get_targets_serving_lines(cast(AsyncSession, session), 2026, 7))

    assert line.line == (float(value) if value is not None else None)
    assert line.start_utc is None and line.opponent_team is None
    assert line.availability == NflAvailability()
    assert project_targets(line.input).projection is None


@pytest.mark.parametrize("name", [None, "Unresolved Receiver"])
def test_unmatched_targets_keep_the_existing_display_contract_without_loading_history(name: str | None) -> None:
    session = _Session([_line(player_id=None, player_name=name, provider_team="CHI", provider_position="WR")])

    line, = asyncio.run(get_unmatched_targets_lines(cast(AsyncSession, session), 2026, 7))

    assert (line.line_id, line.game_id, line.player_name) == (70, 50, name or "Unknown player")
    assert (line.provider_team, line.provider_position, line.line) == ("CHI", "WR", 5.5)
    assert (line.market, line.segment, line.odds_type, line.fetched_at) == (
        "receiving_targets", "full_game", "standard", FETCHED,
    )
    (sql, params), = session.calls
    assert params == {"season": 2026, "week": 7}
    assert "WHERE player_id IS NULL" in sql
    assert "l.market = 'receiving_targets'" in sql and "l.odds_type = 'standard'" in sql
    assert "raw_json ->> 'player_name'" in sql and "nfl_player_weekly_stats" not in sql


def test_empty_unmatched_targets_return_no_rows() -> None:
    session = _Session([])
    assert asyncio.run(get_unmatched_targets_lines(cast(AsyncSession, session), 2026, 7)) == []
