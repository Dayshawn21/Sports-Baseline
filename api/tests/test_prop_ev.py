"""The EV model exists to stop the tier from measuring 'how little does this pay'."""

import pytest

from app.core.prop_ev import (
    DEMON_LEG_DECIMAL,
    GOBLIN_LEG_DECIMAL,
    STANDARD_LEG_DECIMAL,
    american_to_decimal,
    assess_prop,
    break_even_probability,
    ev_confidence_tier,
    leg_decimal_odds,
)


class TestPayoutModel:
    def test_two_standard_legs_compound_to_a_3x_power_play(self):
        assert STANDARD_LEG_DECIMAL**2 == pytest.approx(3.0, abs=0.01)

    def test_goblins_pay_less_and_demons_pay_more_than_standard(self):
        assert GOBLIN_LEG_DECIMAL < STANDARD_LEG_DECIMAL < DEMON_LEG_DECIMAL

    def test_break_even_is_the_inverse_of_decimal_odds(self):
        assert break_even_probability(2.0) == pytest.approx(0.5)
        assert break_even_probability(STANDARD_LEG_DECIMAL) == pytest.approx(0.577, abs=0.001)
        assert break_even_probability(GOBLIN_LEG_DECIMAL) == pytest.approx(0.758, abs=0.001)
        assert break_even_probability(DEMON_LEG_DECIMAL) == pytest.approx(0.413, abs=0.001)

    def test_american_odds_convert(self):
        assert american_to_decimal(100) == pytest.approx(2.0)
        assert american_to_decimal(-150) == pytest.approx(1.667, abs=0.001)
        assert american_to_decimal(250) == pytest.approx(3.5)

    def test_real_american_odds_beat_the_tier_table(self):
        assert leg_decimal_odds("goblin", american_odds=100) == pytest.approx(2.0)

    def test_unpriced_non_prizepicks_prop_is_not_graded(self):
        # Assuming a 1.73x leg for a sportsbook line would invent a price.
        assert leg_decimal_odds(None, source="bet") is None
        assert leg_decimal_odds("", source="draftkings") is None

    def test_unmarked_prizepicks_projection_is_standard(self):
        assert leg_decimal_odds(None, source="prizepicks") == STANDARD_LEG_DECIMAL


class TestTheBugThisFixes:
    """Raw probability graded 36.7% of goblins LOCK and 0.6% of demons LOCK."""

    def test_a_near_certain_goblin_that_pays_nothing_is_not_a_lock(self):
        # 80% hit rate sounds great, but a goblin needs 75.8% just to break even,
        # so it is a marginal pick — the old model graded this LOCK.
        result = assess_prop(0.80, odds_type="goblin", source="prizepicks")
        assert result.ev == pytest.approx(0.056, abs=0.005)
        assert result.confidence == "LEAN"

    def test_a_genuinely_mispriced_goblin_still_grades_well(self):
        result = assess_prop(0.97, odds_type="goblin", source="prizepicks")
        assert result.ev == pytest.approx(0.280, abs=0.005)
        assert result.confidence == "LOCK"

    def test_a_coin_flip_demon_is_value_but_not_a_main_board_pick(self):
        # It only needs 41.3% to break even, so a coin flip returns +21% on
        # average. The strict board still requires at least 55% hit probability.
        result = assess_prop(0.50, odds_type="demon", source="prizepicks")
        assert result.ev == pytest.approx(0.21, abs=0.005)
        assert result.confidence == "PASS"

    def test_a_demon_below_the_probability_gate_cannot_lock(self):
        # +19% EV, but it misses more often than it hits, so strict criteria hide it.
        result = assess_prop(0.49, odds_type="demon", source="prizepicks")
        assert result.ev > 0.15
        assert result.confidence == "PASS"

    def test_a_demon_below_its_break_even_is_a_pass(self):
        result = assess_prop(0.35, odds_type="demon", source="prizepicks")
        assert result.ev < 0
        assert result.confidence == "PASS"

    def test_equal_probabilities_grade_differently_by_price(self):
        p = 0.72
        goblin = assess_prop(p, odds_type="goblin", source="prizepicks")
        standard = assess_prop(p, odds_type="standard", source="prizepicks")
        demon = assess_prop(p, odds_type="demon", source="prizepicks")

        # Same likelihood, three different prices — value must order by payout.
        assert goblin.ev < standard.ev < demon.ev
        assert goblin.confidence == "PASS"
        assert demon.confidence == "LOCK"


class TestTierGates:
    def test_high_ev_but_coin_flip_odds_cannot_reach_lock(self):
        # A 25% shot at 5.0x is +25% EV, but the strict board requires 55%+.
        result = assess_prop(0.25, american_odds=400)
        assert result.ev == pytest.approx(0.25, abs=0.005)
        assert result.confidence == "PASS"

    def test_tiers_ladder_on_ev(self):
        assert ev_confidence_tier(0.20, 0.70) == "LOCK"
        assert ev_confidence_tier(0.10, 0.60) == "STRONG"
        assert ev_confidence_tier(0.05, 0.55) == "LEAN"
        assert ev_confidence_tier(0.00, 0.60) == "PASS"
        assert ev_confidence_tier(-0.10, 0.90) == "PASS"

    def test_break_even_exactly_is_a_pass(self):
        result = assess_prop(break_even_probability(STANDARD_LEG_DECIMAL),
                             odds_type="standard", source="prizepicks")
        assert result.ev == pytest.approx(0.0, abs=1e-6)
        assert result.confidence == "PASS"

    def test_probability_is_clamped(self):
        assert assess_prop(1.5, odds_type="standard", source="prizepicks").probability == 1.0
        assert assess_prop(-0.2, odds_type="standard", source="prizepicks").probability == 0.0

    def test_edge_over_break_even_is_reported_in_points(self):
        result = assess_prop(0.90, odds_type="goblin", source="prizepicks")
        assert result.edge_over_break_even == pytest.approx(14.2, abs=0.2)
