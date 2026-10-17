from dataclasses import replace

import pytest

from app.core.nfl_elo import (
    INITIAL_ELO,
    NFL_ELO_V1,
    NflEloConfig,
    NflEloGame,
    current_ratings,
    expected_home_win_probability,
    margin_multiplier,
    point_differentials,
    regress_to_mean,
    replay,
    season_end_ratings,
    update,
)


def _game(key: str, season: int, week: int, home: str, away: str, home_score: int | None, away_score: int | None) -> NflEloGame:
    return NflEloGame(key, season, week, home, away, home_score, away_score)


def test_equal_teams_on_a_neutral_field_are_a_coin_flip() -> None:
    assert expected_home_win_probability(1500, 1500, home_field=0) == pytest.approx(0.5)


def test_home_field_makes_equal_teams_favor_the_home_side() -> None:
    assert expected_home_win_probability(1500, 1500) == pytest.approx(0.5686, abs=1e-4)


def test_expected_probabilities_for_the_two_sides_sum_to_one() -> None:
    assert expected_home_win_probability(1600, 1450, 0) + expected_home_win_probability(1450, 1600, 0) == pytest.approx(1.0)


def test_an_update_is_zero_sum() -> None:
    home, away = update(1580, 1490, 17, 31)

    assert home + away == pytest.approx(1580 + 1490)


def test_the_winner_gains_and_the_loser_drops() -> None:
    home, away = update(1500, 1500, 10, 24)

    assert away > 1500 > home


def test_a_bigger_margin_moves_ratings_more() -> None:
    close_home, _ = update(1500, 1500, 24, 21)
    blowout_home, _ = update(1500, 1500, 45, 10)

    assert blowout_home - 1500 > close_home - 1500 > 0


def test_a_favored_winner_gets_a_smaller_margin_multiplier_than_an_underdog_winner() -> None:
    # This damping stops favorites' larger average margins from inflating their ratings.
    assert margin_multiplier(14, 200) < margin_multiplier(14, -200)


def test_a_tie_moves_the_home_favorite_down_and_the_visitor_up() -> None:
    # Equal ratings plus home field make the home side the favorite, so a tie underperforms.
    home, away = update(1500, 1500, 20, 20)

    assert home < 1500 < away
    assert home + away == pytest.approx(3000)


@pytest.mark.parametrize("elo, regressed", [(1650.0, 1600.0), (1350.0, 1400.0), (INITIAL_ELO, INITIAL_ELO)])
def test_between_seasons_a_rating_moves_one_third_toward_the_mean(elo: float, regressed: float) -> None:
    assert regress_to_mean(elo) == pytest.approx(regressed)


def test_replay_starts_every_team_at_the_initial_rating_and_writes_two_rows_per_game() -> None:
    rows = replay([_game("g1", 2012, 1, "NYG", "DAL", 17, 24)])

    assert [(row.team_code, row.is_home, row.elo_pre) for row in rows] == [
        ("NYG", True, INITIAL_ELO), ("DAL", False, INITIAL_ELO),
    ]
    assert rows[1].elo_post is not None and rows[1].elo_post > INITIAL_ELO


def test_a_teams_next_pre_rating_is_its_previous_post_rating() -> None:
    rows = replay([
        _game("g1", 2012, 1, "NYG", "DAL", 17, 24),
        _game("g2", 2012, 2, "DAL", "SEA", 20, 27),
    ])

    dallas = [row for row in rows if row.team_code == "DAL"]
    assert dallas[1].elo_pre == dallas[0].elo_post


def test_a_new_season_regresses_ratings_before_the_first_game() -> None:
    rows = replay([
        _game("g1", 2012, 17, "NYG", "DAL", 3, 42),
        _game("g2", 2013, 1, "DAL", "NYG", 20, 20),
    ])

    dallas_2012_post = rows[1].elo_post
    assert dallas_2012_post is not None
    assert rows[2].elo_pre == pytest.approx(regress_to_mean(dallas_2012_post))


