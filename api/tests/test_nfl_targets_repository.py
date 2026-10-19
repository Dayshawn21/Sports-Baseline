import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from math import isnan
from typing import cast

import pytest
from sqlalchemy import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.core.nfl_targets_projection import TargetsObservation, project_targets
from app.repositories.nfl import _player_teams_cte
from app.repositories.nfl_targets import get_targets_replay_rows

KICKOFF = datetime(2024, 10, 6, 17, tzinfo=UTC)


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


def _driver(**overrides: object) -> dict[str, object]:
    return {
        "player_id": 7, "game_id": 50, "week": 5, "position": "WR", "actual": 6,
        "home_moneyline": -150, "away_moneyline": 130, "player_is_home": True,
    } | overrides


def _history(**overrides: object) -> dict[str, object]:
    return {
        "player_id": 7, "game_id": 40, "season": 2024, "week": 4,
        "start_utc": KICKOFF, "targets": 4,
    } | overrides


def test_an_empty_week_skips_the_history_query() -> None:
    session = _Session([])

    assert asyncio.run(get_targets_replay_rows(cast(AsyncSession, session), 2024, 5)) == []
    assert len(session.calls) == 1
    assert session.responses == []


def test_driver_is_one_completed_regular_season_skill_player_game_without_target_filtering() -> None:
    session = _Session([])
    asyncio.run(get_targets_replay_rows(cast(AsyncSession, session), 2024, 5))

    (sql, params), = session.calls
    assert params == {"season": 2024, "week": 5}
    assert "FROM nfl_player_weekly_stats s" in sql
    assert "JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id" in sql
    assert "JOIN sport_players p ON p.sport = 'nfl' AND p.id = s.player_id" in sql
    assert "g.season = :season AND g.week = :week" in sql
    assert "g.game_type = 'REG' AND g.status = 'completed'" in sql
    assert "p.position IN ('RB', 'WR', 'TE')" in sql
    assert "s.targets::double precision AS actual" in sql
    assert "s.targets IS NOT NULL" not in sql and "s.targets >" not in sql
    assert "sport_prop_lines" not in sql and "UNNEST" not in sql.upper()
    assert "ORDER BY g.id, s.player_id" in sql


def test_team_side_reuses_the_slates_bounded_roster_rule_without_outcome_team() -> None:
    session = _Session([])
    asyncio.run(get_targets_replay_rows(cast(AsyncSession, session), 2024, 5))

    sql, _ = session.calls[0]
    assert " ".join(_player_teams_cte().split()) in sql
    assert "r.season < :season OR (r.season = :season AND r.week <= :week)" in sql
    assert "ORDER BY r.player_id, r.season DESC, r.week DESC" in sql
    assert "WHEN rl.player_id IS NULL THEN p.team_id" in sql
    assert "WHEN rl.status IN ('CUT', 'RET') THEN NULL" in sql
    assert "WHEN pt.team_id = g.home_team_id THEN TRUE" in sql
    assert "WHEN pt.team_id = g.away_team_id THEN FALSE ELSE NULL" in sql
    assert "s.team_id" not in sql


def test_history_is_batched_for_distinct_players_and_strictly_before_the_week() -> None:
    session = _Session([_driver(player_id=9), _driver(), _driver(game_id=51)], [])
    asyncio.run(get_targets_replay_rows(cast(AsyncSession, session), 2024, 5))

    assert len(session.calls) == 2
    sql, params = session.calls[1]
    assert params == {"season": 2024, "week": 5, "player_ids": [7, 9]}
    assert "JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id" in sql
    assert "s.player_id = ANY(CAST(:player_ids AS bigint[]))" in sql
    assert "g.game_type = 'REG' AND g.status = 'completed'" in sql
    assert "g.season < :season OR (g.season = :season AND g.week < :week)" in sql
    assert "g.start_utc DESC NULLS LAST, g.id DESC" in sql
    assert "target_share" not in sql and "COALESCE" not in sql.upper()
    assert "targets IS NOT NULL" not in sql
    assert "<= :week" not in sql


