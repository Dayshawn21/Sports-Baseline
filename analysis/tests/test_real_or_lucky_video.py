from dataclasses import replace
import json

import pandas as pd
import pytest

from lib import nfl_team_report as report
from lib import real_or_lucky_video as video
from lib import team_posts
from lib.real_or_lucky_posts import VERDICT_SENTENCES

# Week 1: MIN beats DET by exactly 8 (one score), GB and CHI tie. Week 2: MIN loses at CHI by 9, DET beats GB.
# Week 3 is not played yet, so the cutoff is week 2.
GAMES = pd.DataFrame(
    [(1, 2026, 1, "MIN", "DET", 20, 12, "completed"), (2, 2026, 1, "GB", "CHI", 10, 10, "completed"),
     (3, 2026, 2, "CHI", "MIN", 30, 21, "completed"), (4, 2026, 2, "DET", "GB", 24, 21, "completed"),
     (5, 2026, 3, "MIN", "GB", None, None, "scheduled")],
    columns=["game_id", "season", "week", "home", "away", "home_score", "away_score", "status"],
)
EFFICIENCY = pd.DataFrame(
    [(gid, team, 10, 1.0, 5) for gid in (1, 2, 3, 4) for team in ("MIN", "DET", "GB", "CHI")],
    columns=["game_id", "team", "plays", "epa", "successes"],
)
GIVEAWAYS = pd.DataFrame(
    [(1, "MIN", 0), (1, "DET", 2), (2, "GB", 1), (2, "CHI", 1), (3, "CHI", 1), (3, "MIN", 1),
     (4, "DET", 0), (4, "GB", 1)],
    columns=["game_id", "team", "giveaways"],
)
SNAPSHOT = report.season_snapshot("MIN", 2026, report.last_final_week(GAMES, 2026), games=GAMES,
                                  efficiency=EFFICIENCY, giveaways=GIVEAWAYS)
DATA = video.video_data(SNAPSHOT, GAMES, turnover_carryover=0.3141)


def test_fields_come_from_the_snapshot():
    assert (DATA["team"], DATA["nickname"], DATA["teamName"]) == ("MIN", "Vikings", "Minnesota Vikings")
    assert (DATA["season"], DATA["throughWeek"], DATA["record"]) == (2026, 2, "1-1")
    assert DATA["pointsRecord"] == report.points_record(SNAPSHOT.pythagorean_wins, 2)
    assert DATA["actualWins"] == 1.0
    assert DATA["pythagoreanWins"] == round(SNAPSHOT.pythagorean_wins, 2)
    assert (DATA["oneScoreWins"], DATA["oneScoreLosses"]) == (1, 0)
    assert (DATA["turnoverMargin"], DATA["turnoverMarginRank"]) == (SNAPSHOT.turnover_margin,
                                                                    SNAPSHOT.turnover_margin_rank)
    assert DATA["turnoverCarryover"] == 0.31
    assert (DATA["offenseEpaRank"], DATA["defenseEpaRank"]) == (SNAPSHOT.offense_epa_rank,
                                                                SNAPSHOT.defense_epa_rank)
    assert DATA["source"] == "Source: nflverse · data through week 2, 2026"


def test_games_are_in_week_order_through_the_cutoff_with_the_one_score_edge_at_8():
    assert DATA["games"] == [
        {"week": 1, "opponent": "Lions", "home": True, "scored": 20, "allowed": 12, "margin": 8, "oneScore": True},
        {"week": 2, "opponent": "Bears", "home": False, "scored": 21, "allowed": 30, "margin": -9,
         "oneScore": False},
    ]


def test_ties_count_as_half_a_win():
    snap = report.season_snapshot("GB", 2026, 2, games=GAMES, efficiency=EFFICIENCY, giveaways=GIVEAWAYS)
    data = video.video_data(snap, GAMES, turnover_carryover=0.31)
    assert (data["record"], data["actualWins"]) == ("0-1-1", 0.5)


