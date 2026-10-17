"""The blend is the number every pick is derived from, and it is pure math.

hand_set_blend is ensemble-v2, still served without a market price and still the
26c/26d baseline; blend serves the 26d fitted blend whenever a market price exists.
"""

import pytest

from app.core.tennis_market_blend import market_anchored_prob
from app.core.tennis_market_blend_fit import FIT_COEFFICIENTS
from app.services.tennis.ensemble import (
    ELO_MAX_MARKET_GAP,
    ELO_MIN_PRIOR_MATCHES,
    ENSEMBLE_VERSION,
    EnsembleInput,
    blend,
    elo_is_unreliable,
    fitted_group,
    hand_set_blend,
)


def _blend(**kwargs):
    kwargs.setdefault("tour", "ATP")
    return hand_set_blend(EnsembleInput(**kwargs))


class TestSources:
    def test_no_sources_produces_no_prediction(self):
        assert _blend() is None

    def test_a_single_source_passes_through_unchanged(self):
        result = _blend(elo_prob=0.62)
        assert result.p1_win_prob == pytest.approx(0.62)
        assert result.weights == {"elo": 1.0}

    def test_missing_sources_are_flagged(self):
        result = _blend(elo_prob=0.6)
        assert "ml_missing" in result.quality_flags
        assert "market_missing" in result.quality_flags
        assert "elo_missing" not in result.quality_flags

    def test_weights_always_normalise_to_one(self):
        result = _blend(elo_prob=0.6, ml_prob=0.7, market_prob=0.5)
        assert sum(result.weights.values()) == pytest.approx(1.0)

    def test_sides_are_complementary(self):
        result = _blend(elo_prob=0.6, ml_prob=0.7, market_prob=0.55)
        assert result.p1_win_prob + result.p2_win_prob == pytest.approx(1.0, abs=1e-4)

    def test_agreeing_sources_blend_to_that_agreement(self):
        result = _blend(elo_prob=0.65, ml_prob=0.65, market_prob=0.65)
        assert result.p1_win_prob == pytest.approx(0.65)

    def test_components_are_echoed_back_for_display(self):
        result = _blend(elo_prob=0.6, ml_prob=0.7, market_prob=0.55)
        assert (result.elo_prob, result.ml_prob, result.market_prob) == (0.6, 0.7, 0.55)


class TestTourWeights:
    def test_atp_leans_on_the_market_more_than_wta_does(self):
        atp = hand_set_blend(EnsembleInput(tour="ATP", elo_prob=0.5, ml_prob=0.5, market_prob=0.9))
        wta = hand_set_blend(EnsembleInput(tour="WTA", elo_prob=0.5, ml_prob=0.5, market_prob=0.9))
        assert atp.weights["market"] > wta.weights["market"]

    def test_an_unknown_tour_falls_back_to_the_default_weights(self):
        result = hand_set_blend(EnsembleInput(tour="CHALLENGER", elo_prob=0.6, ml_prob=0.6, market_prob=0.6))
        assert result.weights["elo"] == pytest.approx(0.4)
        assert result.weights["market"] == pytest.approx(0.2)


class TestQualityDegradation:
    def test_stale_odds_halve_the_market_weight_and_flag_it(self):
        fresh = _blend(elo_prob=0.6, ml_prob=0.6, market_prob=0.9)
        stale = _blend(elo_prob=0.6, ml_prob=0.6, market_prob=0.9, market_stale=True)
        assert stale.weights["market"] < fresh.weights["market"]
        assert "stale_odds" in stale.quality_flags

    def test_a_high_overround_market_is_trusted_less(self):
        fresh = _blend(elo_prob=0.6, ml_prob=0.6, market_prob=0.9)
        wide = _blend(elo_prob=0.6, ml_prob=0.6, market_prob=0.9, market_high_overround=True)
        assert wide.weights["market"] < fresh.weights["market"]
        assert "high_overround" in wide.quality_flags

    def test_a_fallback_elo_is_trusted_less(self):
        full = _blend(elo_prob=0.9, ml_prob=0.5, market_prob=0.5)
        fallback = _blend(elo_prob=0.9, ml_prob=0.5, market_prob=0.5, elo_fallback=True)
        assert fallback.weights["elo"] < full.weights["elo"]
        assert "elo_fallback_used" in fallback.quality_flags

    def test_partial_rolling_stats_are_flagged_but_do_not_cut_the_model_weight(self):
        full = _blend(elo_prob=0.5, ml_prob=0.9, market_prob=0.5)
        partial = _blend(elo_prob=0.5, ml_prob=0.9, market_prob=0.5, ml_features_partial=True)
        assert partial.weights == full.weights
        assert "ml_features_partial" in partial.quality_flags

    def test_degrading_one_source_still_leaves_weights_normalised(self):
        result = _blend(elo_prob=0.6, ml_prob=0.7, market_prob=0.5, market_stale=True)
        assert sum(result.weights.values()) == pytest.approx(1.0)


