from datetime import date

import pytest

from app.core.nfl_team_stats import EMPTY_TEAM_STATS, STAT_KEYS, StatLine, TeamGame, team_stats


def _game(team_id: int, points_for: int, points_against: int, **fields: float | int | None) -> TeamGame:
    return TeamGame(team_id=team_id, points_for=points_for, points_against=points_against, **fields)


def test_per_game_values_average_the_games_played() -> None:
    stats = team_stats([
        _game(1, 24, 10, pass_yards_for=250, rush_yards_for=100, pass_yards_against=180),
        _game(1, 17, 20, pass_yards_for=200, rush_yards_for=141, pass_yards_against=220),
    ])[1]
    assert stats.games == 2
    assert stats.stats["points"].value == 20.5
    assert stats.stats["points_allowed"].value == 15.0
    assert stats.stats["pass_yards"].value == 225.0
    assert stats.stats["rush_yards"].value == 120.5
    assert stats.stats["pass_yards_allowed"].value == 200.0


def test_per_play_rates_weigh_games_by_their_plays() -> None:
    stats = team_stats([
        _game(1, 0, 0, plays_for=80, epa_for=8.0, successes_for=40, plays_against=50, epa_against=-5.0, successes_against=20),
        _game(1, 0, 0, plays_for=20, epa_for=-6.0, successes_for=5, plays_against=50, epa_against=5.0, successes_against=30),
    ])[1]
    assert stats.efficiency_games == 2
    assert stats.stats["plays"].value == 50.0
    assert stats.stats["epa_per_play"].value == 0.02
    assert stats.stats["success_rate"].value == 0.45
    assert stats.stats["epa_per_play_allowed"].value == 0.0
    assert stats.stats["success_rate_allowed"].value == 0.5


def test_offense_ranks_high_first_and_defense_ranks_low_allowed_first() -> None:
    stats = team_stats([_game(1, 30, 30), _game(2, 20, 10), _game(3, 10, 20)])
    assert [stats[team].stats["points"].rank for team in (1, 2, 3)] == [1, 2, 3]
    assert [stats[team].stats["points_allowed"].rank for team in (1, 2, 3)] == [3, 1, 2]


def test_tied_values_share_the_lower_rank() -> None:
    stats = team_stats([_game(1, 24, 0), _game(2, 24, 0), _game(3, 21, 0), _game(4, 30, 0)])
    assert [stats[team].stats["points"].rank for team in (4, 1, 2, 3)] == [1, 2, 2, 4]


def test_ties_are_judged_on_the_shown_precision() -> None:
    stats = team_stats([_game(1, 0, 0, pass_yards_for=200.04), _game(2, 0, 0, pass_yards_for=200.01)])
    assert stats[1].stats["pass_yards"].rank == stats[2].stats["pass_yards"].rank == 1


def test_missing_efficiency_rows_leave_play_stats_null_and_unranked() -> None:
    stats = team_stats([_game(1, 24, 10), _game(2, 20, 17, plays_for=60, epa_for=3.0, successes_for=30)])
    assert stats[1].efficiency_games == 0
    assert stats[1].stats["plays"] == StatLine(None, None)
    assert stats[1].stats["epa_per_play"] == StatLine(None, None)
    assert stats[1].stats["success_rate"] == StatLine(None, None)
    assert stats[1].stats["points"] == StatLine(24.0, 1, 1)
    assert stats[2].stats["plays"] == StatLine(60.0, 1, 1)


def test_a_partly_loaded_season_averages_only_the_loaded_games() -> None:
    stats = team_stats([_game(1, 24, 10, rush_yards_for=120), _game(1, 17, 20)])[1]
    assert stats.stats["rush_yards"].value == 120.0
    assert stats.stats["points"].value == 20.5


def test_a_team_without_games_is_absent_and_the_empty_value_is_all_null() -> None:
    assert team_stats([]) == {}
    assert EMPTY_TEAM_STATS.games == 0
    assert set(EMPTY_TEAM_STATS.stats) == set(STAT_KEYS)
    assert all(line == StatLine(None, None) for line in EMPTY_TEAM_STATS.stats.values())


def test_attempts_preserve_zero_and_report_partial_coverage() -> None:
    stats = team_stats([
        _game(1, 10, 20, pass_attempts_for=0, rush_attempts_for=20, pass_attempts_against=35),
        _game(1, 20, 10, pass_attempts_for=30, rush_attempts_against=25),
        _game(1, 20, 17),
    ])[1]
    assert stats.games == 3
    assert stats.stats["pass_attempts"] == StatLine(15.0, 1, 2)
    assert stats.stats["rush_attempts"] == StatLine(20.0, 1, 1)
    assert stats.stats["pass_attempts_allowed"] == StatLine(35.0, 1, 1)
    assert stats.stats["rush_attempts_allowed"] == StatLine(25.0, 1, 1)


def test_recent_window_uses_each_teams_last_three_played_dates_and_ranks_that_window() -> None:
    from dataclasses import replace

    games = [replace(_game(team, points, 10), played_on=date(2026, 9, day), game_id=day)
             for team, points, day in [(1, 100, 1), (2, 15, 2), (1, 10, 22), (1, 20, 8), (1, 30, 15)]]
    season = team_stats(games)
    recent = team_stats(reversed(games), last_n=3)
    assert season[1].stats["points"].value == 40.0
    assert recent[1].games == 3
    assert recent[1].stats["points"] == StatLine(20.0, 1, 3)
    assert recent[2].games == 1
    assert recent[2].stats["points"] == StatLine(15.0, 2, 1)


def test_recent_missing_stats_do_not_reach_back_to_older_loaded_games() -> None:
    from dataclasses import replace

    games = [replace(_game(1, 10, 10, pass_attempts_for=40 if day == 1 else None),
                     played_on=date(2026, 9, day)) for day in (1, 8, 15, 22)]
    assert team_stats(games, last_n=3)[1].stats["pass_attempts"] == StatLine(None, None, 0)


def test_rate_coverage_requires_both_a_numerator_and_positive_plays() -> None:
    stats = team_stats([_game(1, 0, 0, plays_for=60), _game(1, 0, 0, plays_for=0, epa_for=0),
                        _game(1, 0, 0, plays_for=40, epa_for=4, successes_for=20)])[1]
    assert stats.stats["epa_per_play"] == StatLine(0.1, 1, 1)
    assert stats.stats["success_rate"] == StatLine(0.5, 1, 1)
    assert stats.stats["plays"].observed_games == 3


def test_recent_window_rejects_nonpositive_sizes() -> None:
    with pytest.raises(ValueError):
        team_stats([], last_n=0)
