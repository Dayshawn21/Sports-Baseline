import asyncio
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.ingest.nflverse import NflversePlayerWeek
from app.ingest.nflverse_pbp import NflverseRedZoneGame, NflverseRedZoneSeason
from app.ingest.nflverse_depth_charts import NflverseDepthWeek
from app.ingest.nflverse_injuries import NflverseInjuryWeek
from app.ingest.nflverse_rosters import NflverseRosterWeek
from app.ingest.nflverse_snap_counts import NflverseSnapGame
from app.ingest.nflverse_team_efficiency import NflverseTeamEfficiency
from app.core.nfl_baseline import PROJECTION_FIRST_HISTORY_SEASON
from app.core.nfl_elo import NflEloGame, NflTeamEloRow
from app.core.nfl_line_grading import settle_line
from app.core.nfl_game_line_clv import ClvGame, OddsCandidate
from app.core.prop_ranking_check import FrozenLine
from app.core.nfl_game_lines import NflGameLineGame
from app.core.nfl_line_only import LINE_ONLY_COLUMNS
from app.nfl.markets import NflLineOnlyMarket, NflPropMarket
from app.core.nfl_td_backtest import NflSnapRow
from app.core.nfl_team_game_dvp import NflTeamGameTotals
from app.ingest.nflverse import NflverseGame
from app.repositories import nfl as nfl_repository
from app.repositories.nfl import get_current_week, get_environment_fit_games, get_unmatched_slate_lines, get_elo_games, get_gradeable_prop_lines, get_replay_rows, get_game_line_games, get_team_game_position_totals, replace_team_elo, upsert_game
from app.repositories.nfl import TeamEfficiencyWriteResult, get_slate_team_elo, get_team_efficiency, replace_team_efficiency
from app.repositories.nfl import SnapCountWriteResult, _attach_snap_history, get_slate_opponent_position_history, get_snap_rows, get_weekly_td_rows,replace_snap_counts,PlayerWeekWriteResult,_availability, RedZoneWriteResult, RosterWriteResult, get_team_schedule, replace_weekly_depth_charts, replace_weekly_injuries, _player_teams_cte, get_historical_player_baselines, get_player_candidates, replace_weekly_rosters, _optional_averages, _td_history, _usage, get_slate_lines, get_slate_matchup_context, get_slate_player_history, get_slate_prop_odds, get_upcoming_games_needing_weather, insert_game_weather_snapshot, insert_player_prop_odds_snapshot, upsert_weekly_stat, write_red_zone_usage


class _Result:
    def __init__(self, result_id: int = 0) -> None:
        self.result_id = result_id

    def mappings(self) -> list[dict[str, object]]:
        return []

    def fetchall(self) -> list[tuple[object, ...]]:
        return []

    def scalar_one(self) -> int:
        return self.result_id


class _RecordingSession:
    def __init__(self) -> None:
        self.statement = ""
        self.params: dict[str, object] = {}
        self.result_id = 0

    async def execute(
        self,
        statement: TextClause,
        params: dict[str, object] | None = None,
    ) -> _Result:
        self.statement = str(statement)
        self.params = params or {}
        return _Result(self.result_id)


def test_matchup_team_games_keep_pre_week_nfl_regular_season_filters_and_decode_attempts() -> None:
    from unittest.mock import AsyncMock, Mock

    result = Mock()
    result.fetchall.return_value = [
        (18, 20, 10, 240, 180, 90, 110, 60, 55, 3.0, -2.0, 30, 20,
         32, 28, 24, 30, date(2026, 10, 18), 123),
        (26, 10, 20, None, None, None, None, None, None, None, None, None, None,
         None, None, None, None, date(2026, 10, 18), 123),
    ]
    session = Mock()
    session.execute = AsyncMock(return_value=result)
    games = asyncio.run(nfl_repository.get_week_team_games(cast(AsyncSession, session), 2026, 7))
    assert (games[0].pass_attempts_for, games[0].pass_attempts_against) == (32, 28)
    assert (games[0].rush_attempts_for, games[0].rush_attempts_against) == (24, 30)
    assert (games[0].played_on, games[0].game_id) == (date(2026, 10, 18), 123)
    assert games[1].pass_attempts_for is None
    statement, params = session.execute.call_args.args
    sql = str(statement)
    assert params == {"season": 2026, "week": 7}
    assert sql.count("g.sport = 'nfl'") == 2
    assert sql.count("g.game_type = 'REG'") == 2
    assert sql.count("g.week < :week") == 2
    assert sql.count("g.status = 'completed'") == 2


def test_slate_inputs_use_one_pre_week_regular_season_cutoff() -> None:
    session = _RecordingSession()

    assert asyncio.run(get_slate_lines(cast(AsyncSession, session), 2026, 7)) == []

    assert session.params == {"season": 2026, "week": 7, "first_history_season": PROJECTION_FIRST_HISTORY_SEASON}
    assert session.statement.count("s.season < :season OR (s.season = :season AND s.week < :week)") == 4
    assert session.statement.count("g.game_type = 'REG'") >= 5
    assert "s.opponent_team_id AS defense_team_id" in session.statement
    assert "WHEN pt.team_id = g.home_team_id THEN g.away_team_id" in session.statement
    assert "WHEN pt.team_id = g.away_team_id THEN g.home_team_id" in session.statement
    assert "op.position IS NOT DISTINCT FROM p.position" in session.statement


def test_v4_history_ctes_ignore_seasons_before_the_validated_floor() -> None:
    session = _RecordingSession()

    asyncio.run(get_slate_lines(cast(AsyncSession, session), 2026, 7))

    for cte in ("baselines", "position_baselines", "opponent_position_baselines", "league_position_baselines"):
        body = _flat(session.statement.split(f"    {cte} AS (", 1)[1].split("\n    )", 1)[0])
        assert "AND s.season >= :first_history_season AND (s.season < :season" in body, cte
    assert session.params["first_history_season"] == 2024


def test_history_floor_binds_on_every_snap_and_td_query() -> None:
    rows: list[dict] = [{"player_id": 7, "position": "TE", "baseline_season": 2025}]
    snaps = _ScriptedSession([], [])
    asyncio.run(_attach_snap_history(cast(AsyncSession, snaps), 2026, 2, rows))
    tds = _ScriptedSession([], [])
    asyncio.run(_td_history(cast(AsyncSession, tds), 2026, 2, [7]))

    for sql, params in snaps.calls + tds.calls:
        assert "season >= :first_history_season" in sql
        assert params["first_history_season"] == PROJECTION_FIRST_HISTORY_SEASON


def test_opponent_allowed_history_ignores_seasons_before_the_floor() -> None:
    session = _RecordingSession()

    assert asyncio.run(get_slate_opponent_position_history(cast(AsyncSession, session), 2026, 7)) == {}

    assert "g.season >= :first_history_season AND (g.season < :season" in session.statement
    assert session.params == {"season": 2026, "week": 7, "first_history_season": PROJECTION_FIRST_HISTORY_SEASON}


def test_backtest_rows_include_historical_game_lines_and_home_side() -> None:
    session = _RecordingSession()

    assert asyncio.run(get_weekly_td_rows(cast(AsyncSession, session))) == []

    statement = _flat(session.statement)
    assert "g.total_line::double precision, g.spread_line::double precision" in statement
    assert "g.home_moneyline, g.away_moneyline" in statement
    assert "s.end_zone_targets" in statement
    assert "s.team_id = g.home_team_id" in statement


def _flat(statement: str) -> str:
    return " ".join(statement.split())


@pytest.mark.parametrize("consumer", ["linked", "unmatched"])
def test_slate_lines_select_the_latest_snapshot_before_kickoff(consumer: str) -> None:
    session = _RecordingSession()
    load_lines = get_slate_lines if consumer == "linked" else get_unmatched_slate_lines

    assert asyncio.run(load_lines(cast(AsyncSession, session), 2026, 7)) == []

    latest = _flat(session.statement.split("latest_lines AS (", 1)[1].split("\n    )", 1)[0])
    assert (session.params["season"], session.params["week"]) == (2026, 7)
    assert "SELECT DISTINCT ON (l.provider, l.provider_prop_id)" in latest
    assert "JOIN sport_games g ON g.sport = 'nfl' AND g.id = l.game_id" in latest
    assert (
        f"WHERE l.sport = 'nfl' AND {nfl_repository.V4_MARKET_FILTER} "
        "AND (g.start_utc IS NULL OR l.fetched_at < g.start_utc) ORDER BY"
    ) in latest
    assert latest.endswith("ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC")


def test_slate_team_comes_from_the_roster_as_of_the_slate_week() -> None:
    session = _RecordingSession()

    asyncio.run(get_slate_lines(cast(AsyncSession, session), 2026, 7))

    statement = _flat(session.statement)
    assert "r.season < :season OR (r.season = :season AND r.week <= :week)" in statement
    assert "pt.team_id AS player_team_id" in statement
    assert "JOIN player_teams pt ON pt.player_id = p.id" in statement
    # Every team decision in the slate goes through the roster rule, none through the stale column.
    assert "p.team_id =" not in statement


def test_slate_joins_this_weeks_injury_and_depth_and_an_earlier_depth_row() -> None:
    session = _RecordingSession()

    asyncio.run(get_slate_lines(cast(AsyncSession, session), 2026, 7))

    statement = _flat(session.statement)
    assert "FROM nfl_player_injuries WHERE season = :season AND week = :week" in statement
    assert "FROM nfl_player_depth_charts WHERE season = :season AND week = :week" in statement
    # Strictly earlier: the slate week's own chart must never count as the "previous" one.
    assert "WHERE season < :season OR (season = :season AND week < :week) ORDER BY player_id, season DESC, week DESC" in statement
    for join in ("LEFT JOIN week_injuries wi ON wi.player_id = p.id",
                 "LEFT JOIN week_depth wd ON wd.player_id = p.id",
                 "LEFT JOIN previous_depth pd ON pd.player_id = p.id"):
        assert join in statement


def test_availability_fields_pass_through_and_stay_null_when_absent() -> None:
    present = {
        "injury_status": "Questionable", "practice_status": "Limited Participation in Practice",
        "injury": "Hamstring", "depth_team_id": 7, "depth_position": "WR", "depth_rank": 2,
        "previous_depth_team_id": 7, "previous_depth_position": "WR", "previous_depth_rank": 1,
    }

    assert _availability(present) == present
    assert _availability(dict.fromkeys(present)) == dict.fromkeys(present)