def test_typed_rows_separate_the_actual_from_projection_inputs_and_devig_the_close() -> None:
    session = _Session([_driver(actual=Decimal("6"))], [_history(targets=Decimal("4"))])

    row, = asyncio.run(get_targets_replay_rows(cast(AsyncSession, session), 2024, 5))

    assert (row.player_id, row.game_id, row.week, row.position, row.actual) == (7, 50, 5, "WR", 6.0)
    assert (row.input.season, row.input.week) == (2024, 5)
    assert row.input.observations == (TargetsObservation(40, 2024, 4, KICKOFF, 4.0),)
    assert row.input.home_market_prob == pytest.approx(0.5798319327731093)
    assert row.input.player_is_home is True
    assert not hasattr(row.input, "actual")


@pytest.mark.parametrize("actual", [None, 0, -1])
def test_unknown_zero_and_invalid_actuals_are_retained_for_coverage(actual: int | None) -> None:
    session = _Session([_driver(actual=actual)], [])

    row, = asyncio.run(get_targets_replay_rows(cast(AsyncSession, session), 2024, 5))

    assert row.actual == actual
    assert row.input.observations == ()
    assert project_targets(row.input).projection is None


def test_known_targets_survive_missing_share_and_unknown_history_stays_unknown() -> None:
    observations = [
        _history(game_id=game_id, week=game_id, targets=value, target_share=None)
        for game_id, value in enumerate([0, 2, 4, 6, None, -1], start=1)
    ]
    session = _Session([_driver(week=7)], observations)

    row, = asyncio.run(get_targets_replay_rows(cast(AsyncSession, session), 2024, 7))

    assert tuple(item.targets for item in row.input.observations) == (0.0, 2.0, 4.0, 6.0, None, -1.0)
    result = project_targets(row.input)
    assert result.games_in_sample == 4 and result.projection == 3.0


def test_nonfinite_history_and_actuals_are_preserved_for_the_scorers_invalid_counts() -> None:
    session = _Session([_driver(actual=float("nan"))], [_history(targets=float("nan"))])

    row, = asyncio.run(get_targets_replay_rows(cast(AsyncSession, session), 2024, 5))

    assert row.actual is not None and isnan(row.actual)
    value = row.input.observations[0].targets
    assert value is not None and isnan(value)


@pytest.mark.parametrize("side", [True, False, None])
def test_player_side_passes_through_including_unknown(side: bool | None) -> None:
    session = _Session([_driver(player_is_home=side)], [])

    row, = asyncio.run(get_targets_replay_rows(cast(AsyncSession, session), 2024, 5))

    assert row.input.player_is_home is side


@pytest.mark.parametrize(("home", "away"), [(None, 130), (-150, None), (0, 130)])
def test_unusable_moneylines_do_not_drop_a_case(home: int | None, away: int | None) -> None:
    session = _Session([_driver(home_moneyline=home, away_moneyline=away)], [])

    row, = asyncio.run(get_targets_replay_rows(cast(AsyncSession, session), 2024, 5))

    assert row.input.home_market_prob is None
    assert row.actual == 6.0


def test_each_player_gets_only_its_own_history_and_games_are_not_fanned_out() -> None:
    session = _Session(
        [_driver(), _driver(game_id=51), _driver(player_id=9, game_id=52, position="TE")],
        [_history(), _history(player_id=9, game_id=41, season=2023, targets=1)],
    )

    rows = asyncio.run(get_targets_replay_rows(cast(AsyncSession, session), 2024, 5))

    assert [(row.player_id, row.game_id) for row in rows] == [(7, 50), (7, 51), (9, 52)]
    assert rows[0].input.observations == rows[1].input.observations
    assert rows[0].input.observations[0].game_id == 40
    assert rows[2].input.observations == (TargetsObservation(41, 2023, 4, KICKOFF, 1.0),)
    for sql, _ in session.calls:
        assert sql.startswith(("WITH ", "SELECT "))
