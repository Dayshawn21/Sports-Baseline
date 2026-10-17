from dataclasses import replace
from datetime import date, datetime, timezone

from app.ingest.hoopr_nba import (
    latest_teams,
    parse_player_box,
    parse_schedule,
    player_box_url,
    schedule_url,
    select_player_games,
)

SCHEDULE_HEADER = (
    "game_id,season,season_type,game_date,start_date,status_type_completed,status_type_name,"
    "home_abbreviation,home_display_name,home_score,away_abbreviation,away_display_name,away_score,"
    "type_abbreviation"
)
SCHEDULE_CSV = "\n".join([
    SCHEDULE_HEADER,
    "401,2027,2,2026-10-20,2026-10-20T23:30Z,false,STATUS_SCHEDULED,DET,Detroit Pistons,,BOS,Boston Celtics,",
    "402,2027,2,2026-10-27,2026-10-28T00:00Z,true,STATUS_FINAL,NY,New York Knicks,110,PHI,Philadelphia 76ers,104",
    "403,2027,5,2027-04-14,2027-04-14T23:00Z,true,STATUS_FINAL,MIA,Miami Heat,99,CHI,Chicago Bulls,101",
    "404,2027,3,2027-04-18,2027-04-18T17:00Z,false,STATUS_SCHEDULED,OKC,Oklahoma City Thunder,,SA,San Antonio Spurs,",
    "405,2027,1,2026-10-05,2026-10-05T23:00Z,true,STATUS_FINAL,ATL,Atlanta Hawks,100,MEM,Memphis Grizzlies,95",
    "406,2027,2,2026-12-16,,false,STATUS_SCHEDULED,TBD,TBD,,TBD,TBD,",
    "407,2027,2,2027-01-08,2027-01-09T01:00Z,false,STATUS_POSTPONED,CHI,Chicago Bulls,,MIA,Miami Heat,",
    "408,2027,2,2027-02-14,2027-02-15T01:00Z,true,STATUS_FINAL,STARS,Team Stars,40,WORLD,Team World,38,ALLSTAR",
    "409,2027,2,2026-12-15,2026-12-16T01:30Z,true,STATUS_FINAL,UTAH,Utah Jazz,120,NY,New York Knicks,118,CC",
])

BOX_HEADER = (
    "game_id,season,athlete_id,athlete_display_name,athlete_position_abbreviation,team_abbreviation,"
    "opponent_team_abbreviation,home_away,starter,did_not_play,reason,minutes,points,rebounds,"
    "offensive_rebounds,defensive_rebounds,assists,steals,blocks,turnovers,fouls,field_goals_made,"
    "field_goals_attempted,three_point_field_goals_made,three_point_field_goals_attempted,"
    "free_throws_made,free_throws_attempted,plus_minus"
)
BOX_CSV = "\n".join([
    BOX_HEADER,
    "402,2027,3934719,OG Anunoby,F,NY,PHI,home,true,false,COACH'S DECISION,33.0,11,8,0,8,0,3,1,1,5,3,11,1,5,4,6,+2",
    "402,2027,4397020,Bench Guy,G,NY,PHI,home,false,false,,12.5,4,1,0,1,2,0,0,0,1,2,5,0,2,0,0,-7",
    "402,2027,555,Sat Out,C,PHI,NY,away,false,true,COACH'S DECISION,,,,,,,,,,,,,,,,,",
    "402,2027,,Team Row,,NY,PHI,home,false,false,,,,,,,,,,,,,,,,,,",
    ",2027,777,No Game,G,NY,PHI,home,false,false,,10,2,1,0,1,0,0,0,0,0,1,2,0,0,0,0,",
])


def _by_id(games):
    return {game.game_id: game for game in games}


def test_urls_use_the_file_season():
    assert schedule_url(2027).endswith("/espn_nba_schedules/nba_schedule_2027.csv")
    assert player_box_url(2026).endswith("/espn_nba_player_boxscores/player_box_2026.csv")