def test_projection_players_are_placed_in_games_by_the_as_of_team() -> None:
    session = _RecordingSession()

    asyncio.run(get_historical_player_baselines(cast(AsyncSession, session), 2026, 7))

    statement = _flat(session.statement)
    assert "r.season < :season OR (r.season = :season AND r.week <= :week)" in statement
    assert "JOIN player_teams pt ON pt.team_id IN (g.home_team_id, g.away_team_id)" in statement
    assert "p.team_id IN" not in statement


def test_projection_career_averages_ignore_seasons_before_the_floor() -> None:
    session = _ScriptedSession([])

    asyncio.run(get_historical_player_baselines(cast(AsyncSession, session), 2026, 7))

    ((sql, params),) = session.calls
    assert "AND s.season >= :first_history_season AND (s.season < :season" in sql
    assert params == {"season": 2026, "week": 7, "first_history_season": PROJECTION_FIRST_HISTORY_SEASON}


def test_backtest_td_rows_ignore_seasons_before_the_floor() -> None:
    session = _RecordingSession()

    assert asyncio.run(get_weekly_td_rows(cast(AsyncSession, session))) == []

    assert "WHERE g.game_type = 'REG' AND s.season >= :first_history_season" in _flat(session.statement)
    assert session.params == {"first_history_season": PROJECTION_FIRST_HISTORY_SEASON}


def test_link_candidates_carry_the_latest_roster_team_with_no_week_bound() -> None:
    session = _RecordingSession()

    asyncio.run(get_player_candidates(cast(AsyncSession, session)))

    statement = _flat(session.statement)
    assert "JOIN player_teams pt ON pt.player_id = p.id" in statement
    assert "LEFT JOIN sport_teams t ON t.sport = 'nfl' AND t.id = pt.team_id" in statement
    assert ":week" not in statement
    assert "WHEN rl.status IN ('CUT', 'RET') THEN NULL" in statement


def test_team_rule_prefers_the_latest_roster_row_and_treats_cut_or_retired_as_no_team() -> None:
    bounded, unbounded = _flat(_player_teams_cte()), _flat(_player_teams_cte(week_bound=False))

    assert "ORDER BY r.player_id, r.season DESC, r.week DESC" in bounded
    assert "WHEN rl.player_id IS NULL THEN p.team_id" in bounded
    assert "WHEN rl.status IN ('CUT', 'RET') THEN NULL" in bounded
    assert ":week" not in unbounded
    assert "WHEN rl.status IN ('CUT', 'RET') THEN NULL" in unbounded


def test_matchup_context_uses_completed_games_before_the_selected_week() -> None:
    session = _RecordingSession()
    assert asyncio.run(get_slate_matchup_context(cast(AsyncSession, session), 2026, 7)) == {}
    assert session.params == {"season": 2026, "week": 7}
    assert "g.week < :week" in session.statement
    assert "g.status = 'completed'" in session.statement
    assert "o.book = 'draftkings'" in session.statement


def test_slate_moneyline_cutoff_preserves_games_without_eligible_odds() -> None:
    session = _RecordingSession()
    assert asyncio.run(nfl_repository.get_slate_market_probabilities(cast(AsyncSession, session), 2026, 7)) == {}

    sql = _flat(session.statement)
    join, where = sql.split("WHERE g.sport = 'nfl'", 1)
    assert "LEFT JOIN sport_game_odds o" in join
    assert "o.sport = 'nfl' AND o.provider = 'the_odds_api_us' AND o.game_id = g.id" in join
    assert "o.market = 'moneyline' AND o.first_side = 'home'" in join
    assert "AND (g.start_utc IS NULL OR o.fetched_at < g.start_utc)" in join
    assert "o.fetched_at < g.start_utc" not in where
    assert "g.season = :season AND g.week = :week AND g.game_type = 'REG'" in where
    assert "ORDER BY g.id, o.fetched_at DESC NULLS LAST, o.id DESC" in where
    assert session.params == {"season": 2026, "week": 7}


def test_slate_matchup_cutoff_applies_before_latest_market_selection() -> None:
    session = _RecordingSession()
    asyncio.run(get_slate_matchup_context(cast(AsyncSession, session), 2026, 7))

    sql = _flat(session.statement)
    latest, outer = sql.split("latest_odds AS (", 1)[1].split(") SELECT g.id, ml.book", 1)
    assert "DISTINCT ON (g.id, o.market)" in latest
    assert "o.sport = 'nfl' AND o.provider = 'the_odds_api_us' AND o.game_id = g.id" in latest
    assert "g.season = :season AND g.week = :week AND g.game_type = 'REG'" in latest
    assert "AND (g.start_utc IS NULL OR o.fetched_at < g.start_utc) ORDER BY" in latest
    assert "ORDER BY g.id, o.market, (o.book = 'draftkings') DESC, o.fetched_at DESC, o.id DESC" in latest
    for alias, market in (("ml", "moneyline"), ("sp", "spread"), ("tot", "total")):
        assert f"LEFT JOIN latest_odds {alias} ON {alias}.game_id = g.id AND {alias}.market = '{market}'" in outer
    assert "o.fetched_at < g.start_utc" not in outer


def test_missing_opponent_aggregate_remains_unavailable() -> None:
    assert _optional_averages({"opponent_games": None}, "opponent_") is None


def test_slate_history_is_batched_and_limited_to_completed_pre_week_games() -> None:
    session = _RecordingSession()

    assert asyncio.run(get_slate_player_history(cast(AsyncSession, session), 2026, 7, [11, 12])) == {}

    assert session.params == {
        "season": 2026, "week": 7, "player_ids": [11, 12], "first_history_season": PROJECTION_FIRST_HISTORY_SEASON,
    }
    assert "g.season >= :first_history_season" in session.statement
    assert "s.player_id = ANY(CAST(:player_ids AS bigint[]))" in session.statement
    assert "g.status = 'completed'" in session.statement
    assert "g.season < :season OR (g.season = :season AND g.week < :week)" in session.statement
    assert "LEFT JOIN sport_teams opponent ON opponent.sport = 'nfl' AND opponent.id = s.opponent_team_id" in session.statement
    assert "opponent.team_code AS opponent_team" in session.statement
    assert "ORDER BY s.player_id, g.season DESC, g.week DESC" in session.statement


def test_weather_snapshot_keeps_forecast_and_fetch_times_distinct() -> None:
    session = _RecordingSession()
    session.result_id = 17

    assert asyncio.run(insert_game_weather_snapshot(cast(AsyncSession, session), 12, "outdoor", "open_meteo", None, 58, 13, 21, 35, {"hour": 1})) == 17

    assert "nfl_game_weather_snapshots" in session.statement
    assert "forecast_for" in session.statement
    assert "CAST(:raw_json AS jsonb)" in session.statement
    assert session.params["venue_type"] == "outdoor"


def test_player_prop_odds_snapshot_keeps_unresolved_players_and_yes_only_prices() -> None:
    session = _RecordingSession()

    asyncio.run(insert_player_prop_odds_snapshot(
        cast(AsyncSession, session), 12, None, "Bijan Robinson", "evt1", "anytime_touchdown",
        "draftkings", None, -195, None, 0.661, True, {"key": "player_anytime_td"},
    ))

    assert "nfl_player_prop_odds" in session.statement
    assert "CAST(:raw_json AS jsonb)" in session.statement
    assert session.params["player_id"] is None
    assert session.params["no_odds"] is None
    assert session.params["includes_margin"] is True
    assert session.params["raw_json"] == '{"key": "player_anytime_td"}'


def test_td_history_uses_the_slate_cutoff_and_regular_season_only() -> None:
    session = _RecordingSession()

    assert asyncio.run(_td_history(cast(AsyncSession, session), 2026, 2, [7])) == ({}, {})

    assert "g.game_type = 'REG'" in session.statement
    assert "s.season < :season OR (s.season = :season AND s.week < :week)" in session.statement
    assert session.params == {"season": 2026, "week": 2, "first_history_season": PROJECTION_FIRST_HISTORY_SEASON}


def test_td_history_skips_queries_without_players() -> None:
    session = _RecordingSession()

    assert asyncio.run(_td_history(cast(AsyncSession, session), 2026, 2, [])) == ({}, {})
    assert session.statement == ""


def test_slate_prop_odds_takes_the_latest_price_per_book_for_resolved_players() -> None:
    session = _RecordingSession()

    assert asyncio.run(get_slate_prop_odds(cast(AsyncSession, session), 2026, 3)) == {}

    assert "DISTINCT ON (o.game_id, o.player_id, o.book)" in session.statement
    assert "o.player_id IS NOT NULL" in session.statement
    assert "o.fetched_at DESC" in session.statement
    assert session.params == {"season": 2026, "week": 3}


def test_weather_refresh_excludes_games_with_a_recent_snapshot() -> None:
    session = _RecordingSession()

    assert asyncio.run(get_upcoming_games_needing_weather(cast(AsyncSession, session), 7)) == []

    assert "nfl_game_weather_snapshots" in session.statement
    assert "w.fetched_at >= now() - INTERVAL '3 hours'" in session.statement
    assert session.params == {"days_ahead": 7}


def test_usage_aggregates_share_the_pre_week_cutoff_and_ignore_null_usage_rows() -> None:
    session = _RecordingSession()

    asyncio.run(get_slate_lines(cast(AsyncSession, session), 2026, 7))

    usage_filter = "FILTER (WHERE s.targets IS NOT NULL AND s.target_share IS NOT NULL)"
    assert session.statement.count(f"COUNT(*) {usage_filter} AS usage_games") == 2
    assert session.statement.count(f"AVG(s.targets) {usage_filter} AS targets") == 2
    assert session.statement.count(f"AVG(s.target_share) {usage_filter} AS target_share") == 2
    assert "b.usage_games AS player_usage_games" in session.statement
    assert "pb.usage_games AS position_usage_games" in session.statement


def test_usage_without_evidence_is_unavailable_not_zero() -> None:
    assert _usage({"player_usage_games": 0, "player_targets": None, "player_target_share": None}, "player_") is None
    assert _usage({"player_usage_games": None, "player_targets": None, "player_target_share": None}, "player_") is None


def test_usage_with_evidence_carries_sample_and_averages() -> None:
    row = {"position_usage_games": 12, "position_targets": 6.5, "position_target_share": 0.18}

    assert _usage(row, "position_") == {"games": 12, "targets": 6.5, "target_share": 0.18}


class _ScriptedResult:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


