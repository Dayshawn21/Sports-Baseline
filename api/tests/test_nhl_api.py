"""Fixtures trimmed from NHL responses for 2026-03-10; variants exercise missing data."""
import json
import asyncio
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timezone

import pytest
import httpx

from app.ingest.nhl_api import (
    ScheduleWeek, StatRow, StatsReport, parse_goalie_summary, parse_schedule_week, parse_skater_reports,
    _month_windows, _next_schedule_date, _retryable, _validate_report, latest_player_rows, run, select_stat_rows,
)

SCHEDULE: ScheduleWeek = json.loads('''{"gameWeek": [{"games": [
  {"id": 2025021013, "gameType": 2, "startTimeUTC": "2026-03-10T23:00:00Z",
   "gameState": "OFF", "gameScheduleState": "OK", "gameOutcome": {"lastPeriodType": "REG"},
   "homeTeam": {"abbrev": "BUF", "placeName": {"default": "Buffalo"}, "commonName": {"default": "Sabres"}, "score": 6},
   "awayTeam": {"abbrev": "SJS", "placeName": {"default": "San Jose"}, "commonName": {"default": "Sharks"}, "score": 3}},
  {"id": 2025021012, "gameType": 2, "startTimeUTC": "2026-03-10T23:00:00Z",
   "gameState": "OFF", "gameScheduleState": "OK", "gameOutcome": {"lastPeriodType": "OT"},
   "homeTeam": {"abbrev": "BOS", "placeName": {"default": "Boston"}, "commonName": {"default": "Bruins"}, "score": 2},
   "awayTeam": {"abbrev": "LAK", "placeName": {"default": "Los Angeles"}, "commonName": {"default": "Kings"}, "score": 1}},
  {"id": 2025021018, "gameType": 2, "startTimeUTC": "2026-03-10T23:00:00Z",
   "gameState": "OFF", "gameScheduleState": "OK", "gameOutcome": {"lastPeriodType": "SO"},
   "homeTeam": {"abbrev": "CAR", "placeName": {"default": "Carolina"}, "commonName": {"default": "Hurricanes"}, "score": 5},
   "awayTeam": {"abbrev": "PIT", "placeName": {"default": "Pittsburgh"}, "commonName": {"default": "Penguins"}, "score": 4}}
]}]}''')
SKATER: StatRow = {
    "playerId": 8482100, "gameId": 2025021018, "skaterFullName": "Alexander Nikishin",
    "positionCode": "D", "teamAbbrev": "CAR", "opponentTeamAbbrev": "PIT", "homeRoad": "H",
    "goals": 1, "assists": 1, "points": 2, "shots": 2, "plusMinus": 2, "penaltyMinutes": 2,
    "ppGoals": 1, "ppPoints": 1, "shPoints": 0, "otGoals": 0, "timeOnIcePerGame": 1189.0,
}
REALTIME: StatRow = {
    "playerId": 8482100, "gameId": 2025021018, "hits": 2, "blockedShots": 0, "giveaways": 1, "takeaways": 0,
}
FACEOFFS: StatRow = {
    "playerId": 8482100, "gameId": 2025021018, "totalFaceoffWins": 0, "totalFaceoffLosses": 0,
}
GOALIE: StatRow = {
    "playerId": 8475883, "gameId": 2025021018, "goalieFullName": "Frederik Andersen",
    "teamAbbrev": "CAR", "opponentTeamAbbrev": "PIT", "homeRoad": "H", "gamesStarted": 1,
    "wins": 1, "losses": 0, "otLosses": 0, "timeOnIce": 3900, "saves": 24, "shotsAgainst": 28, "goalsAgainst": 4,
}


def _report(*rows: StatRow) -> StatsReport:
    return {"data": list(rows), "total": len(rows)}