def test_schedule_parses_regular_play_in_and_playoff_games():
    games, _ = parse_schedule(SCHEDULE_CSV)
    by_id = _by_id(games)
    assert set(by_id) == {"401", "402", "403", "404", "407", "409"}

    opener = by_id["401"]
    assert (opener.season, opener.game_type, opener.week) == (2026, "REG", 1)
    assert opener.game_date == date(2026, 10, 20)
    assert opener.start_utc == datetime(2026, 10, 20, 23, 30, tzinfo=timezone.utc)
    assert (opener.home_score, opener.away_score, opener.status) == (None, None, "scheduled")
    assert (opener.home_team, opener.home_team_name, opener.away_team) == ("DET", "Detroit Pistons", "BOS")

    final = by_id["402"]
    assert (final.week, final.home_score, final.away_score, final.status) == (2, 110, 104, "completed")
    # The tip is after midnight UTC but the game keeps ESPN's Eastern date.
    assert final.game_date == date(2026, 10, 27)

    assert (by_id["403"].game_type, by_id["403"].week) == ("PIN", None)
    assert (by_id["404"].game_type, by_id["404"].week, by_id["404"].home_score) == ("PST", None, None)


def test_postponed_game_is_kept_as_postponed_with_no_score():
    games, _ = parse_schedule(SCHEDULE_CSV)
    postponed = _by_id(games)["407"]
    assert (postponed.status, postponed.home_score, postponed.game_type, postponed.week) == ("postponed", None, "REG", 12)


def test_schedule_skips_preseason_and_placeholder_games():
    _, skipped = parse_schedule(SCHEDULE_CSV)
    assert skipped == {"not_regular_or_postseason": 1, "placeholder_team": 1, "all_star": 1}


def test_cup_final_stays_a_regular_season_game():
    games, _ = parse_schedule(SCHEDULE_CSV)
    cup_final = _by_id(games)["409"]
    assert (cup_final.game_type, cup_final.week, cup_final.home_team) == ("REG", 9, "UTAH")


def test_box_scores_parse_stats_and_signed_plus_minus():
    rows, _ = parse_player_box(BOX_CSV)
    starter, bench = rows[0], rows[1]
    assert (starter.player_id, starter.team, starter.opponent, starter.season) == ("3934719", "NY", "PHI", 2026)
    assert (starter.is_home, starter.starter, starter.did_not_play) == (True, True, False)
    assert (starter.minutes, starter.points, starter.rebounds, starter.assists) == (33.0, 11, 8, 0)
    assert (starter.three_pointers_made, starter.three_pointers_attempted) == (1, 5)
    assert starter.plus_minus == 2
    # ESPN puts a reason on players who played; only a DNP keeps it.
    assert starter.dnp_reason is None
    assert (bench.minutes, bench.plus_minus) == (12.5, -7)


def test_dnp_row_keeps_null_stats():
    rows, _ = parse_player_box(BOX_CSV)
    dnp = rows[2]
    assert (dnp.did_not_play, dnp.dnp_reason, dnp.is_home) == (True, "COACH'S DECISION", False)
    assert (dnp.minutes, dnp.points, dnp.rebounds, dnp.plus_minus) == (None, None, None, None)


def test_box_scores_skip_rows_without_ids():
    rows, skipped = parse_player_box(BOX_CSV)
    assert len(rows) == 3
    assert skipped == {"missing_athlete_id": 1, "missing_game_id": 1}


def test_select_skips_rows_for_games_not_in_the_schedule():
    games, _ = parse_schedule(SCHEDULE_CSV)
    rows, _ = parse_player_box(BOX_CSV)
    selected, skipped = select_player_games(rows + [replace(rows[0], game_id="999")], games, since=None)
    assert len(selected) == 3
    assert skipped == {"box_game_not_stored": 1}


def test_select_keeps_only_games_on_or_after_since():
    games, _ = parse_schedule(SCHEDULE_CSV)
    rows, _ = parse_player_box(BOX_CSV)
    assert len(select_player_games(rows, games, since=date(2026, 10, 27))[0]) == 3
    assert select_player_games(rows, games, since=date(2026, 10, 28))[0] == []


def test_select_skips_rows_whose_team_is_not_in_the_schedule():
    games, _ = parse_schedule(SCHEDULE_CSV)
    rows, _ = parse_player_box(BOX_CSV)
    _, skipped = select_player_games([replace(rows[0], team="XYZ")], games, since=None)
    assert skipped == {"box_team_unknown": 1}


def test_latest_team_follows_the_most_recent_game():
    games, _ = parse_schedule(SCHEDULE_CSV)
    rows, _ = parse_player_box(BOX_CSV)
    traded = replace(rows[0], game_id="403", team="MIA", opponent="CHI")
    assert latest_teams([rows[0], traded], games)["3934719"] == "MIA"
    assert latest_teams([traded, rows[0]], games)["3934719"] == "MIA"