class _ScriptedSession:
    """Answers each execute with the next scripted rows and keeps every statement."""

    def __init__(self, *responses: list[tuple[object, ...]]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(self, statement: TextClause, params: dict[str, object]) -> _ScriptedResult:
        self.calls.append((" ".join(str(statement).split()), params))
        return _ScriptedResult(self.responses.pop(0))


def test_red_zone_write_zeroes_the_files_games_before_applying_counts() -> None:
    usage = NflverseRedZoneSeason(
        game_ids=frozenset({"2024_01_ARI_BUF", "2024_01_ZZZ_YYY"}),
        games=[
            NflverseRedZoneGame("00-0000001", "2024_01_ARI_BUF", 3, 0, 1, 0, 2),
            NflverseRedZoneGame("00-0000009", "2024_01_ARI_BUF", 0, 2, 0, 1, 1),
        ],
    )
    # Known games, then reset rows, then applied rows: one of two counted players has a row.
    session = _ScriptedSession([("2024_01_ARI_BUF",)], [(1,), (2,), (3,)], [(1,)])

    result = asyncio.run(write_red_zone_usage(cast(AsyncSession, session), usage))

    (_, known_params), (reset_sql, reset_params), (apply_sql, apply_params) = session.calls
    assert known_params["game_keys"] == ["2024_01_ARI_BUF", "2024_01_ZZZ_YYY"]
    assert "end_zone_targets = 0" in reset_sql
    assert reset_params["game_keys"] == ["2024_01_ARI_BUF", "2024_01_ZZZ_YYY"]
    # Applying only updates existing weekly rows; an unmatched player is skipped, not inserted.
    assert apply_sql.startswith("UPDATE nfl_player_weekly_stats s")
    assert "INSERT" not in apply_sql
    assert apply_params["player_keys"] == ["00-0000001", "00-0000009"]
    assert apply_params["rz20_carries"] == [3, 0]
    assert apply_params["rz5_targets"] == [0, 1]
    assert apply_params["end_zone_targets"] == [2, 1]
    assert result == RedZoneWriteResult(rows_reset=3, rows_applied=1, players_skipped=1, games_skipped=1)


def test_red_zone_write_zeroes_and_applies_punts_with_the_other_counts() -> None:
    usage = NflverseRedZoneSeason(
        game_ids=frozenset({"2024_01_ARI_BUF"}),
        games=[
            NflverseRedZoneGame("00-0000004", "2024_01_ARI_BUF", 0, 0, 0, 0, 0, punts=5),
            NflverseRedZoneGame("00-0000001", "2024_01_ARI_BUF", 3, 0, 1, 0, 2),
        ],
    )
    session = _ScriptedSession([("2024_01_ARI_BUF",)], [(1,), (2,)], [(1,), (2,)])

    asyncio.run(write_red_zone_usage(cast(AsyncSession, session), usage))

    (_, _), (reset_sql, _), (apply_sql, apply_params) = session.calls
    assert "punts = 0" in reset_sql
    assert "punts = v.punts" in apply_sql
    assert apply_params["punts"] == [5, 0]


def test_roster_replace_is_scoped_to_the_files_season_weeks_and_never_creates_players() -> None:
    rosters = [
        NflverseRosterWeek("00-0000001", 2026, 1, "PIT", "ACT"),
        NflverseRosterWeek("00-0000001", 2026, 2, "PIT", "RES"),
        NflverseRosterWeek("00-0000099", 2026, 2, "XYZ", "DEV"),
    ]
    # Deleted rows, then inserted rows (the unknown player and team are dropped by the joins), then known teams.
    session = _ScriptedSession([(1,), (2,)], [(10,), (11,)], [("PIT",)])

    result = asyncio.run(replace_weekly_rosters(cast(AsyncSession, session), 2026, rosters))

    (delete_sql, delete_params), (insert_sql, insert_params), _ = session.calls
    assert delete_sql.startswith("DELETE FROM nfl_player_weekly_rosters WHERE season = :season AND week = ANY(:weeks)")
    assert delete_params == {"season": 2026, "weeks": [1, 2]}
    assert "JOIN sport_players p ON p.sport = 'nfl' AND p.source_player_id = v.player_key" in insert_sql
    assert "JOIN sport_teams t ON t.sport = 'nfl' AND t.team_code = v.team" in insert_sql
    assert "INSERT INTO sport_players" not in insert_sql and "INSERT INTO sport_teams" not in insert_sql
    assert insert_params["player_keys"] == ["00-0000001", "00-0000001", "00-0000099"]
    assert insert_params["statuses"] == ["ACT", "RES", "DEV"]
    assert result == RosterWriteResult(rows_deleted=2, rows_inserted=2, rows_skipped=1, unknown_teams=["XYZ"])


def test_injury_replace_is_scoped_to_the_files_season_weeks_and_keeps_nulls() -> None:
    injuries = [
        NflverseInjuryWeek("00-0000001", 2026, 1, "CIN", "Out", "Did Not Participate In Practice", "Knee"),
        NflverseInjuryWeek("00-0000001", 2026, 2, "CIN", None, "Full Participation in Practice", "Knee"),
        NflverseInjuryWeek("00-0000099", 2026, 2, "XYZ", "Questionable", None, None),
    ]
    session = _ScriptedSession([(1,)], [(10,), (11,)], [("CIN",)])

    result = asyncio.run(replace_weekly_injuries(cast(AsyncSession, session), 2026, injuries))

    (delete_sql, delete_params), (insert_sql, insert_params), _ = session.calls
    assert delete_sql.startswith("DELETE FROM nfl_player_injuries WHERE season = :season AND week = ANY(:weeks)")
    assert delete_params == {"season": 2026, "weeks": [1, 2]}
    assert insert_sql.startswith(
        "INSERT INTO nfl_player_injuries (player_id, season, week, team_id, report_status, practice_status, primary_injury)"
    )
    assert "JOIN sport_players p ON p.sport = 'nfl' AND p.source_player_id = v.player_key" in insert_sql
    assert "INSERT INTO sport_players" not in insert_sql and "INSERT INTO sport_teams" not in insert_sql
    assert insert_params["row_weeks"] == [1, 2, 2]
    assert insert_params["report_status"] == ["Out", None, "Questionable"]
    assert insert_params["practice_status"] == ["Did Not Participate In Practice", "Full Participation in Practice", None]
    assert result == PlayerWeekWriteResult(rows_deleted=1, rows_inserted=2, rows_skipped=1, unknown_teams=["XYZ"])


def test_depth_replace_writes_position_rank_and_snapshot_through_the_shared_helper() -> None:
    snapshot = datetime(2026, 9, 18, 12, 12, 55, tzinfo=UTC)
    depth = [
        NflverseDepthWeek("00-0000001", 2026, 2, "CIN", "WR", 1, snapshot),
        NflverseDepthWeek("00-0000002", 2026, 2, "CIN", "WR", 2, snapshot),
    ]
    session = _ScriptedSession([], [(10,), (11,)], [("CIN",)])

    result = asyncio.run(replace_weekly_depth_charts(cast(AsyncSession, session), 2026, depth))

    (delete_sql, delete_params), (insert_sql, insert_params), _ = session.calls
    assert delete_sql.startswith("DELETE FROM nfl_player_depth_charts WHERE season = :season AND week = ANY(:weeks)")
    assert delete_params == {"season": 2026, "weeks": [2]}
    assert "CAST(:depth_rank AS smallint[])" in insert_sql and "CAST(:snapshot_at AS timestamptz[])" in insert_sql
    assert insert_params["position"] == ["WR", "WR"]
    assert insert_params["depth_rank"] == [1, 2]
    assert insert_params["snapshot_at"] == [snapshot, snapshot]
    assert result == PlayerWeekWriteResult(rows_deleted=0, rows_inserted=2, rows_skipped=0, unknown_teams=[])


def test_snap_replace_is_scoped_to_the_files_games_and_never_creates_players_or_games() -> None:
    rows = [
        ("00-0033906", NflverseSnapGame("KamaAl00", "2025_01_ARI_NO", 2025, 1, "NO", 59, 0.79)),
        ("00-0000099", NflverseSnapGame("UnstAa00", "2025_01_ARI_NO", 2025, 1, "NO", 0, 0.0)),
        ("00-0033906", NflverseSnapGame("KamaAl00", "2025_02_NO_ZZZ", 2025, 2, "NO", None, None)),
    ]
    # Deleted rows, inserted rows (unknown player and game dropped by the joins), known games, known teams.
    session = _ScriptedSession([(1,), (2,)], [(10,)], [("2025_01_ARI_NO",)], [("NO",)])

    result = asyncio.run(replace_snap_counts(
        cast(AsyncSession, session), frozenset({"2025_01_ARI_NO", "2025_02_NO_ZZZ", "2025_01_DAL_PHI"}), rows,
    ))

    (delete_sql, delete_params), (insert_sql, insert_params), _, _ = session.calls
    # Only the file's games are cleared, including a game whose rows were all filtered out.
    assert delete_sql.startswith("DELETE FROM nfl_player_snap_counts s USING sport_games g WHERE g.sport = 'nfl'")
    assert delete_params == {"game_keys": ["2025_01_ARI_NO", "2025_01_DAL_PHI", "2025_02_NO_ZZZ"]}
    assert "SELECT p.id, g.id, g.season, g.week, t.id" in insert_sql
    assert "JOIN sport_players p ON p.sport = 'nfl' AND p.source_player_id = v.player_key" in insert_sql
    assert "JOIN sport_games g ON g.sport = 'nfl' AND g.source_game_id = v.game_key" in insert_sql
    assert "INSERT INTO sport_players" not in insert_sql and "INSERT INTO sport_games" not in insert_sql
    # Blank stays NULL and zero stays zero.
    assert insert_params["offense_snaps"] == [59, 0, None]
    assert insert_params["offense_pct"] == [0.79, 0.0, None]
    assert result == SnapCountWriteResult(
        rows_deleted=2, rows_inserted=1, rows_skipped_player=1, rows_skipped_game=1, unknown_teams=[],
    )


def test_snap_history_is_pre_week_and_takes_the_position_share_from_the_baseline_season() -> None:
    rows: list[dict] = [
        {"player_id": 7, "position": "TE", "baseline_season": 2025},
        {"player_id": 8, "position": "RB", "baseline_season": None},
    ]
    session = _ScriptedSession(
        [(7, 2025, 12, 0.81), (7, 2026, 1, 0.9)],
        [("TE", 2025, 0.44), ("TE", 2026, 0.47), ("RB", 2025, 0.38)],
    )

    asyncio.run(_attach_snap_history(cast(AsyncSession, session), 2026, 2, rows))

    (player_sql, player_params), (position_sql, _) = session.calls
    # Strictly before the slate week, the same cutoff as the TD history; NULL shares are not evidence.
    for sql in (player_sql, position_sql):
        assert "(season < :season OR (season = :season AND week < :week))" in sql.replace("s.", "")
        assert "offense_pct IS NOT NULL" in sql
    # Snap-only games count: the player query reads the snap table alone, no weekly-stat join.
    assert "nfl_player_weekly_stats" not in player_sql
    assert player_params == {
        "player_ids": [7, 8], "season": 2026, "week": 2, "first_history_season": PROJECTION_FIRST_HISTORY_SEASON,
    }
    assert rows[0]["snap_seasons"] == [{"season": 2025, "games": 12, "share": 0.81}, {"season": 2026, "games": 1, "share": 0.9}]
    assert rows[0]["position_snap_share"] == 0.44
    assert (rows[1]["snap_seasons"], rows[1]["position_snap_share"]) == ([], 0.0)


class _NoParamsSession(_ScriptedSession):
    async def execute(self, statement: TextClause, params: dict[str, object] | None = None) -> _ScriptedResult:
        return await super().execute(statement, params or {})


def test_backtest_snap_rows_are_regular_season_and_keep_null_shares() -> None:
    session = _NoParamsSession([(1, "TE", 2025, 3, 0.62), (1, "TE", 2025, 4, None)])

    rows = asyncio.run(get_snap_rows(cast(AsyncSession, session)))

    ((sql, params),) = session.calls
    assert "FROM nfl_player_snap_counts s" in sql and "WHERE g.game_type = 'REG'" in sql
    assert "AND s.season >= :first_history_season" in sql
    assert params == {"first_history_season": PROJECTION_FIRST_HISTORY_SEASON}
    assert rows == [NflSnapRow(1, "TE", 2025, 3, 0.62), NflSnapRow(1, "TE", 2025, 4, None)]


def test_elo_games_are_regular_season_in_date_order_and_keep_unfinished_games() -> None:
    session = _NoParamsSession([
        ("2020_12_PIT_BAL", 2020, 12, "BAL", "PIT", 14, 19),
        ("2026_03_DAL_PHI", 2026, 3, "PHI", "DAL", None, None),
    ])

    games = asyncio.run(get_elo_games(cast(AsyncSession, session)))

    ((sql, _),) = session.calls
    assert "WHERE g.sport = 'nfl' AND g.game_type = 'REG'" in sql
    # Date, not week: a postponed game keeps its original week number.
    assert "ORDER BY g.game_date, g.start_utc NULLS LAST, g.source_game_id" in sql
    assert "home_score IS NOT NULL" not in sql
    assert games == [
        NflEloGame("2020_12_PIT_BAL", 2020, 12, "BAL", "PIT", 14, 19),
        NflEloGame("2026_03_DAL_PHI", 2026, 3, "PHI", "DAL", None, None),
    ]


def test_game_upsert_writes_and_refreshes_recorded_weather() -> None:
    session = _RecordingSession()
    game = NflverseGame(
        "2025_01_DAL_PHI", 2025, 1, "REG", date(2025, 9, 4), None, "PHI", "DAL", 24, 20,
        8.5, 47.5, -425, 330, "outdoors", 7, 7, temp=75, wind=11,
    )

    asyncio.run(upsert_game(cast(AsyncSession, session), game, 1, 2))

    assert (session.params["temp"], session.params["wind"]) == (75, 11)
    # A game re-imported after it is played picks up weather it lacked before.
    assert "temp = EXCLUDED.temp" in session.statement
    assert "wind = EXCLUDED.wind" in session.statement


def _game(game_id: str = "2025_01_DAL_PHI") -> NflverseGame:
    return NflverseGame(
        game_id, 2025, 1, "REG", date(2025, 9, 4), None, "PHI", "DAL", None, None,
        None, None, None, None, None, None, None,
    )


@pytest.mark.parametrize(("write", "insert", "conflict"), [
    (lambda db: nfl_repository.upsert_team(db, "ATL"),
     "INSERT INTO sport_teams (sport, team_code, name)", "ON CONFLICT (sport, team_code)"),
    (lambda db: nfl_repository.upsert_player(db, "00-0033873", "P. Mahomes", "QB", 1),
     "INSERT INTO sport_players (sport, source_player_id, name, position, team_id)",
     "ON CONFLICT (sport, source_player_id)"),
    (lambda db: nfl_repository.upsert_player_alias(db, "Pat Mahomes", "pat mahomes", 7),
     "INSERT INTO sport_player_aliases (sport, player_id, alias_name, alias_name_norm, source)",
     "ON CONFLICT (sport, alias_name_norm)"),
    (lambda db: upsert_game(db, _game(), 1, 2),
     "INSERT INTO sport_games (", "ON CONFLICT (sport, source_game_id)"),
])
def test_shared_table_upserts_write_nfl_rows_on_the_sport_scoped_key(write, insert, conflict) -> None:
    session = _RecordingSession()

    asyncio.run(write(cast(AsyncSession, session)))

    assert insert in session.statement
    assert "VALUES ('nfl', :" in session.statement or "VALUES (\n                'nfl', :" in session.statement
    assert conflict in session.statement
    assert "nfl_" not in session.statement


def test_game_odds_insert_and_latest_read_stay_on_nfl_rows() -> None:
    session = _RecordingSession()

    asyncio.run(nfl_repository.insert_game_odds_snapshot(
        cast(AsyncSession, session), 9, "draftkings", "spread", -3.5, "home", "away", -110, -110, 0.5, 0.5, None, provider="the_odds_api_us",
    ))
    assert "INSERT INTO sport_game_odds (\n                sport, game_id," in session.statement
    assert "'nfl', :game_id" in session.statement


class _NoRow:
    def first(self) -> None:
        return None


class _NoRowSession(_RecordingSession):
    async def execute(self, statement: TextClause, params: dict[str, object] | None = None) -> "_NoRowSession":
        await super().execute(statement, params)
        return self

    def mappings(self) -> _NoRow:
        return _NoRow()


def test_latest_game_odds_read_only_sees_nfl_rows() -> None:
    session = _NoRowSession()

    assert asyncio.run(nfl_repository.get_latest_game_odds(cast(AsyncSession, session), 9, "draftkings", "spread")) is None
    assert "FROM sport_game_odds\n            WHERE sport = 'nfl' AND provider = 'the_odds_api_us' AND game_id = :game_id" in session.statement


def test_game_line_games_share_the_elo_order_and_carry_nullable_closing_lines() -> None:
    session = _NoParamsSession([
        ("2025_01_DAL_PHI", 2025, 1, "PHI", "DAL", 24, 20, 8.5, 47.5, -425, 330, "outdoors", 75, 11, 7, 7),
        ("2012_05_X_Y", 2012, 5, "NYG", "DAL", 17, 24, None, None, None, None, "dome", None, None, None, None),
    ])

    games = asyncio.run(get_game_line_games(cast(AsyncSession, session)))

    ((sql, _),) = session.calls
    assert "WHERE g.sport = 'nfl' AND g.game_type = 'REG'" in sql
    assert "ORDER BY g.game_date, g.start_utc NULLS LAST, g.source_game_id" in sql
    assert "g.spread_line::double precision, g.total_line::double precision" in sql
    assert "g.roof, g.temp, g.wind, g.home_rest, g.away_rest" in sql
    assert games[0] == NflGameLineGame(
        NflEloGame("2025_01_DAL_PHI", 2025, 1, "PHI", "DAL", 24, 20), 8.5, 47.5, -425, 330,
        "outdoors", 75, 11, 7, 7,
    )
    assert (games[1].spread_line, games[1].total_line, games[1].home_moneyline) == (None, None, None)
    assert (games[1].roof, games[1].temp, games[1].wind) == ("dome", None, None)


def test_clv_games_carry_the_previous_weeks_last_kickoff_and_pre_kickoff_odds_by_market() -> None:
    kickoff = datetime(2026, 9, 27, 17, 0, tzinfo=UTC)
    previous = datetime(2026, 9, 22, 0, 15, tzinfo=UTC)
    fetched = datetime(2026, 9, 22, 18, 0, tzinfo=UTC)
    session = _ScriptedSession(
        [
            (7, "2026_03_DAL_NYG", 3, kickoff, True, 27, 20, 2.5, 39.5, previous),
            (8, "2026_01_KC_BAL", 1, kickoff, False, None, None, None, None, None),
        ],
        [(7, "spread", 101, "draftkings", -2.5, fetched), (7, "total", 102, "draftkings", 39.5, fetched)],
    )

    games = asyncio.run(nfl_repository.get_game_line_clv_games(cast(AsyncSession, session), 2026))

    (games_sql, games_params), (odds_sql, odds_params) = session.calls
    assert games_params == odds_params == {"season": 2026}
    assert "LEFT JOIN week_last prev ON prev.week = g.week - 1" in games_sql
    assert "g.status = 'completed'" in games_sql and "g.game_type = 'REG'" in games_sql
    assert "o.market IN ('spread', 'total')" in odds_sql and "o.fetched_at < g.start_utc" in odds_sql
    assert games[0] == ClvGame(
        "2026_03_DAL_NYG", 3, kickoff, True, 27, 20, 2.5, 39.5, previous,
        {"spread": [OddsCandidate(101, "draftkings", -2.5, fetched)], "total": [OddsCandidate(102, "draftkings", 39.5, fetched)]},
    )
    assert games[1].previous_week_last_kickoff is None
    assert games[1].candidates == {"spread": [], "total": []}


def test_team_elo_replace_is_scoped_to_one_model_version_and_never_creates_teams_or_games() -> None:
    rows = [
        NflTeamEloRow("PHI", "2026_03_DAL_PHI", 2026, 3, True, 1561.2, None),
        NflTeamEloRow("DAL", "2026_03_DAL_PHI", 2026, 3, False, 1488.4, None),
    ]
    session = _ScriptedSession([(1,), (2,), (3,)], [(10,), (11,)])

    result = asyncio.run(replace_team_elo(cast(AsyncSession, session), rows, "nfl-elo-v1"))

    (delete_sql, delete_params), (insert_sql, insert_params) = session.calls
    assert delete_sql.startswith("DELETE FROM nfl_team_elo WHERE model_version = :model_version")
    assert delete_params == {"model_version": "nfl-elo-v1"}
    assert "JOIN sport_teams t ON t.sport = 'nfl' AND t.team_code = v.team" in insert_sql
    assert "JOIN sport_games g ON g.sport = 'nfl' AND g.source_game_id = v.game_key" in insert_sql
    assert "INSERT INTO sport_teams" not in insert_sql and "INSERT INTO sport_games" not in insert_sql
    assert insert_params["teams"] == ["PHI", "DAL"]
    assert insert_params["is_home"] == [True, False]
    # An unfinished game's post rating stays NULL rather than defaulting.
    assert insert_params["elo_post"] == [None, None]
    assert result == (3, 2)


def test_slate_team_elo_pairs_home_and_away_for_one_model_version() -> None:
    session = _ScriptedSession([(41, "2026_03_PHI_CHI", 1512.3, 1540.8)])

    elo = asyncio.run(get_slate_team_elo(cast(AsyncSession, session), 2026, 3))

    (sql, params), = session.calls
    assert params == {"season": 2026, "week": 3, "model_version": "nfl-elo-v1"}
    assert "JOIN nfl_team_elo h ON h.game_id = g.id AND h.is_home AND h.model_version = :model_version" in sql
    assert "JOIN nfl_team_elo a ON a.game_id = g.id AND NOT a.is_home AND a.model_version = :model_version" in sql
    # Inner joins: a game missing either side's rating is left out, never half-filled.
    assert "LEFT JOIN" not in sql
    assert "g.game_type = 'REG'" in sql
    assert elo == {41: ("2026_03_PHI_CHI", 1512.3, 1540.8)}


def test_team_efficiency_read_is_regular_season_and_keyed_by_game_and_side() -> None:
    session = _NoParamsSession([("2025_01_DAL_PHI", True, 59, 9.47, 30), ("2025_01_DAL_PHI", False, 55, 1.94, 25)])

    rows = asyncio.run(get_team_efficiency(cast(AsyncSession, session)))

    (sql, _), = session.calls
    assert "JOIN sport_games g ON g.sport = 'nfl' AND g.id = e.game_id" in sql and "g.game_type = 'REG'" in sql
    assert rows[("2025_01_DAL_PHI", False)] == NflverseTeamEfficiency("2025_01_DAL_PHI", False, 55, 1.94, 25)
    assert rows[("2025_01_DAL_PHI", True)].plays == 59


def test_team_efficiency_replace_resolves_teams_from_the_game_and_writes_only_final_games() -> None:
    rows = [
        NflverseTeamEfficiency("2025_01_DAL_PHI", True, 59, 9.47, 30),
        NflverseTeamEfficiency("2025_01_DAL_PHI", False, 55, 1.94, 25),
        NflverseTeamEfficiency("2026_03_KC_NYG", True, 20, 0.5, 9),
        NflverseTeamEfficiency("2099_01_ZZZ_YYY", True, 60, 0.0, 30),
    ]
    # Known games with finality, then deleted rows, then inserted rows (only the final game's two).
    session = _ScriptedSession(
        [("2025_01_DAL_PHI", True), ("2026_03_KC_NYG", False)], [(1,), (2,), (3,)], [(10,), (11,)],
    )

    result = asyncio.run(replace_team_efficiency(cast(AsyncSession, session), rows))

    (_, known_params), (delete_sql, delete_params), (insert_sql, insert_params) = session.calls
    assert known_params["game_keys"] == ["2025_01_DAL_PHI", "2026_03_KC_NYG", "2099_01_ZZZ_YYY"]
    # Scoped to the file's games only, so loading one season never touches another.
    assert delete_sql.startswith("DELETE FROM nfl_team_game_efficiency e USING sport_games g WHERE g.sport = 'nfl'")
    assert "g.source_game_id = ANY(:game_keys)" in delete_sql
    assert delete_params == known_params
    assert "CASE WHEN v.is_home THEN g.home_team_id ELSE g.away_team_id END" in insert_sql
    assert "sport_teams" not in insert_sql and "INSERT INTO sport_games" not in insert_sql
    assert "g.game_type = 'REG' AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL" in insert_sql
    assert insert_params["is_home"] == [True, False, True, True]
    assert insert_params["epa"] == [9.47, 1.94, 0.5, 0.0]
    assert result == TeamEfficiencyWriteResult(rows_deleted=3, rows_inserted=2, games_unknown=1, games_not_final=1)


def test_team_schedule_groups_regular_season_games_by_team_in_date_order() -> None:
    session = _ScriptedSession([
        ("BUF", 1, date(2026, 9, 13)), ("BUF", 2, date(2026, 9, 17)), ("CIN", 1, date(2026, 9, 13)),
    ])

    schedule = asyncio.run(get_team_schedule(cast(AsyncSession, session), 2026))

    (sql, params), = session.calls
    assert "g.game_type = 'REG'" in sql and "ORDER BY t.team_code, g.game_date" in sql
    assert params == {"season": 2026}
    assert schedule == {"BUF": [(1, date(2026, 9, 13)), (2, date(2026, 9, 17))], "CIN": [(1, date(2026, 9, 13))]}


def test_weekly_stat_upsert_leaves_red_zone_counts_to_the_play_by_play_ingest() -> None:
    # The Tuesday stats re-import must not wipe counts the play-by-play ingest wrote.
    session = _RecordingSession()
    stat = NflversePlayerWeek(
        player_id="00-0030000", player_name="Back", position="RB", team="CHI",
        opponent="DET", game_id="2026_01_DET_CHI", season=2026, week=1,
        passing_yards=0, passing_attempts=0, passing_completions=0, rushing_yards=40,
        rushing_attempts=10, receiving_yards=0, receptions=0, targets=0,
        target_share=0.0, air_yards_share=0.0, wopr=0.0, touchdowns=1, fantasy_points=10.0,
    )

    asyncio.run(upsert_weekly_stat(cast(AsyncSession, session), stat, 1, 2, 3, 4))

    assert "rz20" not in session.statement
    assert "rz5" not in session.statement


def test_weekly_stat_upsert_writes_kicking_but_leaves_punts_to_the_play_by_play_ingest() -> None:
    session = _RecordingSession()
    stat = NflversePlayerWeek(
        player_id="00-0035000", player_name="Kicker", position="K", team="CHI",
        opponent="DET", game_id="2026_01_DET_CHI", season=2026, week=1,
        passing_yards=0, passing_attempts=0, passing_completions=0, rushing_yards=0,
        rushing_attempts=0, receiving_yards=0, receptions=0, targets=None,
        target_share=None, air_yards_share=None, wopr=None, touchdowns=0, fantasy_points=9.0,
        fg_made=3, pat_made=2,
    )

    asyncio.run(upsert_weekly_stat(cast(AsyncSession, session), stat, 1, 2, 3, 4))

    assert (session.params["fg_made"], session.params["pat_made"]) == (3, 2)
    assert "fg_made = EXCLUDED.fg_made" in session.statement
    assert "pat_made = EXCLUDED.pat_made" in session.statement
    assert "punts" not in session.statement


def test_weekly_stat_upsert_keeps_usage_values_nullable_and_updates_them() -> None:
    session = _RecordingSession()
    stat = NflversePlayerWeek(
        player_id="00-0030000", player_name="Receiver", position="WR", team="CHI",
        opponent="DET", game_id="2026_01_DET_CHI", season=2026, week=1,
        passing_yards=0, passing_attempts=0, passing_completions=0, rushing_yards=0,
        rushing_attempts=0, receiving_yards=88, receptions=7, targets=None,
        target_share=None, air_yards_share=None, wopr=None, touchdowns=1, fantasy_points=22.1,
    )

    asyncio.run(upsert_weekly_stat(cast(AsyncSession, session), stat, 1, 2, 3, 4))

    assert session.params["targets"] is None
    assert session.params["target_share"] is None
    assert session.params["air_yards_share"] is None
    assert session.params["wopr"] is None
    assert "targets = EXCLUDED.targets" in session.statement
    assert "target_share = EXCLUDED.target_share" in session.statement
    assert "air_yards_share = EXCLUDED.air_yards_share" in session.statement
    assert "wopr = EXCLUDED.wopr" in session.statement


def test_weekly_stat_upsert_writes_and_updates_fantasy_components() -> None:
    session = _RecordingSession()
    stat = NflversePlayerWeek(
        player_id="00-0030000", player_name="Quarterback", position="QB", team="MIA",
        opponent="IND", game_id="2025_01_MIA_IND", season=2025, week=1,
        passing_yards=114, passing_attempts=23, passing_completions=14, rushing_yards=7,
        rushing_attempts=2, receiving_yards=0, receptions=0, targets=None,
        target_share=None, air_yards_share=None, wopr=None, touchdowns=0, fantasy_points=5.26,
        passing_tds=1, interceptions=2, fumbles_lost=1, two_point_conversions=1,
        return_tds=0, fumble_recovery_tds=0, prizepicks_fantasy_points=8.26,
    )

    asyncio.run(upsert_weekly_stat(cast(AsyncSession, session), stat, 1, 2, 3, 4))

    assert (session.params["interceptions"], session.params["fumbles_lost"]) == (2, 1)
    assert session.params["prizepicks_fantasy_points"] == 8.26
    assert session.params["fantasy_points"] == 5.26
    for column in (
        "passing_tds", "interceptions", "fumbles_lost", "two_point_conversions",
        "return_tds", "fumble_recovery_tds", "prizepicks_fantasy_points",
    ):
        assert f"{column} = EXCLUDED.{column}" in session.statement


class _OneRowResult:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self.row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self.row


class _OneRowSession:
    def __init__(self, *rows: tuple[object, ...] | None) -> None:
        self.rows = list(rows)
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(self, statement: TextClause, params: dict[str, object]) -> _OneRowResult:
        self.calls.append((" ".join(str(statement).split()), params))
        return _OneRowResult(self.rows.pop(0))


NOW = datetime(2026, 9, 26, 18, 0, tzinfo=UTC)


def test_current_week_is_the_next_game_within_a_12_hour_grace() -> None:
    session = _OneRowSession((2026, 3))

    assert asyncio.run(get_current_week(cast(AsyncSession, session), NOW)) == (2026, 3)

    [(sql, params)] = session.calls
    assert "game_type = 'REG' AND start_utc >= :cutoff" in sql
    assert "ORDER BY start_utc, id" in sql
    assert params["cutoff"] == datetime(2026, 9, 26, 6, 0, tzinfo=UTC)


def test_current_week_falls_back_to_the_latest_loaded_week_after_the_season() -> None:
    session = _OneRowSession(None, (2026, 18))

    assert asyncio.run(get_current_week(cast(AsyncSession, session), NOW)) == (2026, 18)
    assert "ORDER BY season DESC, week DESC" in session.calls[1][0]


def test_current_week_is_none_without_any_regular_season_game() -> None:
    session = _OneRowSession(None, None)

    assert asyncio.run(get_current_week(cast(AsyncSession, session), NOW)) is None


class _MappingResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self) -> list[dict[str, object]]:
        return self.rows


