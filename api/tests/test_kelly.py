"""Stake sizing decides how much a wrong probability costs, so it gets pinned down."""

import pytest

from app.core.kelly import DEFAULT_KELLY_MULTIPLIER, expected_value, kelly_fraction


class TestExpectedValue:
    def test_a_fairly_priced_bet_has_no_edge(self):
        assert expected_value(0.5, 100) == pytest.approx(0.0)

    def test_edge_is_positive_when_our_probability_beats_the_price(self):
        assert expected_value(0.6, 100) == pytest.approx(0.2)

    def test_edge_is_negative_when_the_price_is_short(self):
        assert expected_value(0.6, -200) == pytest.approx(-0.1)

    def test_negative_odds_use_the_reciprocal_payout(self):
        assert expected_value(0.75, -200) == pytest.approx(0.75 * 0.5 - 0.25)


class TestKellyFraction:
    def test_no_edge_means_no_bet(self):
        assert kelly_fraction(0.5, 100) == 0.0

    def test_negative_edge_never_returns_a_stake(self):
        assert kelly_fraction(0.4, 100) == 0.0

    def test_stake_is_a_quarter_of_full_kelly_by_default(self):
        # Full Kelly on a 60% shot at +100 is 0.20 of bankroll; quarter Kelly is 0.05.
        assert kelly_fraction(0.6, 100) == pytest.approx(0.05)

    def test_multiplier_scales_the_stake_linearly(self):
        full = kelly_fraction(0.6, 100, multiplier=1.0)
        assert full == pytest.approx(0.20)
        assert kelly_fraction(0.6, 100, multiplier=0.5) == pytest.approx(full * 0.5)

    def test_default_multiplier_is_quarter_kelly(self):
        assert DEFAULT_KELLY_MULTIPLIER == 0.25

    def test_cap_still_binds_on_an_extreme_edge(self):
        # Full Kelly here is ~0.94, well past the cap even after scaling.
        assert kelly_fraction(0.95, 100, multiplier=1.0) == 0.25

    def test_scaled_stake_stays_below_the_cap_where_full_kelly_would_not(self):
        assert kelly_fraction(0.95, 100) == pytest.approx(0.9 / 4)

    def test_stake_never_exceeds_the_cap(self):
        for prob in (0.55, 0.7, 0.85, 0.99):
            assert 0.0 <= kelly_fraction(prob, 150) <= 0.25
