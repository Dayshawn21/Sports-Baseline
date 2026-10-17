from datetime import date, datetime, timezone

from app.ingest.espn_nba_preseason import parse_scoreboard, parse_summary, scoreboard_date


def _event(event_id, start, season_type, completed, home=("ATL", "Atlanta Hawks", "123"), away=("MEM", "Memphis Grizzlies", "132")):
    return {
        "id": event_id,
        "date": start,
        "season": {"year": 2027, "type": season_type},
        "status": {"type": {"name": "STATUS_FINAL" if completed else "STATUS_SCHEDULED", "completed": completed}},
        "competitions": [{"competitors": [
            {"homeAway": "home", "score": home[2], "team": {"abbreviation": home[0], "displayName": home[1]}},
            {"homeAway": "away", "score": away[2], "team": {"abbreviation": away[0], "displayName": away[1]}},
        ]}],
    }


SCOREBOARD = {"events": [
    _event("401898388", "2026-10-05T23:00Z", 1, True),
    _event("401898400", "2026-10-07T00:30Z", 1, False, home=("LAL", "Los Angeles Lakers", "0"), away=("GS", "Golden State Warriors", "0")),
    _event("401910001", "2026-10-21T23:30Z", 2, False),
    _event("401914130", "2026-10-12T02:00Z", 1, True, home=("POR", "Portland Trail Blazers", "130"), away=("LON", "London Lions", "90")),
]}

KEYS = [
    "minutes", "points", "fieldGoalsMade-fieldGoalsAttempted", "threePointFieldGoalsMade-threePointFieldGoalsAttempted",
    "freeThrowsMade-freeThrowsAttempted", "rebounds", "assists", "turnovers", "steals", "blocks",
    "offensiveRebounds", "defensiveRebounds", "fouls", "plusMinus",
]


def _athlete(athlete_id, name, stats, starter=False, did_not_play=False, reason=None):
    return {
        "athlete": {"id": athlete_id, "displayName": name, "position": {"abbreviation": "F"}} if athlete_id else {"displayName": name},
        "starter": starter, "didNotPlay": did_not_play, "reason": reason, "stats": stats,
    }


SUMMARY = {"boxscore": {"players": [
    {"team": {"abbreviation": "MEM"}, "statistics": [{"keys": KEYS, "athletes": [
        _athlete("4903027", "Cedric Coward", ["18", "9", "3-6", "1-3", "2-2", "5", "4", "2", "1", "0", "1", "4", "2", "+5"], starter=True, reason="COACH'S DECISION"),
        _athlete("111", "Sat Out", [], did_not_play=True, reason="COACH'S DECISION"),
        _athlete(None, "No Id", ["1", "0", "0-0", "0-0", "0-0", "0", "0", "0", "0", "0", "0", "0", "0", "0"]),
    ]}]},
    {"team": {"abbreviation": "ATL"}, "statistics": [{"keys": KEYS, "athletes": [
        _athlete("222", "Home Player", ["30", "20", "8-15", "2-5", "2-3", "6", "3", "1", "0", "1", "2", "4", "3", "-3"], starter=True),
    ]}]},
]}}


def test_scoreboard_keeps_preseason_games_between_nba_teams_only():
    games = parse_scoreboard(SCOREBOARD)
    assert [game.game_id for game in games] == ["401898388", "401898400"]


def test_preseason_game_fields():
    final = parse_scoreboard(SCOREBOARD)[0]
    assert (final.game_type, final.week, final.season) == ("PRE", None, 2026)
    assert final.game_date == date(2026, 10, 5)
    assert final.start_utc == datetime(2026, 10, 5, 23, 0, tzinfo=timezone.utc)
    assert (final.home_team, final.away_team, final.home_score, final.away_score) == ("ATL", "MEM", 123, 132)
    assert final.status == "completed"


def test_late_tip_takes_the_eastern_date_and_has_no_score_until_final():
    late = parse_scoreboard(SCOREBOARD)[1]
    assert late.game_date == date(2026, 10, 6)
    assert (late.status, late.home_score, late.away_score) == ("scheduled", None, None)


def test_summary_parses_box_scores():
    game = parse_scoreboard(SCOREBOARD)[0]
    rows = {row.player_id: row for row in parse_summary(SUMMARY, game)}
    coward = rows["4903027"]
    assert (coward.team, coward.opponent, coward.is_home, coward.starter, coward.season) == ("MEM", "ATL", False, True, 2026)
    assert (coward.minutes, coward.points, coward.rebounds, coward.assists) == (18.0, 9, 5, 4)
    assert (coward.field_goals_made, coward.field_goals_attempted) == (3, 6)
    assert (coward.three_pointers_made, coward.three_pointers_attempted) == (1, 3)
    assert (coward.free_throws_made, coward.free_throws_attempted) == (2, 2)
    assert (coward.offensive_rebounds, coward.defensive_rebounds, coward.fouls) == (1, 4, 2)
    assert (coward.plus_minus, coward.dnp_reason) == (5, None)
    home = rows["222"]
    assert (home.is_home, home.opponent, home.plus_minus) == (True, "MEM", -3)


def test_dnp_keeps_null_stats_and_missing_ids_are_skipped():
    game = parse_scoreboard(SCOREBOARD)[0]
    rows = {row.player_id: row for row in parse_summary(SUMMARY, game)}
    assert set(rows) == {"4903027", "111", "222"}
    dnp = rows["111"]
    assert (dnp.did_not_play, dnp.dnp_reason) == (True, "COACH'S DECISION")
    assert (dnp.minutes, dnp.points, dnp.field_goals_made, dnp.plus_minus) == (None, None, None, None)


def test_scoreboard_date_format():
    assert scoreboard_date(date(2026, 10, 5)) == "20261005"