class _MappingSession:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(self, statement: TextClause, params: dict[str, object]) -> _MappingResult:
        self.calls.append((" ".join(str(statement).split()), params))
        return _MappingResult(self.rows)


def _gradeable_row(**overrides: object) -> dict[str, object]:
    stats = dict.fromkeys(
        ("passing_yards", "passing_attempts", "passing_completions", "rushing_yards", "rushing_attempts",
         "receiving_yards", "receptions", "touchdowns", "prizepicks_fantasy_points"),
    )
    return {
        "id": 7, "season": 2026, "week": 2, "game_id": 3, "player_id": 9, "market": "receptions",
        "segment": "full_game", "odds_type": "standard", "line": Decimal("4.5"),
        "fetched_at": datetime(2026, 9, 20, 15, 0, tzinfo=UTC), **stats, "receptions": 6,
        "offense_snaps": 51, "game_has_stats": True,
    } | overrides


def test_gradeable_lines_take_the_last_pre_kickoff_snapshot_of_completed_games() -> None:
    session = _MappingSession([_gradeable_row()])

    [line] = asyncio.run(get_gradeable_prop_lines(cast(AsyncSession, session), 2026))

    [(sql, params)] = session.calls
    assert params == {"season": 2026}
    assert "l.fetched_at < g.start_utc" in sql
    assert "g.status = 'completed'" in sql and "g.game_type = 'REG'" in sql
    assert "DISTINCT ON (l.provider, l.provider_prop_id)" in sql
    assert "ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC" in sql
    assert "LEFT JOIN nfl_player_weekly_stats s ON s.player_id = latest.player_id AND s.game_id = latest.game_id" in sql
    assert "LEFT JOIN nfl_player_snap_counts sc ON sc.player_id = latest.player_id AND sc.game_id = latest.game_id" in sql
    assert (
        "EXISTS (SELECT 1 FROM nfl_player_weekly_stats gs WHERE gs.game_id = latest.game_id) AS game_has_stats" in sql
    )
    assert "loaded_weeks" not in sql
    assert (line.line, line.stat_value, line.offense_snaps, line.game_has_stats) == (4.5, 6.0, 51, True)


