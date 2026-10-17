from dataclasses import replace

import pytest

from app.core.nfl_elo import NflEloGame
from app.core.nfl_scoring_ratings import INITIAL_LEAGUE_POINTS, NflScoringConfig, replay

CONFIG = NflScoringConfig(learning_rate=0.1)


def _game(key: str, season: int, week: int, home: str, away: str, home_score: int | None, away_score: int | None) -> NflEloGame:
    return NflEloGame(key, season, week, home, away, home_score, away_score)


def test_the_first_game_expects_the_initial_league_average_for_both_sides() -> None:
    [row] = replay([_game("g1", 2012, 1, "NYG", "DAL", 17, 24)], CONFIG)

    assert (row.expected_home_points, row.expected_away_points) == (INITIAL_LEAGUE_POINTS, INITIAL_LEAGUE_POINTS)
    assert row.expected_total == 2 * INITIAL_LEAGUE_POINTS


def test_a_team_that_outscores_expectation_raises_its_offense_and_the_opponents_defense_allowance() -> None:
    rows = replay([
        _game("g1", 2012, 1, "KC", "DEN", 42, 22),
        _game("g2", 2012, 1, "SEA", "LAR", 22, 22),
        # Week 2 league average is (42 + 22 + 22 + 22) / 4 = 27.
        _game("g3", 2012, 2, "KC", "SEA", None, None),
        _game("g4", 2012, 2, "DEN", "LAR", None, None),
    ], CONFIG)

    kc_home, denver_home = rows[2], rows[3]
    # KC scored 20 over expectation: offense +2.0. Denver allowed it: defense +2.0.
    assert kc_home.expected_home_points == pytest.approx(27 + 2.0 + 0.0)
    assert denver_home.expected_away_points == pytest.approx(27 + 0.0 + 2.0)
    # Denver scored exactly as expected: nothing moves on that side.
    assert denver_home.expected_home_points == pytest.approx(27 + 0.0 + 0.0)


def test_the_league_average_only_uses_earlier_weeks() -> None:
    rows = replay([
        _game("g1", 2012, 1, "KC", "DEN", 50, 50),
        _game("g2", 2012, 1, "SEA", "LAR", None, None),
    ], CONFIG)

    # Same week as a 100-point game, still on the initial average.
    assert rows[1].expected_total == 2 * INITIAL_LEAGUE_POINTS


def test_a_new_season_keeps_two_thirds_of_each_rating() -> None:
    rows = replay([
        _game("g1", 2012, 17, "KC", "DEN", 52, 22),
        _game("g2", 2013, 1, "KC", "DEN", None, None),
    ], CONFIG)

    # KC offense and Denver's defense allowance each rose 0.1 * (52 - 22) = 3.0 in
    # 2012; 2/3 of each carries into 2013 on top of the 37-point league average.
    assert rows[1].expected_home_points == pytest.approx((52 + 22) / 2 + 2 * 3.0 * 2 / 3)


def test_a_scheduled_game_gets_expectations_and_changes_nothing() -> None:
    rows = replay([
        _game("g1", 2026, 1, "KC", "DEN", None, None),
        _game("g2", 2026, 2, "KC", "DEN", None, None),
    ], CONFIG)

    assert rows[0].expected_total == rows[1].expected_total == 2 * INITIAL_LEAGUE_POINTS


def test_a_games_own_result_and_later_results_never_change_its_expectation() -> None:
    games = [
        _game("g1", 2012, 1, "KC", "DEN", 30, 20),
        _game("g2", 2012, 2, "DEN", "SEA", 17, 24),
        _game("g3", 2012, 3, "SEA", "KC", 10, 13),
    ]
    changed = [games[0], replace(games[1], home_score=56, away_score=3), replace(games[2], home_score=0, away_score=45)]

    original = [(row.expected_home_points, row.expected_away_points) for row in replay(games, CONFIG)[:2]]
    after = [(row.expected_home_points, row.expected_away_points) for row in replay(changed, CONFIG)[:2]]

    assert original == after