class TestUnusableElo:
    def test_missing_elo_gives_its_weight_to_the_market_not_ml(self):
        # WTA base: elo 0.40, ml 0.45, market 0.15
        result = hand_set_blend(EnsembleInput(tour="WTA", ml_prob=0.66, market_prob=0.23))
        assert result.weights["ml"] == pytest.approx(0.45)
        assert result.weights["market"] == pytest.approx(0.55)
        assert "elo_missing" in result.quality_flags

    def test_missing_elo_and_market_renormalise_onto_ml(self):
        result = _blend(ml_prob=0.66)
        assert result.weights == {"ml": 1.0}

    def test_unreliable_elo_is_weighted_like_missing_elo(self):
        missing = hand_set_blend(EnsembleInput(tour="WTA", ml_prob=0.5, market_prob=0.23))
        unreliable = hand_set_blend(EnsembleInput(
            tour="WTA", elo_prob=0.74, ml_prob=0.5, market_prob=0.23, elo_unreliable=True,
        ))
        assert unreliable.weights == missing.weights
        assert unreliable.p1_win_prob == pytest.approx(missing.p1_win_prob)
        assert "elo_unreliable" in unreliable.quality_flags
        assert "elo_missing" not in unreliable.quality_flags

    def test_unreliable_elo_is_still_echoed_for_display(self):
        result = _blend(elo_prob=0.74, ml_prob=0.5, market_prob=0.23, elo_unreliable=True)
        assert result.elo_prob == 0.74

    def test_the_market_discount_applies_to_the_weight_it_took_from_elo(self):
        fresh = hand_set_blend(EnsembleInput(tour="WTA", ml_prob=0.5, market_prob=0.3))
        stale = hand_set_blend(EnsembleInput(tour="WTA", ml_prob=0.5, market_prob=0.3, market_stale=True))
        assert stale.weights["market"] < fresh.weights["market"]
        assert sum(stale.weights.values()) == pytest.approx(1.0)


class TestEloReliability:
    def test_no_elo_is_not_unreliable(self):
        assert not elo_is_unreliable(None, 0.3, 2)

    def test_a_gap_just_under_the_limit_is_trusted(self):
        assert not elo_is_unreliable(0.60, 0.60 - ELO_MAX_MARKET_GAP + 0.001, 50)

    def test_a_gap_at_the_limit_is_unreliable(self):
        assert elo_is_unreliable(0.60, 0.60 - ELO_MAX_MARKET_GAP, 50)

    def test_a_gap_in_either_direction_counts(self):
        assert elo_is_unreliable(0.23, 0.74, 50)

    def test_a_thin_history_is_unreliable_even_when_elo_agrees(self):
        assert elo_is_unreliable(0.60, 0.60, ELO_MIN_PRIOR_MATCHES - 1)

    def test_the_minimum_history_is_enough(self):
        assert not elo_is_unreliable(0.60, 0.60, ELO_MIN_PRIOR_MATCHES)

    def test_without_a_market_only_history_can_flag_it(self):
        assert not elo_is_unreliable(0.90, None, 50)
        assert not elo_is_unreliable(0.90, None, None)


class TestClamping:
    def test_certain_inputs_are_clamped_away_from_zero_and_one(self):
        assert _blend(elo_prob=1.0).p1_win_prob == 0.99
        assert _blend(elo_prob=0.0).p1_win_prob == 0.01


class TestMarketAnchored:
    def test_a_reliable_elo_gets_the_fitted_blend(self):
        result = blend(EnsembleInput(tour="ATP", elo_prob=0.62, ml_prob=0.7, market_prob=0.58))
        coefs = FIT_COEFFICIENTS["ATP"]
        assert result.p1_win_prob == pytest.approx(market_anchored_prob(coefs, 0.58, 0.62))
        assert result.weights == {"market": coefs.market, "elo": coefs.elo}
        assert "ml" not in result.weights

    @pytest.mark.parametrize("kwargs, flag", [
        ({"elo_unreliable": True}, "elo_unreliable"),
        ({"elo_fallback": True}, "elo_fallback_used"),
        ({"elo_prob": None}, "elo_missing"),
    ])
    def test_an_unusable_elo_serves_the_market(self, kwargs, flag):
        inputs = {"tour": "WTA", "elo_prob": 0.7, "market_prob": 0.4, **kwargs}
        result = blend(EnsembleInput(**inputs))
        assert result.p1_win_prob == pytest.approx(0.4)
        assert result.weights == {"market": 1.0}
        assert flag in result.quality_flags

    def test_stale_and_overround_flag_without_moving_the_probability(self):
        fresh = blend(EnsembleInput(tour="ATP", elo_prob=0.62, market_prob=0.58))
        stale = blend(EnsembleInput(tour="ATP", elo_prob=0.62, market_prob=0.58, market_stale=True))
        wide = blend(EnsembleInput(tour="ATP", elo_prob=0.62, market_prob=0.58, market_high_overround=True))
        assert stale.p1_win_prob == fresh.p1_win_prob == wide.p1_win_prob
        assert "stale_odds" in stale.quality_flags and "high_overround" in wide.quality_flags

    def test_without_a_market_the_hand_set_blend_is_unchanged(self):
        inputs = EnsembleInput(tour="ATP", elo_prob=0.6, ml_prob=0.66)
        assert blend(inputs) == hand_set_blend(inputs)

    @pytest.mark.parametrize("tour, group", [("ATP", "ATP"), ("wta", "WTA"), ("CHALLENGER", "CHALLENGER"),
                                             ("ITF", "CHALLENGER"), ("", "CHALLENGER")])
    def test_tours_map_to_their_fit_group(self, tour, group):
        assert fitted_group(tour) == group

    def test_extreme_markets_stay_clamped(self):
        assert blend(EnsembleInput(tour="ATP", market_prob=0.999)).p1_win_prob == 0.99


def test_the_served_version_is_v3():
    assert ENSEMBLE_VERSION == "ensemble-v3"