def test_frozen_lines_take_the_latest_pre_kickoff_frozen_row_of_each_provider_prop() -> None:
    row = _gradeable_row(p_over=0.62, p_under=0.38, model_version="v4", over_probability_version="nfl-pover-v1")
    session = _MappingSession([row])

    [frozen] = asyncio.run(nfl_repository.get_frozen_gradeable_lines(cast(AsyncSession, session), 2026))

    [(sql, params)] = session.calls
    assert params == {"season": 2026}
    assert "FROM sport_prop_predictions p JOIN sport_prop_lines l ON l.sport = 'nfl' AND l.id = p.prop_line_id" in sql
    assert "DISTINCT ON (l.provider, l.provider_prop_id)" in sql
    assert "l.fetched_at < g.start_utc AND p.generated_at < g.start_utc" in sql
    assert "g.status = 'completed'" in sql and "g.game_type = 'REG'" in sql
    assert (
        "EXISTS (SELECT 1 FROM nfl_player_weekly_stats gs WHERE gs.game_id = frozen.game_id) AS game_has_stats" in sql
    )
    assert "loaded_weeks" not in sql
    assert "ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC, p.generated_at DESC" in sql
    # Settled here: 6 receptions against 4.5.
    assert frozen == FrozenLine(
        line_id=7, period=2, player_id=9, game_id=3, market="receptions", odds_type="standard", outcome="over",
        p_over=0.62, p_under=0.38, model_version="v4", over_probability_version="nfl-pover-v1",
    )