def test_a_scheduled_game_gets_a_pre_rating_and_no_post_rating_and_changes_nothing() -> None:
    rows = replay([
        _game("g1", 2026, 1, "NYG", "DAL", 17, 24),
        _game("g2", 2026, 2, "DAL", "SEA", None, None),
        _game("g3", 2026, 3, "PHI", "DAL", None, None),
    ])

    scheduled = [row for row in rows if row.game_key == "g2"]
    assert all(row.elo_post is None for row in scheduled)
    dallas = [row for row in rows if row.team_code == "DAL"]
    assert dallas[1].elo_pre == dallas[2].elo_pre == dallas[0].elo_post


_SEASONS = [
    _game("g1", 2025, 17, "NYG", "DAL", 3, 42),
    _game("g2", 2025, 18, "DAL", "PHI", 10, 13),
    _game("g3", 2026, 1, "PHI", "NYG", 30, 20),
    _game("g4", 2026, 2, "DAL", "NYG", None, None),
]


def test_current_ratings_use_the_last_post_or_the_pre_rating_of_an_unplayed_game() -> None:
    rows = replay(_SEASONS)
    ratings = current_ratings(rows)

    philly_week_1 = next(row for row in rows if row.team_code == "PHI" and row.game_key == "g3")
    dallas_week_2 = next(row for row in rows if row.team_code == "DAL" and row.game_key == "g4")
    assert ratings["PHI"] == philly_week_1.elo_post
    # Dallas has not played in 2026, so its current rating is the regressed pre rating.
    assert ratings["DAL"] == dallas_week_2.elo_pre


def test_season_end_ratings_are_the_last_post_before_regression() -> None:
    rows = replay(_SEASONS)

    dallas_2025 = [row for row in rows if row.team_code == "DAL" and row.season == 2025]
    assert season_end_ratings(rows, 2025)["DAL"] == dallas_2025[-1].elo_post
    assert set(season_end_ratings(rows, 2026)) == {"PHI", "NYG"}


def test_point_differentials_net_every_final_game_in_the_season_and_skip_unplayed() -> None:
    assert point_differentials(_SEASONS, 2025) == {"NYG": -39, "DAL": 36, "PHI": 3}
    assert point_differentials(_SEASONS, 2026) == {"PHI": 10, "NYG": -10}


def test_a_different_config_changes_ratings_and_v1_is_the_default() -> None:
    faster = NflEloConfig(k=30.0, home_field=24.0, season_regression=0.5)

    default_rows = replay(_SEASONS)
    v1_rows = replay(_SEASONS, NFL_ELO_V1)
    faster_rows = replay(_SEASONS, faster)

    assert default_rows == v1_rows
    assert [row.elo_post for row in faster_rows] != [row.elo_post for row in v1_rows]
    # Season regression reads the config too: 2026 pre ratings move half the way back.
    dallas = [row for row in faster_rows if row.team_code == "DAL"]
    dallas_2025_post = [row for row in dallas if row.season == 2025][-1].elo_post
    assert dallas_2025_post is not None
    dallas_2026 = next(row for row in dallas if row.season == 2026)
    assert dallas_2026.elo_pre == pytest.approx(regress_to_mean(dallas_2025_post, faster))


def test_a_games_own_result_and_later_results_never_change_its_pre_rating() -> None:
    games = [
        _game("g1", 2012, 1, "NYG", "DAL", 17, 24),
        _game("g2", 2012, 2, "DAL", "SEA", 20, 27),
        _game("g3", 2012, 3, "SEA", "NYG", 14, 10),
    ]
    changed = [games[0], replace(games[1], home_score=56, away_score=0), replace(games[2], home_score=0, away_score=35)]

    original_pre = {(row.team_code, row.game_key): row.elo_pre for row in replay(games) if row.game_key != "g3"}
    changed_pre = {(row.team_code, row.game_key): row.elo_pre for row in replay(changed) if row.game_key != "g3"}

    assert original_pre == changed_pre
