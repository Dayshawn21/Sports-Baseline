"""Total games is a mixture over set count, not a Poisson draw.

Measured over 27,439 completed best-of-3 matches, the pooled variance/mean ratio is 1.59,
but within a fixed set count it is 0.48. The spread is not overdispersion in a single
count process; it is two modes about 10.4 games apart. Treating it as Poisson badly
misprices the tails, which is exactly where the attractive lines sit.
"""

import pytest

from app.core.poisson import over_under_push_probs
from app.core.prop_probs import prop_probabilities, total_games_probs


class TestShape:
    def test_over_and_under_partition_the_probability(self):
        p = total_games_probs(22.5, 23.0, 0.5)
        assert p.p_over + p.p_under + p.p_push == pytest.approx(1.0)

    def test_a_line_below_the_projection_favours_the_over(self):
        p = total_games_probs(18.5, 23.0, 0.5)
        assert p.p_over > p.p_under

    def test_a_line_above_the_projection_favours_the_under(self):
        p = total_games_probs(28.5, 23.0, 0.5)
        assert p.p_under > p.p_over

    def test_a_half_point_line_cannot_push(self):
        assert total_games_probs(22.5, 23.0, 0.5).p_push == 0.0

    def test_a_whole_number_line_carries_push_mass(self):
        assert total_games_probs(22.0, 23.0, 0.5).p_push > 0.0


class TestBeatsPoissonInTheTails:
    # Measured over 27,439 completed best-of-3 matches: pooled mean 22.29 games, and
    # 9,508 of them went to a deciding set, so the mixture weight for this population is
    # 0.347. Comparing at any other weight compares against a different population.
    POOLED_MEAN = 22.29
    POOLED_P3 = 0.347
    EMPIRICAL_OVER = {18: 0.689, 20: 0.549, 22: 0.441, 24: 0.376, 26: 0.296, 28: 0.224}

    @pytest.mark.parametrize("line", list(EMPIRICAL_OVER))
    def test_it_is_closer_to_reality_than_poisson_at_every_line(self, line):
        empirical = self.EMPIRICAL_OVER[line]
        mix = total_games_probs(line + 0.5, self.POOLED_MEAN, self.POOLED_P3).p_over
        poisson = over_under_push_probs(line + 0.5, self.POOLED_MEAN)[0]
        assert abs(mix - empirical) < abs(poisson - empirical)

    def test_mean_absolute_error_is_several_times_smaller(self):
        def mae(fn):
            return sum(abs(fn(k) - e) for k, e in self.EMPIRICAL_OVER.items()) / len(self.EMPIRICAL_OVER)

        mix = mae(lambda k: total_games_probs(k + 0.5, self.POOLED_MEAN, self.POOLED_P3).p_over)
        poisson = mae(lambda k: over_under_push_probs(k + 0.5, self.POOLED_MEAN)[0])
        assert mix < poisson / 3

    def test_poisson_badly_understates_the_far_tail(self):
        # The defect that motivated this: Poisson says ~0.10, reality says 0.224.
        assert over_under_push_probs(28.5, self.POOLED_MEAN)[0] < 0.15
        assert total_games_probs(28.5, self.POOLED_MEAN, self.POOLED_P3).p_over > 0.18


class TestDecidingSetWeight:
    def test_a_likely_deciding_set_widens_the_upper_tail(self):
        close = total_games_probs(28.5, 23.0, 0.5).p_over
        lopsided = total_games_probs(28.5, 23.0, 0.1).p_over
        assert close > lopsided

    def test_the_weighted_mean_stays_at_the_projection(self):
        # A line at the projection should sit near even money regardless of the weight.
        for p3 in (0.1, 0.3, 0.5):
            assert total_games_probs(23.0, 23.0, p3).p_over == pytest.approx(0.5, abs=0.12)

    def test_an_unknown_deciding_probability_falls_back_without_error(self):
        p = total_games_probs(22.5, 23.0, None)
        assert p.p_over + p.p_under == pytest.approx(1.0)

    def test_best_of_five_uses_the_set_count_mixture(self):
        assert total_games_probs(22.5, 23.0, 0.5, best_of=5).p_over > 0.0


class TestRouting:
    def test_prop_probabilities_routes_total_games_away_from_poisson(self):
        via_router = prop_probabilities("total_games", 28.5, 23.0).p_over
        assert via_router == pytest.approx(total_games_probs(28.5, 23.0).p_over)
        assert via_router != pytest.approx(over_under_push_probs(28.5, 23.0)[0])

    def test_prop_probabilities_forwards_deciding_set_weight(self):
        close = prop_probabilities(
            "total_games",
            28.5,
            23.0,
            p_deciding_set=0.5,
        ).p_over
        lopsided = prop_probabilities(
            "total_games",
            28.5,
            23.0,
            p_deciding_set=0.1,
        ).p_over

        assert close > lopsided

    def test_prop_probabilities_forwards_closeness_for_best_of_five(self):
        close = prop_probabilities(
            "total_games",
            32.5,
            30.0,
            best_of=5,
            p_deciding_set=0.5,
        ).p_over
        lopsided = prop_probabilities(
            "total_games",
            32.5,
            30.0,
            best_of=5,
            p_deciding_set=0.1,
        ).p_over

        assert close > lopsided
