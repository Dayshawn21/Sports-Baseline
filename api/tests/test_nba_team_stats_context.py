import asyncio
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock, Mock, call

import pytest
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_team_stats import TEAM_STATS, TeamBoxGame, TeamStatRate, team_stats
from app.core.nba_projection_backtest import NbaHistoryRow
from app.repositories import nba as repo
from app.repositories import nba_injuries as injury_repo
from app.routers import nba as router
from app.schemas.nba import NbaTeamStatsContextSchema
from app.services.nba import game_detail, line_only_props, prop_board, props
from app.services.nba.slate import slate_games
from app.services.nba.team_stats import load_team_stats, team_stats_schema

BEFORE = date(2026, 11, 1)


def _row(team: str = "BOS", **overrides: object) -> dict[str, object]:
    return {
        "game_id": 11, "season": 2026, "game_date": date(2026, 10, 25), "home_team": "BOS", "away_team": "NY",
        "home_score": 100, "away_score": 90, "player_rows": 10, "did_not_play": False,
        "team": team, "opponent": "NY" if team == "BOS" else "BOS",
        "points": 100 if team == "BOS" else 90, "rebounds": 40, "assists": 20, "threes_made": 10,
        "blocks": 5, **overrides,
    }


def _session(rows: Sequence[dict[str, object]]) -> AsyncMock:
    result = Mock()
    result.mappings.return_value = rows
    return AsyncMock(spec=AsyncSession, execute=AsyncMock(return_value=result))


def _read(rows: Sequence[dict[str, object]]) -> list[TeamBoxGame]:
    return asyncio.run(repo.get_team_box_games(_session(rows), 2026, BEFORE))


def _target(game_id: int, season: int = 2026, game_date: date = BEFORE) -> dict[str, object]:
    return {
        "game_id": game_id, "season": season, "game_date": game_date, "home_team": "BOS", "away_team": "NY",
        "week": 1, "game_type": "REG", "status": "scheduled", "start_utc": datetime(2026, 11, 1, 23, tzinfo=UTC),
        "home_team_name": "Boston Celtics", "away_team_name": "New York Knicks", "home_score": None, "away_score": None,
    }


def test_repository_uses_one_league_wide_grouped_read_with_strict_filters() -> None:
    db = _session([])
    assert asyncio.run(repo.get_team_box_games(db, 2026, BEFORE)) == []
    db.execute.assert_awaited_once()
    statement, params = db.execute.await_args.args
    sql = " ".join(str(statement).split())
    assert params == {"season": 2026, "before": BEFORE}
    for alias in ("g", "home", "away", "team", "opponent"):
        assert f"{alias}.sport = 'nba'" in sql
    for predicate in ("g.season = :season", "g.game_date < :before", "g.game_type = 'REG'", "g.status = 'completed'"):
        assert predicate in sql
    assert "GROUP BY s.game_id, s.team_id, s.opponent_team_id, s.did_not_play" in sql
    assert "LEFT JOIN side_totals" in sql
    assert "LEFT JOIN sport_teams team" in sql and "LEFT JOIN sport_teams opponent" in sql
    assert "sport_players" not in sql and "LIMIT" not in sql
    assert "team_id = :" not in sql and "player_id =" not in sql
    db.commit.assert_not_awaited()
    db.flush.assert_not_awaited()


def test_sql_rejects_partial_negative_or_wrong_season_player_totals_and_maps_threes() -> None:
    db = _session([])
    asyncio.run(repo.get_team_box_games(db, 2026, BEFORE))
    sql = " ".join(str(db.execute.await_args.args[0]).split())
    for stat in TEAM_STATS:
        column = "three_pointers_made" if stat == "threes_made" else stat
        assert (
            f"CASE WHEN COUNT(*) FILTER ( WHERE s.{column} IS NULL OR s.{column} < 0 OR s.season <> g.season )"
            f" > 0 THEN NULL ELSE SUM(s.{column}) END AS {stat}"
        ) in sql
    assert "COALESCE" not in sql
    assert "NOT s.did_not_play" not in sql


def test_repository_maps_grouped_sides_dnp_and_no_box_games_without_losing_coverage() -> None:
    games = _read([
        _row(), _row("NY"),
        _row(player_rows=3, did_not_play=True, **{stat: None for stat in TEAM_STATS}),
        _row(game_id=12, player_rows=None, team=None, opponent=None, did_not_play=None,
             **{stat: None for stat in TEAM_STATS}),
    ])
    assert len(games) == 2 and len(games[0].sides) == 3 and games[1].sides == ()
    assert games[0].sides[0].team == "BOS" and games[0].sides[1].opponent == "BOS"
    assert games[0].sides[2].did_not_play
    stats = team_stats(games, 2026, BEFORE)
    assert stats["BOS"].completed_games == 2
    assert stats["BOS"].stats["points"].for_ == TeamStatRate(100.0, 1, 1, 2)


