"""Odds conversions are the base every EV and stake number is built on top of."""

import pytest

from app.core.odds import (
    american_to_decimal,
    american_to_prob,
    decimal_to_american,
    devig_two_way,
    implied_prob_from_american,
    near_even_rungs,
    overround,
    prob_to_american,
)


class TestAmericanToProb:
    def test_even_money_both_ways_is_half(self):
        assert american_to_prob(100) == pytest.approx(0.5)
        assert american_to_prob(-100) == pytest.approx(0.5)

    def test_favourite_prices_above_half(self):
        assert american_to_prob(-200) == pytest.approx(2 / 3)

    def test_underdog_prices_below_half(self):
        assert american_to_prob(200) == pytest.approx(1 / 3)


class TestDecimalConversion:
    def test_positive_and_negative_odds_convert_to_decimal(self):
        assert american_to_decimal(150) == pytest.approx(2.5)
        assert american_to_decimal(-150) == pytest.approx(1 + 100 / 150)

    @pytest.mark.parametrize("odds", [-500, -200, -110, 100, 150, 400])
    def test_decimal_conversion_round_trips(self, odds):
        assert decimal_to_american(american_to_decimal(odds)) == odds

    def test_decimal_at_or_below_evens_is_clamped_rather_than_dividing_by_zero(self):
        assert decimal_to_american(1.0) == -10000


class TestProbToAmerican:
    @pytest.mark.parametrize("odds", [-300, -150, 120, 250])
    def test_probability_conversion_round_trips(self, odds):
        assert prob_to_american(american_to_prob(odds)) == odds

    def test_degenerate_probabilities_do_not_blow_up(self):
        assert prob_to_american(0.0) > 0
        assert prob_to_american(1.0) < 0


class TestDevig:
    def test_a_vigged_pair_normalises_to_one(self):
        p1, p2 = implied_prob_from_american(-110, -110)
        assert p1 + p2 == pytest.approx(1.0)
        assert p1 == pytest.approx(0.5)

    def test_devig_preserves_which_side_is_favoured(self):
        p1, p2 = implied_prob_from_american(-200, 170)
        assert p1 > p2
        assert p1 + p2 == pytest.approx(1.0)

    def test_empty_market_falls_back_to_a_coin_flip(self):
        assert devig_two_way(0.0, 0.0) == (0.5, 0.5)

    def test_overround_is_the_excess_over_one(self):
        raw_p1 = american_to_prob(-110)
        raw_p2 = american_to_prob(-110)
        assert overround(raw_p1, raw_p2) == pytest.approx(0.0476, abs=1e-4)

    def test_a_fair_market_has_no_overround(self):
        assert overround(0.5, 0.5) == pytest.approx(0.0)


def test_near_even_rungs_drop_any_side_priced_past_three_quarters():
    ladder = [(1.002, 36.0), (1.25, 4.0), (1.85, 1.96), (4.0 / 3, 3.9)]
    assert near_even_rungs(ladder, lambda rung: rung) == [(1.85, 1.96), (4.0 / 3, 3.9)]


def test_near_even_rungs_keep_everything_when_no_rung_qualifies():
    lopsided = [(1.10, 7.0), (1.20, 4.5)]
    assert near_even_rungs(lopsided, lambda rung: rung) == lopsided