@pytest.mark.parametrize(
    ("index", "game_id", "period", "scores"),
    [(0, "2025021013", "REG", (6, 3)), (1, "2025021012", "OT", (2, 1)), (2, "2025021018", "SO", (5, 4))],
)
def test_finals_preserve_official_scores_and_period(index: int, game_id: str, period: str, scores: tuple[int, int]) -> None:
    games, skipped = parse_schedule_week(SCHEDULE)
    game = games[index]
    assert not skipped
    assert (game.game_id, game.season, game.game_type, game.week) == (game_id, 2025, "REG", None)
    assert game.start_utc == datetime(2026, 3, 10, 23, tzinfo=timezone.utc)
    assert game.game_date == date(2026, 3, 10)
    assert (game.home_score, game.away_score) == scores
    assert (game.status, game.end_period) == ("completed", period)


def test_eastern_date_and_accented_team_name() -> None:
    payload = deepcopy(SCHEDULE)
    row = payload["gameWeek"][0]["games"][0]
    row["startTimeUTC"] = "2026-03-11T02:00:00Z"
    row["homeTeam"] = {
        "abbrev": "MTL", "placeName": {"default": "Montréal"}, "commonName": {"default": "Canadiens"}, "score": 3,
    }
    games, _ = parse_schedule_week(payload)
    assert games[0].start_utc == datetime(2026, 3, 11, 2, tzinfo=timezone.utc)
    assert games[0].game_date == date(2026, 3, 10)
    assert (games[0].home_team, games[0].home_team_name) == ("MTL", "Montréal Canadiens")


@pytest.mark.parametrize(
    ("state", "schedule_state", "expected"),
    [("FUT", "OK", "scheduled"), ("LIVE", "OK", "scheduled"),
     ("FUT", "PPD", "postponed"), ("FINAL", "CNCL", "canceled")],
)
def test_nonfinal_games_hide_scores_and_outcome(state: str, schedule_state: str, expected: str) -> None:
    payload = deepcopy(SCHEDULE)
    for row in payload["gameWeek"][0]["games"]:
        row.update(gameState=state, gameScheduleState=schedule_state)
    games, _ = parse_schedule_week(payload)
    assert all((g.status, g.home_score, g.away_score, g.end_period) == (expected, None, None, None) for g in games)


def test_future_game_needs_no_score_or_outcome_fields() -> None:
    payload = deepcopy(SCHEDULE)
    for row in payload["gameWeek"][0]["games"]:
        row["gameState"] = "FUT"
        del row["gameOutcome"], row["homeTeam"]["score"], row["awayTeam"]["score"]
    games, skipped = parse_schedule_week(payload)
    assert len(games) == 3 and not skipped
    assert all(g.home_score is None and g.away_score is None and g.end_period is None for g in games)


def test_excluded_game_types_are_counted_before_parsing() -> None:
    payload = deepcopy(SCHEDULE)
    for row, kind in zip(payload["gameWeek"][0]["games"], (1, 4, 99)):
        row["gameType"] = kind
        row["startTimeUTC"] = "not parsed"
    games, skipped = parse_schedule_week(payload)
    assert games == []
    assert skipped == {"game_type_1": 1, "game_type_4": 1, "game_type_99": 1}


def test_playoffs_keep_start_year_and_no_week() -> None:
    payload = deepcopy(SCHEDULE)
    row = payload["gameWeek"][0]["games"][0]
    row.update(id=2025030111, gameType=3, startTimeUTC="2026-04-20T23:00:00Z")
    games, _ = parse_schedule_week(payload)
    assert (games[0].season, games[0].game_type, games[0].week) == (2025, "PST", None)


def test_schedule_rejects_ambiguous_start_time() -> None:
    payload = deepcopy(SCHEDULE)
    payload["gameWeek"][0]["games"][0]["startTimeUTC"] = "2026-03-10T23:00:00"
    with pytest.raises(ValueError, match="without a UTC offset"):
        parse_schedule_week(payload)