@pytest.mark.parametrize("bad_side", [
    {"points": None}, {"points": 99}, {"team": "LAL"}, {"opponent": "LAL"}, {"team": None},
])
def test_malformed_grouped_sides_never_supply_partial_game_rates(bad_side: dict[str, object]) -> None:
    stats = team_stats(_read([_row(**bad_side), _row("NY")]), 2026, BEFORE)
    assert stats["BOS"].completed_games == 1
    assert stats["BOS"].stats["points"].for_ == TeamStatRate(None, None, 0, 0)


def test_null_metric_is_paired_and_zero_remains_observed() -> None:
    stats = team_stats(_read([_row(blocks=None, threes_made=0), _row("NY", threes_made=0)]), 2026, BEFORE)
    assert stats["BOS"].stats["blocks"].for_ == TeamStatRate(None, None, 0, 0)
    assert stats["NY"].stats["blocks"].allowed == TeamStatRate(None, None, 0, 0)
    assert stats["BOS"].stats["threes_made"].for_ == TeamStatRate(0.0, 1, 1, 2)


def test_service_batches_targets_by_season_date_and_selects_game_teams(monkeypatch: pytest.MonkeyPatch) -> None:
    history = _read([_row(), _row("NY"),
                     _row(game_id=12, home_team="LAL", away_team="GS", team="LAL", opponent="GS", points=100),
                     _row(game_id=12, home_team="LAL", away_team="GS", team="GS", opponent="LAL", points=90)])
    reader = AsyncMock(return_value=history)
    monkeypatch.setattr(repo, "get_team_box_games", reader)
    db = cast(AsyncSession, Mock())
    contexts = asyncio.run(load_team_stats(db, [_target(1), _target(2)]))
    reader.assert_awaited_once_with(db, 2026, BEFORE)
    assert set(contexts) == {1, 2} and contexts[1] == contexts[2]
    context = contexts[1]
    assert context.season == 2026 and context.before_date == BEFORE
    assert context.basis == "stored_player_box_scores"
    assert context.home.team == "BOS" and context.away.team == "NY"
    assert context.home.stats["points"].for_.ranked_teams == 4
    assert context.home.stats["points"].allowed.per_game == 90


