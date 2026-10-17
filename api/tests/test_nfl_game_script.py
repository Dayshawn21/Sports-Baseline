from math import exp, inf, nan

import pytest

from app.core.nfl_game_script import implied_team_points, scoring_environment_probability


def test_a_home_favorite_gets_the_larger_implied_total() -> None:
    # Real NFLverse row 2025_01_DAL_PHI: PHI at home, moneyline -425, spread_line +8.5, total 47.5.
    assert implied_team_points(47.5, 8.5, True) == 28.0
    assert implied_team_points(47.5, 8.5, False) == 19.5


def test_a_road_favorite_gets_the_larger_implied_total() -> None:
    # Real NFLverse row 2025_01_KC_LAC: KC on the road, moneyline -175, spread_line -3, total 47.5.
    assert implied_team_points(47.5, -3.0, True) == 22.25
    assert implied_team_points(47.5, -3.0, False) == 25.25


def test_a_zero_blend_weight_reproduces_the_production_rate_unrounded() -> None:
    probability = scoring_environment_probability(0.35, 55.0, -7.0, True, 23.5, 1.5, 0.0)

    assert probability == 1 - exp(-0.35)


@pytest.mark.parametrize("total, spread", [(None, -3.0), (47.0, None), (nan, -3.0), (47.0, inf)])
def test_missing_or_non_finite_lines_fall_back_to_the_baseline(total: float | None, spread: float | None) -> None:
    assert scoring_environment_probability(0.35, total, spread, True, 23.5, 1.5, 0.7) == 1 - exp(-0.35)


def test_a_higher_implied_total_raises_probability_with_a_positive_exponent() -> None:
    # Home team implied 31.0 points versus 17.0.
    high = scoring_environment_probability(0.35, 55.0, 7.0, True, 23.5, 1.0, 1.0)
    low = scoring_environment_probability(0.35, 41.0, -7.0, True, 23.5, 1.0, 1.0)

    assert high > low


def test_non_finite_inputs_are_clamped_to_safe_probabilities() -> None:
    probability = scoring_environment_probability(nan, 47.0, -3.0, True, inf, nan, nan)

    assert probability == 0.0


def test_a_non_positive_implied_total_cannot_create_an_infinite_rate() -> None:
    # A 6-point home underdog in a 2-point game is implied -2.0 points.
    probability = scoring_environment_probability(0.35, 2.0, -6.0, True, 23.5, -1.0, 1.0)

    assert probability == 0.0