def test_skater_maps_all_three_reports_and_preserves_zero() -> None:
    rows, skipped = parse_skater_reports(_report(SKATER), _report(REALTIME), _report(FACEOFFS))
    row = rows[0]
    assert not skipped
    assert (row.player_id, row.game_id, row.player_name, row.position) == (
        "8482100", "2025021018", "Alexander Nikishin", "D",
    )
    assert (row.team, row.opponent, row.season, row.is_home) == ("CAR", "PIT", 2025, True)
    assert (row.goals, row.assists, row.points, row.shots, row.plus_minus, row.penalty_minutes) == (1, 1, 2, 2, 2, 2)
    assert (row.power_play_goals, row.power_play_points, row.shorthanded_points, row.ot_goals) == (1, 1, 0, 0)
    assert (row.hits, row.blocked_shots, row.giveaways, row.takeaways) == (2, 0, 1, 0)
    assert (row.faceoffs_won, row.faceoffs_lost, row.time_on_ice_seconds) == (0, 0, 1189)
    assert isinstance(row.time_on_ice_seconds, int)


@pytest.mark.parametrize(("with_live", "with_faceoffs"), [(False, True), (True, False), (False, False)])
def test_missing_supplementary_report_stays_null(with_live: bool, with_faceoffs: bool) -> None:
    rows, _ = parse_skater_reports(
        _report(SKATER), _report(REALTIME) if with_live else _report(), _report(FACEOFFS) if with_faceoffs else _report(),
    )
    row = rows[0]
    assert row.hits == (2 if with_live else None)
    assert row.blocked_shots == (0 if with_live else None)
    assert row.giveaways == (1 if with_live else None)
    assert row.takeaways == (0 if with_live else None)
    assert row.faceoffs_won == (0 if with_faceoffs else None)
    assert row.faceoffs_lost == (0 if with_faceoffs else None)
    assert row.goals == 1


def test_report_join_uses_both_player_and_game_and_keeps_summary_roster() -> None:
    same_player_other_game = {**SKATER, "gameId": 2025021019, "homeRoad": "R"}
    same_game_other_player = {**SKATER, "playerId": 8482101}
    rows, skipped = parse_skater_reports(
        _report(SKATER, same_player_other_game, same_game_other_player),
        _report(REALTIME, {**REALTIME, "playerId": 9999999}), _report(FACEOFFS),
    )
    assert len(rows) == 3 and not skipped
    assert rows[0].hits == 2
    assert rows[1].hits is None and rows[1].faceoffs_won is None and rows[1].is_home is False
    assert rows[2].hits is None and rows[2].faceoffs_won is None


def test_missing_stat_columns_are_not_filled_with_zero() -> None:
    row = {key: value for key, value in SKATER.items() if key not in ("goals", "timeOnIcePerGame", "positionCode")}
    rows, _ = parse_skater_reports(_report(row), _report(), _report())
    assert (rows[0].goals, rows[0].time_on_ice_seconds, rows[0].position) == (None, None, None)


def test_nonzero_faceoff_counts_and_negative_plus_minus() -> None:
    rows, _ = parse_skater_reports(
        _report({**SKATER, "plusMinus": -2}), _report(),
        _report({**FACEOFFS, "totalFaceoffWins": 7, "totalFaceoffLosses": 3}),
    )
    assert (rows[0].faceoffs_won, rows[0].faceoffs_lost, rows[0].plus_minus) == (7, 3, -2)


@pytest.mark.parametrize(
    ("wins", "losses", "ot_losses", "started", "expected"),
    [(1, 0, 0, 1, "W"), (0, 1, 0, 1, "L"), (0, 0, 1, 1, "O"), (0, 0, 0, 0, None)],
)
def test_goalie_decision_and_started(wins: int, losses: int, ot_losses: int, started: int, expected: str | None) -> None:
    raw = {**GOALIE, "wins": wins, "losses": losses, "otLosses": ot_losses, "gamesStarted": started}
    rows, skipped = parse_goalie_summary(_report(raw))
    row = rows[0]
    assert not skipped
    assert (row.player_id, row.player_name, row.position, row.season) == ("8475883", "Frederik Andersen", "G", 2025)
    assert (row.saves, row.shots_against, row.goals_against, row.time_on_ice_seconds) == (24, 28, 4, 3900)
    assert row.started is bool(started)
    assert row.decision == expected


