"""Best-of-3 set outcomes fitted to real results must stay a coherent distribution."""
import numpy as np
import pytest

from app.core.tennis_sets import set_outcomes, three_set_probability

GRID = np.linspace(0.5, 0.99, 50)


class TestCoherence:
    @pytest.mark.parametrize("p", GRID)
    def test_outcomes_sum_to_one_and_are_never_negative(self, p):
        o = set_outcomes(p)
        assert o.favorite_straight + o.underdog_straight + o.three_sets == pytest.approx(1.0)
        assert min(o.favorite_straight, o.underdog_straight, o.three_sets) >= 0.0

    @pytest.mark.parametrize("p", GRID)
    def test_straight_sets_never_exceed_each_sides_win_probability(self, p):
        o = set_outcomes(p)
        assert o.favorite_straight <= p + 1e-9
        assert o.underdog_straight <= (1 - p) + 1e-9

    def test_it_does_not_matter_which_side_is_p1(self):
        assert set_outcomes(0.3) == set_outcomes(0.7)
        assert three_set_probability(0.3) == pytest.approx(three_set_probability(0.7))


class TestFittedValues:
    # Measured rates on 4,680 settled matches, by favorite's de-vigged probability.
    @pytest.mark.parametrize(("p", "measured"), [(0.55, 0.400), (0.75, 0.323), (0.95, 0.189)])
    def test_three_sets_tracks_the_measured_rate(self, p, measured):
        assert three_set_probability(p) == pytest.approx(measured, abs=0.04)

    def test_a_coin_flip_goes_three_sets_about_two_fifths_of_the_time(self):
        assert three_set_probability(0.5) == pytest.approx(0.1168 + 0.5813 * 0.5)

    def test_a_close_favorite_sweeps_less_often_than_p_squared_suggests_for_heavy_ones(self):
        # The old p**2 overstated heavy favourites' sweeps (0.857 vs 0.789 measured).
        assert set_outcomes(0.95).favorite_straight < 0.95 ** 2
        assert set_outcomes(0.95).favorite_straight == pytest.approx(0.789, abs=0.04)