def test_service_reads_each_distinct_season_date_once(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = AsyncMock(return_value=[])
    monkeypatch.setattr(repo, "get_team_box_games", reader)
    db = cast(AsyncSession, Mock())
    tomorrow = date(2026, 11, 2)
    contexts = asyncio.run(load_team_stats(db, [
        _target(1), _target(2, season=2025), _target(3, game_date=tomorrow), _target(4),
    ]))
    assert reader.await_args_list == [call(db, 2026, BEFORE), call(db, 2025, BEFORE), call(db, 2026, tomorrow)]
    assert contexts[2].season == 2025 and contexts[3].before_date == tomorrow
    assert contexts[1].home.completed_games == 0
    assert contexts[1].home.stats["points"].for_ == TeamStatRate(None, None, 0, 0)


def test_empty_targets_skip_history_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = AsyncMock()
    monkeypatch.setattr(repo, "get_team_box_games", reader)
    assert asyncio.run(load_team_stats(cast(AsyncSession, Mock()), [])) == {}
    reader.assert_not_awaited()


def test_service_propagates_repository_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(repo, "get_team_box_games", AsyncMock(side_effect=RuntimeError("unavailable")))
    with pytest.raises(RuntimeError, match="unavailable"):
        asyncio.run(load_team_stats(cast(AsyncSession, Mock()), [_target(1)]))


def _line(market: str = "assists", value: float = 4.5) -> dict[str, object]:
    return {"player_id": 1, "player_name": "Player", "position": "G", "team": "NYK", "market": market,
            "odds_type": "standard", "line": value, "fetched_at": datetime(2026, 11, 1, 18, tzinfo=UTC)}


def _prior() -> dict[int, list[NbaHistoryRow]]:
    return {1: [
        NbaHistoryRow(player_id=1, game_id=day, season=2026, game_date=BEFORE - timedelta(days=day),
                      game_type="REG", did_not_play=False, minutes=32.0,
                      stats={"points": 20, "assists": 5, "rebounds": 6})
        for day in range(1, 21)
    ]}


def _assembly(monkeypatch: pytest.MonkeyPatch, history: list[TeamBoxGame]) -> AsyncMock:
    modelled, plain = [_line(), _line("points", 20.5), _line(value=6.5)], [_line("double_double", 0.5)]
    for name, result in {
        "get_game": _target(1), "get_game_dates": [BEFORE], "get_games_on": [_target(1)],
        "get_modelled_lines": modelled, "get_line_only_lines": plain,
        "get_date_modelled_lines": {1: modelled}, "get_date_line_only_lines": {1: plain},
        "get_prior_games": _prior(), "get_recent_box_scores": [], "get_game_line_history": [],
    }.items():
        monkeypatch.setattr(repo, name, AsyncMock(return_value=result))
    monkeypatch.setattr(injury_repo, "get_game_snapshots", AsyncMock(return_value={}))
    monkeypatch.setattr(game_detail, "assemble_games", AsyncMock(return_value=slate_games([_target(1)], [], {2026: {}})))
    reader = AsyncMock(return_value=history)
    monkeypatch.setattr(repo, "get_team_box_games", reader)
    return reader


@pytest.mark.parametrize("has_history", [False, True])
def test_all_four_assemblies_serve_identical_context_and_unchanged_lines(
    monkeypatch: pytest.MonkeyPatch, has_history: bool,
) -> None:
    history = _read([_row(), _row("NY")]) if has_history else []
    reader = _assembly(monkeypatch, history)
    db = cast(AsyncSession, object())
    now = datetime(2026, 11, 1, 20, tzinfo=UTC)
    modelled = asyncio.run(props.build_props(db, 1, now))
    plain = asyncio.run(line_only_props.build_line_only_props(db, 1, now))
    detail = asyncio.run(game_detail.build_game_detail(db, 1, now))
    board = asyncio.run(prop_board.build_prop_board(db, BEFORE, BEFORE, now))
    assert modelled is not None and plain is not None and detail is not None
    context = modelled.team_stats
    assert context is not None and context == plain.team_stats == detail.team_stats == board.games[0].team_stats
    assert reader.await_args_list == [call(db, 2026, BEFORE)] * 4
    assert context.home.team == "BOS" and context.away.team == "NY"
    assert context.home.completed_games == int(has_history)
    assert context.home.stats["points"].for_.per_game == (100.0 if has_history else None)
    assert board.games[0].lines == modelled.lines and board.games[0].line_only_lines == plain.lines
    assert any(line.p_over is not None for line in modelled.lines)
    modelled_before = props.props_response(1, [_line(), _line("points", 20.5), _line(value=6.5)], _prior(), [])
    plain_before = line_only_props.line_only_props(1, [_line("double_double", 0.5)], [])
    assert modelled.model_dump(exclude={"team_stats"}) == modelled_before.model_dump(exclude={"team_stats"})
    assert plain.model_dump(exclude={"team_stats"}) == plain_before.model_dump(exclude={"team_stats"})
    slate = slate_games([_target(1)], [], {2026: {}})[0]
    assert detail.model_dump(exclude={"team_stats"}) == game_detail.game_detail(slate, []).model_dump(exclude={"team_stats"})


def test_context_wire_shape_preserves_stat_keys_and_for_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    _assembly(monkeypatch, _read([_row(threes_made=0), _row("NY")]))
    context = asyncio.run(load_team_stats(cast(AsyncSession, object()), [_target(1)]))[1]
    schema = team_stats_schema(context)
    payload = schema.model_dump(mode="json", by_alias=True)
    assert payload.keys() == {"season", "beforeDate", "basis", "away", "home"}
    assert payload["beforeDate"] == "2026-11-01"
    assert payload["home"].keys() == {"team", "completedGames", "stats"}
    assert payload["home"]["stats"].keys() == set(TEAM_STATS)
    assert payload["home"]["stats"]["threes_made"] == {
        "for": {"perGame": 0.0, "rank": 2, "games": 1, "rankedTeams": 2},
        "allowed": {"perGame": 10.0, "rank": 2, "games": 1, "rankedTeams": 2},
    }
    assert NbaTeamStatsContextSchema.model_validate(payload) == schema
    del payload["home"]["stats"]["blocks"]
    with pytest.raises(ValidationError, match="all five measures"):
        NbaTeamStatsContextSchema.model_validate(payload)


@pytest.mark.parametrize("endpoint", [router.get_game, router.get_game_props, router.get_game_line_only_props])
def test_not_found_routes_do_not_read_team_history(
    monkeypatch: pytest.MonkeyPatch, endpoint: Callable[[int, AsyncSession], Awaitable[BaseModel]],
) -> None:
    monkeypatch.setattr(repo, "get_game", AsyncMock(return_value=None))
    reader = AsyncMock()
    monkeypatch.setattr(repo, "get_team_box_games", reader)
    with pytest.raises(HTTPException) as error:
        asyncio.run(endpoint(999, cast(AsyncSession, object())))
    assert error.value.status_code == 404
    reader.assert_not_awaited()