def test_goalie_away_and_missing_stats_remain_unavailable() -> None:
    row = {**GOALIE, "homeRoad": "R", "saves": None, "timeOnIce": None, "wins": None}
    rows, _ = parse_goalie_summary(_report(row))
    assert rows[0].is_home is False
    assert (rows[0].saves, rows[0].time_on_ice_seconds, rows[0].decision) == (None, None, None)
    assert parse_goalie_summary(_report()) == ([], {})


@pytest.mark.parametrize("key", ["playerId", "gameId"])
@pytest.mark.parametrize("value", [None, ""])
def test_missing_stat_ids_are_skipped_and_counted_in_each_report(key: str, value: None | str) -> None:
    bad = {**SKATER, key: value}
    rows, skipped = parse_skater_reports(_report(SKATER, bad), _report(bad), _report(bad))
    suffix = "missing_player_id" if key == "playerId" else "missing_game_id"
    assert len(rows) == 1
    assert skipped == {f"summary_{suffix}": 1, f"realtime_{suffix}": 1, f"faceoffwins_{suffix}": 1}
    goalies, goalie_skips = parse_goalie_summary(_report({**GOALIE, key: value}))
    assert goalies == [] and goalie_skips == {f"goalie_{suffix}": 1}


@pytest.mark.parametrize("key", ["playerId", "gameId"])
def test_absent_stat_id_fields_are_skipped(key: str) -> None:
    raw = {k: v for k, v in SKATER.items() if k != key}
    rows, skipped = parse_skater_reports(_report(raw), _report(), _report())
    suffix = "missing_player_id" if key == "playerId" else "missing_game_id"
    assert rows == [] and skipped == {f"summary_{suffix}": 1}
    goalies, goalie_skips = parse_goalie_summary(_report({k: v for k, v in GOALIE.items() if k != key}))
    assert goalies == [] and goalie_skips == {f"goalie_{suffix}": 1}


def test_unknown_home_road_is_skipped_instead_of_becoming_away() -> None:
    rows, skipped = parse_skater_reports(_report({**SKATER, "homeRoad": None}), _report(), _report())
    assert rows == [] and skipped == {"summary_invalid_home_road": 1}
    goalies, goalie_skips = parse_goalie_summary(_report({**GOALIE, "homeRoad": "?"}))
    assert goalies == [] and goalie_skips == {"goalie_invalid_home_road": 1}


def test_parser_outputs_are_frozen() -> None:
    games, _ = parse_schedule_week(SCHEDULE)
    skaters, _ = parse_skater_reports(_report(SKATER), _report(), _report())
    goalies, _ = parse_goalie_summary(_report(GOALIE))
    for row in (games[0], skaters[0], goalies[0]):
        with pytest.raises(FrozenInstanceError):
            row.season = 2026


def test_month_windows_are_inclusive_disjoint_and_handle_leap_year() -> None:
    assert list(_month_windows(date(2024, 1, 30), date(2024, 3, 2))) == [
        (date(2024, 1, 30), date(2024, 1, 31)),
        (date(2024, 2, 1), date(2024, 2, 29)),
        (date(2024, 3, 1), date(2024, 3, 2)),
    ]
    assert list(_month_windows(date(2026, 12, 31), date(2027, 1, 1))) == [
        (date(2026, 12, 31), date(2026, 12, 31)), (date(2027, 1, 1), date(2027, 1, 1)),
    ]
    assert list(_month_windows(date(2026, 10, 24), date(2026, 10, 23))) == []


