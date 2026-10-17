"""Prop confidence comes straight out of these, including whether pushes are counted."""

import math

import pytest

from app.core.poisson import (
    confidence_tier,
    over_under_probs,
    over_under_push_probs,
    poisson_cdf,
)


class TestPoissonCdf:
    def test_cdf_matches_the_closed_form_for_a_small_lambda(self):
        expected = math.exp(-2.0) * (1 + 2.0 + 2.0**2 / 2)
        assert poisson_cdf(2, 2.0) == pytest.approx(expected)

    def test_cdf_is_monotonic_in_k(self):
        values = [poisson_cdf(k, 5.0) for k in range(12)]
        assert values == sorted(values)

    def test_cdf_approaches_one_far_out_in_the_tail(self):
        assert poisson_cdf(60, 5.0) == pytest.approx(1.0, abs=1e-9)

    def test_zero_lambda_puts_all_mass_at_zero(self):
        assert poisson_cdf(0, 0.0) == 1.0


class TestOverUnderProbs:
    def test_over_and_under_partition_the_probability(self):
        p_over, p_under = over_under_probs(5.5, 6.0)
        assert p_over + p_under == pytest.approx(1.0)

    def test_a_line_below_the_projection_favours_the_over(self):
        p_over, p_under = over_under_probs(3.5, 8.0)
        assert p_over > p_under

    def test_a_line_above_the_projection_favours_the_under(self):
        p_over, p_under = over_under_probs(12.5, 4.0)
        assert p_under > p_over


class TestPushProbs:
    def test_a_half_point_line_cannot_push(self):
        p_over, p_under, p_push = over_under_push_probs(5.5, 6.0)
        assert p_push == 0.0
        assert p_over + p_under == pytest.approx(1.0)

    def test_a_whole_number_line_carries_real_push_mass(self):
        _, _, p_push = over_under_push_probs(6.0, 6.0)
        assert p_push > 0.0

    def test_push_mass_is_not_folded_into_the_under(self):
        _, push_aware_under, p_push = over_under_push_probs(6.0, 6.0)
        _, naive_under = over_under_probs(6.0, 6.0)
        assert naive_under == pytest.approx(push_aware_under + p_push)
        assert push_aware_under < naive_under

    def test_all_three_outcomes_sum_to_one(self):
        p_over, p_under, p_push = over_under_push_probs(6.0, 6.0)
        assert p_over + p_under + p_push == pytest.approx(1.0)


class TestConfidenceTier:
    @pytest.mark.parametrize(
        "prob,tier",
        [(0.75, "LOCK"), (0.70, "LOCK"), (0.65, "STRONG"), (0.62, "STRONG"),
         (0.58, "LEAN"), (0.55, "LEAN"), (0.54, "PASS"), (0.2, "PASS")],
    )
    def test_tiers_are_assigned_at_their_boundaries(self, prob, tier):
        assert confidence_tier(prob) == tier