def test_finished_weeks_need_every_regular_season_game_completed_and_its_stats_loaded() -> None:
    session = _ScriptedSession([(1,), (2,)])

    weeks = asyncio.run(nfl_repository.get_finished_weeks(cast(AsyncSession, session), 2026))

    [(sql, params)] = session.calls
    assert params == {"season": 2026}
    assert "g.sport = 'nfl'" in sql and "g.game_type = 'REG'" in sql and "GROUP BY g.week" in sql
    assert "bool_and(g.status = 'completed')" in sql
    assert "bool_and(EXISTS (SELECT 1 FROM nfl_player_weekly_stats s WHERE s.game_id = g.id))" in sql
    assert weeks == {1, 2}


def test_frozen_coverage_counts_27a_full_game_lines_with_any_frozen_row_per_week() -> None:
    session = _ScriptedSession([(2, 6021, 0), (3, 120, 95)])

    coverage = asyncio.run(nfl_repository.get_frozen_coverage(cast(AsyncSession, session), 2026))

    [(sql, _)] = session.calls
    assert "l.segment = 'full_game'" in sql
    assert "ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC" in sql
    assert "fl.provider = latest.provider AND fl.provider_prop_id = latest.provider_prop_id" in sql
    assert "GROUP BY latest.week" in sql
    assert coverage == {2: (6021, 0), 3: (120, 95)}


def test_the_modelled_market_filter_lists_exactly_the_projected_markets() -> None:
    expected = ", ".join(f"'{market.value}'" for market in NflPropMarket)
    assert nfl_repository.MODELLED_MARKET_FILTER == f"l.market IN ({expected})"
    assert len(NflPropMarket) == 10


def test_slate_lines_read_only_modelled_markets() -> None:
    assert f"WHERE l.sport = 'nfl' AND {nfl_repository.V4_MARKET_FILTER}" in nfl_repository._LATEST_LINES_CTE


def test_gradeable_lines_read_only_modelled_markets() -> None:
    for player_id in (None, 9):
        session = _MappingSession([])
        asyncio.run(get_gradeable_prop_lines(cast(AsyncSession, session), 2026, player_id=player_id))
        [(sql, _)] = session.calls
        assert nfl_repository.V4_MARKET_FILTER in sql


def test_frozen_coverage_counts_only_modelled_markets() -> None:
    session = _ScriptedSession([])
    asyncio.run(nfl_repository.get_frozen_coverage(cast(AsyncSession, session), 2026))
    [(sql, _)] = session.calls
    assert f"l.segment = 'full_game' AND {nfl_repository.V4_MARKET_FILTER}" in sql


def test_gradeable_line_reads_its_markets_stat_and_keeps_a_missing_row_as_none() -> None:
    session = _MappingSession([
        _gradeable_row(market="anytime_touchdown", touchdowns=2),
        _gradeable_row(id=8, market="receiving_yards", receiving_yards=None, offense_snaps=None),
    ])

    touchdown, missing = asyncio.run(get_gradeable_prop_lines(cast(AsyncSession, session), 2026))

    assert touchdown.stat_value == 2.0
    assert (missing.stat_value, missing.offense_snaps) == (None, None)


def test_a_fantasy_line_settles_on_prizepicks_points_not_nflverse_ppr() -> None:
    # One interception: PPR charges 2 and lands under 20.5; PrizePicks charges 1 and lands over.
    session = _MappingSession([
        _gradeable_row(market="fantasy_points", line=Decimal("20.5"), fantasy_points=20.26, prizepicks_fantasy_points=21.26),
    ])

    [line] = asyncio.run(get_gradeable_prop_lines(cast(AsyncSession, session), 2026))

    assert "s.prizepicks_fantasy_points" in session.calls[0][0]
    assert line.stat_value == 21.26
    assert settle_line(line).outcome == "over"