def test_schedule_pager_stops_at_last_published_week_and_rejects_loops() -> None:
    assert _next_schedule_date({"gameWeek": [], "nextStartDate": "2026-10-06"}, date(2026, 9, 29)) == date(2026, 10, 6)
    assert _next_schedule_date({"gameWeek": []}, date(2027, 4, 6)) is None
    for value in ("2026-09-29", "2026-09-22"):
        with pytest.raises(ValueError, match="did not advance"):
            _next_schedule_date({"gameWeek": [], "nextStartDate": value}, date(2026, 9, 29))


def test_report_total_guard_rejects_partial_and_excess_rows() -> None:
    _validate_report(_report(SKATER), "skater/summary")
    _validate_report(_report(), "empty")
    for total in (0, 2):
        with pytest.raises(ValueError, match=f"truncated: total {total}, received 1"):
            _validate_report({"data": [SKATER], "total": total}, "skater/summary")


def test_selection_keeps_only_completed_known_games_and_matching_sides() -> None:
    games, _ = parse_schedule_week(SCHEDULE)
    skaters, _ = parse_skater_reports(_report(SKATER), _report(), _report())
    row = skaters[0]
    games.extend([
        replace(games[2], game_id="future", status="scheduled"),
        replace(games[2], game_id="old", game_date=date(2026, 3, 1)),
    ])
    candidates = [row, replace(row, game_id="unknown"), replace(row, game_id="future"),
                  replace(row, game_id="old"), replace(row, is_home=False),
                  replace(row, team="UNKNOWN"), replace(row, is_home=False, team="PIT", opponent="CAR")]
    selected, skipped = select_stat_rows(candidates, games, date(2026, 3, 10), date(2026, 3, 10), "skater")
    assert selected == [row, candidates[-1]]
    assert skipped == {"skater_game_not_stored": 1, "skater_game_not_completed": 1,
                       "skater_outside_window": 1, "skater_team_mismatch": 2}
    goalies, _ = parse_goalie_summary(_report(GOALIE))
    selected_goalies, counts = select_stat_rows(
        [goalies[0], replace(goalies[0], game_id="future")], games, date(2026, 3, 10), date(2026, 3, 10), "goalie",
    )
    assert selected_goalies == goalies and counts == {"goalie_game_not_completed": 1}


def test_latest_player_uses_game_time_instead_of_report_order() -> None:
    games, _ = parse_schedule_week(SCHEDULE)
    skaters, _ = parse_skater_reports(_report(SKATER), _report(), _report())
    goalies, _ = parse_goalie_summary(_report(GOALIE))
    newer_game = replace(games[2], game_id="later", start_utc=datetime(2026, 3, 11, 23, tzinfo=timezone.utc))
    newer_row = replace(skaters[0], game_id="later", team="PIT")
    rows = latest_player_rows([newer_row, goalies[0], skaters[0]], [*games, newer_game])
    assert {row.player_id: row for row in rows} == {newer_row.player_id: newer_row, goalies[0].player_id: goalies[0]}


@pytest.mark.parametrize("status", [400, 404, 429, 500, 503])
def test_only_transport_errors_and_server_errors_are_retried(status: int) -> None:
    request = httpx.Request("GET", "https://example.test/nhl")
    error = httpx.HTTPStatusError("failed", request=request, response=httpx.Response(status, request=request))
    assert _retryable(error) is (status >= 500)
    assert _retryable(httpx.ConnectError("unavailable"))
    assert not _retryable(ValueError("malformed payload"))


@pytest.mark.parametrize(("season", "days_back"), [(2022, None), (2027, None), (2026, -1)])
def test_invalid_cli_inputs_fail_before_any_http_or_database_call(season: int, days_back: int | None) -> None:
    with pytest.raises(ValueError):
        asyncio.run(run(season, days_back, True, today=date(2026, 10, 23)))
