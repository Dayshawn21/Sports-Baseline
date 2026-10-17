import pytest

from app.core.bettable_criteria import _BLOCKING_FLAGS, _DOWNGRADE_FLAGS, assess_bettable_pick
from app.services.tennis.ensemble import EnsembleInput, blend


def test_hides_pick_below_five_percent_ev():
    assert assess_bettable_pick(0.72, 0.049, 0.08) is None


def test_probability_alone_does_not_create_strong():
    result = assess_bettable_pick(0.72, 0.06, 0.08)
    assert result is not None
    assert result.confidence == "LEAN"


def test_strong_requires_probability_ev_and_kelly_gates():
    low_prob = assess_bettable_pick(0.59, 0.12, 0.04)
    low_kelly = assess_bettable_pick(0.64, 0.12, 0.019)
    strong = assess_bettable_pick(0.64, 0.12, 0.03)

    assert low_prob is not None
    assert low_prob.confidence == "LEAN"
    assert low_kelly is not None
    assert low_kelly.confidence == "LEAN"
    assert strong is not None
    assert strong.confidence == "STRONG"


def test_lock_requires_all_lock_gates():
    result = assess_bettable_pick(0.69, 0.16, 0.031)
    assert result is not None
    assert result.confidence == "LOCK"


def test_weak_data_downgrades_one_tier():
    result = assess_bettable_pick(0.69, 0.16, 0.031, data_quality_flags=["small_sample"])
    assert result is not None
    assert result.confidence == "STRONG"
    assert result.downgraded is True
    assert "small_sample" in result.data_quality_flags


def test_imputed_odds_cannot_lock():
    result = assess_bettable_pick(0.76, 0.24, 0.08, odds_source="imputed")
    assert result is not None
    assert result.confidence == "STRONG"
    assert result.odds_source == "imputed"
    assert "imputed_odds" in result.data_quality_flags


def test_imputed_odds_hide_when_kelly_gate_fails():
    assert assess_bettable_pick(0.76, 0.24, 0.0, odds_source="imputed") is None


def test_imputed_odds_with_weak_data_downgrades_after_lock_cap():
    result = assess_bettable_pick(
        0.76,
        0.24,
        0.08,
        data_quality_flags=["small_sample"],
        odds_source="imputed",
    )

    assert result is not None
    assert result.confidence == "LEAN"
    assert result.downgraded is True
    assert result.odds_source == "imputed"
    assert "imputed_odds" in result.data_quality_flags
    assert "small_sample" in result.data_quality_flags


@pytest.mark.parametrize("flag", ["ml_missing", "elo_missing", "p1_elo_missing", "ml_not_trained_for_tour"])
def test_missing_model_inputs_downgrade_strong_to_lean(flag):
    result = assess_bettable_pick(0.64, 0.12, 0.03, data_quality_flags=[flag])
    assert result is not None
    assert result.confidence == "LEAN"
    assert result.downgraded is True


def test_every_missing_input_the_blend_reports_is_a_downgrade_flag():
    # One source present at a time, so each run reports the other two as missing.
    emitted: set[str] = set()
    for source in ("elo_prob", "ml_prob", "market_prob"):
        emitted.update(blend(EnsembleInput(tour="ATP", **{source: 0.6})).quality_flags)
    missing = {flag for flag in emitted if flag.endswith("_missing")}
    assert missing == {"elo_missing", "ml_missing", "market_missing"}
    assert missing <= _DOWNGRADE_FLAGS


def test_unreliable_elo_hides_even_a_lock():
    assert assess_bettable_pick(0.72, 0.20, 0.05, data_quality_flags=["elo_unreliable"]) is None


def test_unreliable_elo_hides_a_lean():
    assert assess_bettable_pick(0.56, 0.06, 0.01, data_quality_flags=["elo_unreliable"]) is None


def test_missing_elo_still_only_downgrades():
    result = assess_bettable_pick(0.56, 0.06, 0.01, data_quality_flags=["elo_missing"])
    assert result is not None
    assert result.confidence == "LEAN"


def test_the_blend_emits_the_blocking_flag_by_that_name():
    result = blend(EnsembleInput(tour="ATP", elo_prob=0.9, market_prob=0.5, elo_unreliable=True))
    assert _BLOCKING_FLAGS <= set(result.quality_flags)


def test_rolling_stats_gaps_alone_do_not_downgrade():
    result = assess_bettable_pick(0.64, 0.12, 0.03, data_quality_flags=["ml_features_partial"])
    assert result is not None
    assert result.confidence == "STRONG"