def test_replay_rows_drive_the_slate_query_from_the_weeks_rated_player_games(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_slate_line_rows(db: object, season: int, week: int, lines_cte: str, params: dict[str, object]) -> list[dict]:
        captured.update(season=season, week=week, lines_cte=" ".join(lines_cte.split()), params=params)
        return [
            {"player_id": 9, "game_id": 3, "market": "receptions", "position": "WR", "opponent_team_id": 5},
            {"player_id": 9, "game_id": 3, "market": "receiving_yards", "position": "WR", "opponent_team_id": 5},
            {"player_id": 4, "game_id": 3, "market": "receptions", "position": "WR", "opponent_team_id": 5},  # no stat row: dropped
        ]

    wr_game = NflTeamGameTotals(
        game_id=30, season=2025, week=9, passing_yards=0.0, passing_attempts=0.0, passing_completions=0.0,
        rushing_yards=0.0, rushing_attempts=0.0, receiving_yards=150.0, receptions=12.0, touchdowns=1.0,
        fantasy_points=None,
    )

    async def fake_team_game_totals(db: object, season: int, week: int) -> dict:
        assert (season, week) == (2025, 10)
        return {(5, "WR"): [wr_game]}

    monkeypatch.setattr(nfl_repository, "_slate_line_rows", fake_slate_line_rows)
    monkeypatch.setattr(nfl_repository, "get_team_game_position_totals", fake_team_game_totals)
    stats = dict.fromkeys(
        ("passing_yards", "passing_attempts", "passing_completions", "rushing_yards", "rushing_attempts",
         "receiving_yards", "receptions", "touchdowns", "prizepicks_fantasy_points"),
    )
    session = _MappingSession([
        {"player_id": 9, "game_id": 3, **stats, "receptions": 7, "receiving_yards": 88,
         "home_moneyline": -150, "away_moneyline": 130, "spread_line": 3.0, "total_line": 44.5,
         "roof": "outdoors", "wind": 18},
    ])

    replay = asyncio.run(get_replay_rows(cast(AsyncSession, session), 2025, 10))

    cte = captured["lines_cte"]
    assert (captured["season"], captured["week"]) == (2025, 10)
    assert "FROM nfl_player_weekly_stats s" in cte
    assert "WHERE g.season = :season AND g.week = :week AND g.game_type = 'REG'" in cte
    assert "WITH ORDINALITY AS m(position, market, ordinal) ON m.position = p.position" in cte
    params = cast(dict[str, list[str]], captured["params"])
    pairs = set(zip(params["replay_positions"], params["replay_markets"]))
    assert ("QB", "passing_yards") in pairs and ("TE", "receptions") in pairs
    assert ("WR", "passing_yards") not in pairs and "LB" not in params["replay_positions"]
    [(outcome_sql, outcome_params)] = session.calls
    assert "SELECT s.player_id, s.game_id" in outcome_sql and "g.home_moneyline, g.away_moneyline" in outcome_sql
    assert outcome_params == {"season": 2025, "week": 10}
    assert [(item.row["market"], item.actual) for item in replay] == [("receptions", 7.0), ("receiving_yards", 88.0)]
    # -150 / +130 de-vigged: 0.6 and 0.4348 normalized to about 0.58.
    assert replay[0].home_market_prob == pytest.approx(0.58, abs=0.005)
    opponent = replay[0].row["team_game_opponent_averages"]
    assert (opponent["games"], opponent["receiving_yards"]) == (1, 150.0)
    assert replay[0].row["team_game_league_averages"] == opponent
    assert replay[0].row["game_lines"] == {"home_spread_margin": 3.0, "total": 44.5}
    assert "g.spread_line::double precision, g.total_line::double precision, g.roof, g.wind" in outcome_sql
    assert replay[0].row["game_weather"] == {"roof": "outdoors", "wind": 18}


def _team_game_row(**overrides: object) -> dict[str, object]:
    return {
        "defense_team_id": 5, "position": "WR", "game_id": 30, "season": 2025, "week": 9,
        "passing_yards": None, "passing_attempts": None, "passing_completions": None,
        "rushing_yards": Decimal("4"), "rushing_attempts": 1, "receiving_yards": Decimal("171"),
        "receptions": 14, "touchdowns": 1, "fantasy_points": Decimal("40.1"),
    } | overrides


def test_team_game_totals_group_by_defense_position_and_game_before_the_week() -> None:
    session = _MappingSession([
        _team_game_row(),
        _team_game_row(game_id=22, week=8, receiving_yards=Decimal("140"), fantasy_points=None),
        _team_game_row(position="TE", game_id=30, receiving_yards=Decimal("55")),
    ])

    totals = asyncio.run(get_team_game_position_totals(cast(AsyncSession, session), 2025, 10))

    [(sql, params)] = session.calls
    assert params == {"season": 2025, "week": 10, "first_history_season": PROJECTION_FIRST_HISTORY_SEASON}
    assert "s.season >= :first_history_season" in sql
    assert "GROUP BY s.opponent_team_id, p.position, g.id, g.season, g.week" in sql
    assert "team_code" not in sql
    assert "g.game_type = 'REG' AND g.status = 'completed'" in sql
    assert "s.opponent_team_id IS NOT NULL AND p.position IS NOT NULL" in sql
    assert "(s.season < :season OR (s.season = :season AND s.week < :week))" in sql
    assert "ORDER BY s.opponent_team_id, p.position, g.season DESC, g.week DESC, g.id DESC" in sql
    newest, older = totals[(5, "WR")]
    assert (newest.game_id, newest.receiving_yards, newest.passing_yards, newest.fantasy_points) == (30, 171.0, 0.0, 40.1)
    assert (older.game_id, older.fantasy_points) == (22, None)
    assert [item.receiving_yards for item in totals[(5, "TE")]] == [55.0]


class _RowsResult(_Result):
    def __init__(self, rows: list[dict[str, object]]) -> None:
        super().__init__()
        self.rows = rows

    def mappings(self) -> list[dict[str, object]]:
        return self.rows


class _FirstQueryRowsSession(_RecordingSession):
    """Returns `rows` for the slate query and nothing for the queries after it."""

    def __init__(self, rows: list[dict[str, object]]) -> None:
        super().__init__()
        self.rows = rows

    async def execute(self, statement: TextClause, params: dict[str, object] | None = None) -> _Result:
        rows, self.rows = self.rows, []
        return _RowsResult(rows)


def _season_row(season: int, games: int, receiving_yards: float) -> dict[str, object]:
    row: dict[str, object] = defaultdict(lambda: None)
    row.update({
        "id": 1, "game_id": 10, "player_id": 5, "player_name": "A Receiver", "position": "WR",
        "market": "receiving_yards", "segment": "full_game", "line": Decimal("60.5"),
        "provider": "prizepicks", "odds_type": "standard",
        "baseline_season": season, "player_games": games, "player_receiving_yards": receiving_yards,
        "player_usage_games": games, "player_targets": 7.0, "player_target_share": 0.2,
        "player_environment_games": games, "player_team_total": 20.0 + games, "player_team_margin": -1.5,
    })
    return row


def test_slate_rows_keep_every_season_beside_the_chosen_one() -> None:
    session = _FirstQueryRowsSession([_season_row(2025, 17, 80.0), _season_row(2026, 2, 40.0)])

    [line] = asyncio.run(get_slate_lines(cast(AsyncSession, session), 2026, 3))

    assert line["baseline_season"] == 2025
    assert line["averages"]["receiving_yards"] == 80.0
    assert sorted(line["baseline_seasons"]) == [2025, 2026]
    assert line["baseline_seasons"][2026]["averages"]["games"] == 2
    assert line["baseline_seasons"][2026]["averages"]["receiving_yards"] == 40.0
    assert line["baseline_seasons"][2025]["usage"] == {"games": 17, "targets": 7.0, "target_share": 0.2}
    assert line["baseline_seasons"][2026]["environment"] == {"games": 2, "team_total": 22.0, "team_margin": -1.5}
    assert line["environment"] == {"games": 17, "team_total": 37.0, "team_margin": -1.5}


def test_slate_rows_carry_prizepicks_fantasy_averages_beside_nflverse_ppr() -> None:
    row = _season_row(2025, 17, 0.0)
    row.update({"market": "fantasy_points"})
    for prefix, ppr, prizepicks in (
        ("player_", 18.0, 18.6), ("position_", 14.0, 14.3), ("opponent_", 15.0, 15.4), ("league_", 14.5, 14.8),
    ):
        row.update({f"{prefix}games": 17, f"{prefix}fantasy_points": ppr, f"{prefix}prizepicks_fantasy_points": prizepicks})
    session = _FirstQueryRowsSession([row])

    [line] = asyncio.run(get_slate_lines(cast(AsyncSession, session), 2026, 3))

    for key, ppr, prizepicks in (
        ("averages", 18.0, 18.6), ("position_averages", 14.0, 14.3),
        ("opponent_averages", 15.0, 15.4), ("league_position_averages", 14.5, 14.8),
    ):
        assert (line[key]["fantasy_points"], line[key]["prizepicks_fantasy_points"]) == (ppr, prizepicks)
    assert line["baseline_seasons"][2025]["averages"]["prizepicks_fantasy_points"] == 18.6


def test_slate_baselines_average_prizepicks_fantasy_points_in_every_aggregate() -> None:
    session = _RecordingSession()

    asyncio.run(get_slate_lines(cast(AsyncSession, session), 2026, 3))

    assert session.statement.count("AVG(s.prizepicks_fantasy_points) AS prizepicks_fantasy_points") == 4


def test_slate_rows_average_the_players_own_margin_over_games_with_both_lines() -> None:
    session = _RecordingSession()

    asyncio.run(get_slate_lines(cast(AsyncSession, session), 2026, 3))
    sql = " ".join(session.statement.split())

    assert "CASE WHEN s.team_id = g.home_team_id THEN g.spread_line ELSE -g.spread_line END" in sql
    assert "COUNT(*) FILTER (WHERE g.spread_line IS NOT NULL AND g.total_line IS NOT NULL) AS environment_games" in sql


def test_slate_lines_tiebreak_on_line_id_so_tied_lines_keep_one_order() -> None:
    session = _RecordingSession()

    asyncio.run(get_slate_lines(cast(AsyncSession, session), 2026, 3))

    # The id sits before the season so each line's season rows stay together.
    assert "ORDER BY p.name, l.market, l.line, l.id, b.season" in " ".join(session.statement.split())


def test_unmatched_slate_lines_tiebreak_on_line_id() -> None:
    session = _RecordingSession()

    asyncio.run(get_unmatched_slate_lines(cast(AsyncSession, session), 2026, 3))

    assert "ORDER BY l.raw_json ->> 'player_name', l.market, l.id" in " ".join(session.statement.split())


def test_slate_rows_without_lined_games_carry_no_environment() -> None:
    row = _season_row(2025, 17, 80.0)
    row["player_environment_games"] = 0
    session = _FirstQueryRowsSession([row])

    [line] = asyncio.run(get_slate_lines(cast(AsyncSession, session), 2026, 3))

    assert line["environment"] is None


def test_environment_fit_games_read_a_seasons_lined_games_for_rated_positions() -> None:
    stats = dict.fromkeys(
        ("passing_yards", "passing_attempts", "passing_completions", "rushing_yards", "rushing_attempts",
         "receiving_yards", "receptions", "touchdowns", "prizepicks_fantasy_points"),
    )
    session = _MappingSession([
        {"player_id": 7, "position": "QB", **stats, "passing_attempts": 34, "team_total": 24.0, "team_margin": 3.5,
         "roof": "dome", "wind": None},
    ])

    [game] = asyncio.run(get_environment_fit_games(cast(AsyncSession, session), 2024))

    [(sql, params)] = session.calls
    assert params == {"season": 2024, "positions": ["QB", "RB", "TE", "WR"]}
    assert "g.season = :season AND g.game_type = 'REG' AND g.spread_line IS NOT NULL AND g.total_line IS NOT NULL" in sql
    assert "CASE WHEN s.team_id = g.home_team_id THEN g.spread_line ELSE -g.spread_line END" in sql
    assert (game.player_id, game.position, game.team_total, game.team_margin) == (7, "QB", 24.0, 3.5)
    assert "g.roof, g.wind" in sql and (game.roof, game.wind) == ("dome", None)
    assert game.stats["passing_attempts"] == 34.0 and game.stats["passing_yards"] is None
    assert game.stats["anytime_touchdown"] is None


def test_game_notes_injuries_cover_all_positions_on_the_reporting_team() -> None:
    session = _RecordingSession()

    assert asyncio.run(nfl_repository.get_week_game_injuries(cast(AsyncSession, session), 2026, 3)) == []

    statement = _flat(session.statement)
    assert session.params == {"season": 2026, "week": 3}
    assert "WHERE i.season = :season AND i.week = :week" in statement
    assert "p.position IN" not in statement
    assert "JOIN sport_teams t ON t.sport = 'nfl' AND t.id = i.team_id" in statement
    assert "(i.report_status IS NOT NULL OR i.practice_status IS NOT NULL)" in statement
    assert "i.primary_injury, p.id, i.updated_at FROM nfl_player_injuries i" in statement
    assert "JOIN sport_players p ON p.sport = 'nfl'" in statement


def test_game_notes_injury_query_decodes_lineman_and_report_update_time() -> None:
    from unittest.mock import AsyncMock, Mock

    updated = datetime(2026, 10, 22, 12, tzinfo=UTC)
    result = Mock()
    result.fetchall.return_value = [(1, 'NE', 'Lineman', 'OT', 'Out', None, 'Ankle', 99, updated)]
    session = Mock()
    session.execute = AsyncMock(return_value=result)
    [row] = asyncio.run(nfl_repository.get_week_game_injuries(cast(AsyncSession, session), 2026, 7))
    assert row == {'team_id': 1, 'team': 'NE', 'player_name': 'Lineman', 'position': 'OT',
                   'injury_status': 'Out', 'practice_status': None, 'injury': 'Ankle', 'player_id': 99, 'updated_at': updated}


def test_game_notes_depth_rows_pair_this_week_with_a_strictly_earlier_chart() -> None:
    session = _RecordingSession()

    assert asyncio.run(nfl_repository.get_week_depth_rows(cast(AsyncSession, session), 2026, 3)) == []

    statement = _flat(session.statement)
    assert session.params == {"season": 2026, "week": 3}
    assert "FROM nfl_player_depth_charts WHERE season = :season AND week = :week" in statement
    assert "WHERE season < :season OR (season = :season AND week < :week)" in statement
    assert "FROM week_depth wd" in statement
    assert "LEFT JOIN previous_depth pd ON pd.player_id = wd.player_id" in statement
    assert "pd.depth_rank, p.id FROM week_depth wd" in statement


def test_game_notes_line_movement_is_pre_kickoff_from_one_lowercase_book() -> None:
    session = _RecordingSession()

    assert asyncio.run(nfl_repository.get_week_line_movement(cast(AsyncSession, session), 2026, 3)) == []

    statement = _flat(session.statement)
    assert session.params == {"season": 2026, "week": 3}
    assert "o.market IN ('spread', 'total')" in statement
    assert "o.book = lower(o.book)" in statement
    assert "(g.start_utc IS NULL OR o.fetched_at < g.start_utc)" in statement
    assert "ORDER BY game_id, market, (book = 'draftkings') DESC, COUNT(*) DESC, book" in statement
    # Open and current both come from the chosen book only.
    assert "FROM pre_kickoff p JOIN chosen_book c USING (game_id, market, book)" in statement
    assert "entry_line" not in statement


def test_game_notes_rest_reads_this_weeks_regular_season_games() -> None:
    session = _RecordingSession()

    assert asyncio.run(nfl_repository.get_week_game_rest(cast(AsyncSession, session), 2026, 3)) == {}

    statement = _flat(session.statement)
    assert "g.away_rest" in statement and "g.home_rest" in statement
    assert "g.away_score, g.home_score" in statement
    assert "WHERE g.sport = 'nfl' AND g.season = :season AND g.week = :week AND g.game_type = 'REG'" in statement


def test_game_notes_recent_results_are_completed_games_before_the_week_capped_per_team() -> None:
    session = _RecordingSession()

    assert asyncio.run(nfl_repository.get_week_team_recent_results(cast(AsyncSession, session), 2026, 3)) == {}

    statement = _flat(session.statement)
    assert session.params == {"season": 2026, "week": 3, "limit": 3}
    assert statement.count("g.season = :season AND g.week < :week AND g.game_type = 'REG' AND g.status = 'completed'") == 2
    assert "ROW_NUMBER() OVER (PARTITION BY tg.team_id ORDER BY tg.week DESC)" in statement
    assert "WHERE r.recency <= :limit" in statement


def test_gradeable_lines_can_narrow_to_one_player() -> None:
    session = _MappingSession([_gradeable_row()])

    asyncio.run(get_gradeable_prop_lines(cast(AsyncSession, session), 2026, player_id=9))

    [(sql, params)] = session.calls
    assert params == {"season": 2026, "player_id": 9}
    assert "AND l.fetched_at < g.start_utc AND l.player_id = :player_id" in sql


def test_player_profile_reads_the_roster_team_and_this_weeks_depth_and_injury() -> None:
    session = _MappingSession([{"id": 9, "name": "James Cook", "aliases": ["J. Cook"]}])

    profile = asyncio.run(nfl_repository.get_player_profile(cast(AsyncSession, session), 9, 2026, 4))

    [(sql, params)] = session.calls
    assert params == {"player_id": 9, "season": 2026, "week": 4}
    assert "player_teams AS" in sql and "LEFT JOIN player_teams pt ON pt.player_id = p.id" in sql
    assert "nfl_player_depth_charts d ON d.player_id = p.id AND d.season = :season AND d.week = :week" in sql
    assert "nfl_player_injuries i ON i.player_id = p.id AND i.season = :season AND i.week = :week" in sql
    assert profile == {"id": 9, "name": "James Cook", "aliases": ["J. Cook"]}


def test_player_profile_is_none_for_an_unknown_player() -> None:
    assert asyncio.run(nfl_repository.get_player_profile(cast(AsyncSession, _MappingSession([])), 9, 2026, 4)) is None


def test_player_game_rows_read_completed_regular_season_games_from_the_stat_rows_team() -> None:
    row = {
        "game_id": 3, "season": 2026, "week": 2, "opponent": "NE", "is_home": False, "team_score": 17,
        "opponent_score": 23, "team_spread": Decimal("2.5"), "roof": "outdoors", "snap_pct": 0.6,
        "passing_completions": 0, "passing_attempts": 0, "passing_yards": 0, "rushing_attempts": 14,
        "rushing_yards": 51, "targets": None, "receptions": 2, "receiving_yards": 9, "touchdowns": 0,
        "prizepicks_fantasy_points": Decimal("8.0"), "fg_made": 2, "pat_made": None, "punts": 0,
    }
    session = _MappingSession([row])

    [game] = asyncio.run(nfl_repository.get_player_game_rows(cast(AsyncSession, session), 9, 2026))

    [(sql, params)] = session.calls
    assert params == {"player_id": 9, "season": 2026, "previous_season": 2025}
    assert "g.game_type = 'REG' AND g.status = 'completed'" in sql
    assert "s.team_id = g.home_team_id AS is_home" in sql
    assert "CASE WHEN s.team_id = g.home_team_id THEN -g.spread_line ELSE g.spread_line END AS team_spread" in sql
    assert "LEFT JOIN nfl_player_snap_counts sc ON sc.player_id = s.player_id AND sc.game_id = s.game_id" in sql
    assert "ORDER BY g.season DESC, g.week DESC, g.id DESC" in sql
    assert (game.is_home, game.team_spread, game.snap_pct, game.targets, game.prizepicks_fantasy_points) == (False, 2.5, 0.6, None, 8.0)

    assert (game.fg_made, game.pat_made, game.punts) == (2, None, 0)
    assert "s.fg_made, s.pat_made, s.punts" in sql


def test_line_only_filter_lists_exactly_the_line_only_markets() -> None:
    expected = ", ".join(f"'{market.value}'" for market in NflLineOnlyMarket)
    assert nfl_repository.LINE_ONLY_MARKET_FILTER == f"l.market IN ({expected})"


def test_line_only_lines_take_each_props_last_full_game_snapshot_before_kickoff() -> None:
    fetched = datetime(2026, 10, 5, 18, 0, tzinfo=UTC)
    session = _ScriptedSession([(41, "Nick Folk", "K", "NYJ", "field_goals_made", "standard", Decimal("1.5"), fetched)])

    [line] = asyncio.run(nfl_repository.get_line_only_lines(cast(AsyncSession, session), 49))

    [(sql, params)] = session.calls
    assert params == {"game_id": 49}
    assert "DISTINCT ON (l.provider, l.provider_prop_id)" in sql
    assert "l.game_id = :game_id AND l.segment = 'full_game'" in sql
    assert "l.fetched_at < g.start_utc" in sql
    assert nfl_repository.LINE_ONLY_MARKET_FILTER in sql
    assert "JOIN sport_players p ON p.sport = 'nfl' AND p.id = l.player_id" in sql
    assert line == {"player_id": 41, "player_name": "Nick Folk", "position": "K", "team": "NYJ",
                    "market": "field_goals_made", "odds_type": "standard", "line": 1.5, "fetched_at": fetched}


def test_recent_stat_rows_stop_before_the_games_week_and_keep_the_last_five() -> None:
    session = _MappingSession([{"player_id": 41, "season": 2026, "week": 3, "opponent": "MIA", "fg_made": 2}])

    rows = asyncio.run(nfl_repository.get_recent_stat_rows(cast(AsyncSession, session), [41, 77], 2026, 4))

    [(sql, params)] = session.calls
    assert params == {"player_ids": [41, 77], "season": 2026, "week": 4, "limit": 5}
    assert "(s.season < :season OR (s.season = :season AND s.week < :week))" in sql
    assert "g.game_type = 'REG'" in sql
    assert "PARTITION BY s.player_id ORDER BY s.season DESC, s.week DESC" in sql
    assert "WHERE recency <= :limit" in sql
    for column in LINE_ONLY_COLUMNS:
        assert f"s.{column}" in sql
    assert rows == [{"player_id": 41, "season": 2026, "week": 3, "opponent": "MIA", "fg_made": 2}]


def test_week_line_only_props_preserve_sport_week_market_and_snapshot_boundaries() -> None:
    fetched = datetime(2026, 10, 5, 18, tzinfo=UTC)
    session = _ScriptedSession([(41, "Nick Folk", "K", "NYJ", "field_goals_made", "standard", Decimal("1.5"), fetched, 49)])
    [line] = asyncio.run(nfl_repository.get_week_line_only_lines(cast(AsyncSession, session), 2026, 7))
    [(sql, params)] = session.calls
    assert params == {"season": 2026, "week": 7}
    assert "g.season = :season AND g.week = :week AND g.game_type = 'REG'" in sql
    assert "WHERE l.sport = 'nfl'" in sql
    assert "JOIN sport_games g ON g.sport = 'nfl'" in sql
    assert "JOIN sport_players p ON p.sport = 'nfl'" in sql
    assert "l.segment = 'full_game' AND l.fetched_at < g.start_utc" in sql
    assert nfl_repository.LINE_ONLY_MARKET_FILTER in sql
    assert "DISTINCT ON (l.game_id, l.provider, l.provider_prop_id)" in sql
    assert "ORDER BY l.game_id, l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC" in sql
    assert line["game_id"] == 49 and line["line"] == 1.5