def test_verdict_sentence_matches_the_posts():
    assert DATA["verdict"] == report.real_verdict(SNAPSHOT)
    assert DATA["verdictSentence"] == VERDICT_SENTENCES[DATA["verdict"]]
    assert "disclaimer" not in DATA


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


@pytest.mark.parametrize("team", ["MIN", "DET", "GB", "CHI"])
def test_no_dash_or_betting_language(team):
    snap = report.season_snapshot(team, 2026, 2, games=GAMES, efficiency=EFFICIENCY, giveaways=GIVEAWAYS)
    data = video.video_data(snap, GAMES, turnover_carryover=0.31)
    for text in strings(data):
        assert "\u2014" not in text and "\u2013" not in text
        assert not team_posts.BANNED_WORDS.search(text)


def test_round_trips_through_json():
    assert json.loads(json.dumps(DATA)) == DATA


def test_league_has_every_team_through_the_cutoff_with_ties_as_half():
    table = report.standings(GAMES, 2026, 2)
    assert [dot["team"] for dot in DATA["league"]] == sorted(table.index)
    by_team = {dot["team"]: dot for dot in DATA["league"]}
    assert by_team["MIN"] == {"team": "MIN", "nickname": "Vikings", "actualWins": 1.0,
                              "pythagoreanWins": round(table.loc["MIN", "pythagorean_wins"], 2)}
    assert by_team["GB"]["actualWins"] == 0.5
    assert by_team["CHI"]["actualWins"] == 1.5


def test_chart_title_matches_the_feed_chart():
    from lib.real_or_lucky_posts import chart_title
    assert DATA["chartTitle"] == chart_title(SNAPSHOT)


def test_history_is_null_unless_the_team_has_a_perfect_start_to_compare():
    assert DATA["history"] is None and DATA["lastUnbeaten"] is False
    history = report.UnbeatenHistory(first_season=2012, last_season=2025, games=2, starts=3, points_below_perfect=1,
                                     more_points=2, rest_win_rate=0.375, pythagorean_wins=[1.07, 1.56, 2.0],
                                     fewer_points=0, fewer_allowed=1)
    data = video.video_data(SNAPSHOT, GAMES, turnover_carryover=0.31, history=history, last_unbeaten=True)
    assert data["lastUnbeaten"] is True
    assert data["history"] == {"firstSeason": 2012, "lastSeason": 2025, "games": 2, "starts": 3,
                               "pointsBelowPerfect": 1, "morePoints": 2, "restWinPct": 38,
                               "pythagoreanWins": [1.07, 1.56, 2.0], "fewerPoints": 0, "fewerAllowed": 1}
    empty = replace(history, starts=0, pythagorean_wins=[])
    assert video.video_data(SNAPSHOT, GAMES, turnover_carryover=0.31, history=empty)["history"] is None


def test_kicker_is_carried_only_when_he_scored_at_least_half():
    assert DATA["kicker"] is None
    run = report.ScoringRun(games=2, first_week=1, last_week=2, touchdowns=1, kick_points=20, points=41)
    data = lambda r: video.video_data(SNAPSHOT, GAMES, turnover_carryover=0.31, scoring=r)["kicker"]
    assert data(run) is None                                           # 20 of 41 is under half
    assert data(replace(run, kick_points=21, points=42)) == {"kickPoints": 21, "points": 42, "games": 2,
                                                             "allGames": True}
    assert data(replace(run, games=1, kick_points=9, points=12))["allGames"] is False


def test_opponent_adjustment_is_carried_with_the_opponent_nickname():
    assert DATA["opponentAdjustment"] is None
    adjustment = report.OpponentAdjustment(allowed_below=11.1, scored_vs_usual=-3.4, best_opponent="CHI",
                                           best_allowed=3, best_usual=29.5)
    data = video.video_data(SNAPSHOT, GAMES, turnover_carryover=0.31, adjustment=adjustment)
    assert data["opponentAdjustment"] == {"allowedBelow": 11.1, "bestOpponent": "Bears", "bestAllowed": 3,
                                          "bestUsual": 29.5}
