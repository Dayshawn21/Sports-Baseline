import ast
import math
import random
from pathlib import Path

import pytest

from app.core import nfl_volume_anchor as anchor
from app.core import prop_ranking_rule as rule
from app.core.nfl_volume_projection import NFL_VOLUME_MODEL_VERSION


def test_identity_blend_returns_the_projection():
    over, under = anchor.anchored_probability(0.62, 0.0, 0.0, 1.0)
    assert over == pytest.approx(0.62)
    assert under == pytest.approx(0.38)


def test_zero_slope_returns_the_intercept_only():
    over, _ = anchor.anchored_probability(0.9, 0.0, 0.0, 0.0)
    assert over == pytest.approx(0.5)
    shifted, _ = anchor.anchored_probability(0.9, 0.0, 0.4, 0.0)
    assert shifted == pytest.approx(1.0 / (1.0 + math.exp(-0.4)))


def test_slope_below_one_shrinks_toward_half():
    over, _ = anchor.anchored_probability(0.8, 0.0, 0.0, 0.5)
    assert 0.5 < over < 0.8


@pytest.mark.parametrize("q_vol", [0.0, 0.1, 0.5, 0.97, 1.0])
@pytest.mark.parametrize("p_push", [0.0, 0.08, 0.5])
def test_over_under_push_sum_to_one(q_vol, p_push):
    over, under = anchor.anchored_probability(q_vol, p_push, 0.2, 0.7)
    assert over + under + p_push == pytest.approx(1.0)


def test_clamp_holds_at_the_extremes():
    low, _ = anchor.anchored_probability(0.0, 0.0, 0.0, 1.0)
    high, _ = anchor.anchored_probability(1.0, 0.0, 0.0, 1.0)
    assert low == pytest.approx(anchor.ANCHOR_Q_CLAMP)
    assert high == pytest.approx(1.0 - anchor.ANCHOR_Q_CLAMP)


@pytest.mark.parametrize("kwargs", [{"q_vol": -0.1, "p_push": 0.0}, {"q_vol": 1.1, "p_push": 0.0},
                                    {"q_vol": 0.5, "p_push": -0.1}, {"q_vol": 0.5, "p_push": 1.0}])
def test_invalid_probabilities_raise(kwargs):
    with pytest.raises(ValueError):
        anchor.anchored_probability(a=0.0, b=1.0, **kwargs)


def test_conditional_over_removes_the_push():
    assert anchor.conditional_over(0.45, 0.45) == pytest.approx(0.5)
    assert anchor.conditional_over(0.3, 0.6) == pytest.approx(1 / 3)
    with pytest.raises(ValueError):
        anchor.conditional_over(0.0, 0.0)


def test_rule_constants_are_pinned_to_27i_and_the_spec():
    assert anchor.ANCHOR_PICK_RULE == {
        "min_pick_margin": rule.MIN_PICK_MARGIN, "min_picks": rule.MIN_PICKS,
        "min_periods": rule.MIN_PERIODS, "standard_errors": rule.STANDARD_ERRORS_REQUIRED,
    }
    assert anchor.ANCHOR_PICK_RULE == {"min_pick_margin": 0.03, "min_picks": 200, "min_periods": 4, "standard_errors": 2.0}
    assert anchor.LOG_LOSS_STANDARD_ERRORS == 2.0
    assert anchor.LOG_LOSS_MIN_WEEKS_WON == 3
    assert anchor.LOG_LOSS_REFERENCES == ("raw_volume", "constant_half")
    assert anchor.NFL_VOLUME_ANCHOR_VERSION == "nfl-volume-anchor-v1"
    assert (anchor.ANCHOR_MARKET, anchor.ANCHOR_FIT_SEASON) == ("receptions", 2026)
    assert (anchor.ANCHOR_FIT_FIRST_WEEK, anchor.ANCHOR_FIT_LAST_WEEK) == (1, 8)
    assert anchor.ANCHOR_MIN_FIT_PAIRS == 400
    assert anchor.ANCHOR_Q_CLAMP == 0.001


@pytest.mark.parametrize("market", [
    "passing_attempts", "passing_completions", "passing_yards", "receiving_yards",
    "rushing_attempts", "rushing_yards", "anytime_touchdown",
])
def test_every_non_receptions_market_is_refused(market):
    with pytest.raises(anchor.AnchorRefused):
        anchor.require_anchorable(market, NFL_VOLUME_MODEL_VERSION)


def test_only_the_adopted_model_version_is_accepted():
    anchor.require_anchorable("receptions", NFL_VOLUME_MODEL_VERSION)
    with pytest.raises(anchor.AnchorRefused):
        anchor.require_anchorable("receptions", "opponent-dvp-tg-blend-usage-snap-v4")


def test_module_stays_pure():
    tree = ast.parse(Path(anchor.__file__).read_text())
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in (node.names if isinstance(node, ast.Import) else [None])
    }
    forbidden = ("sqlalchemy", "httpx", "requests", "lightgbm", "xgboost", "joblib", "app.db", "app.repositories")
    assert not [name for name in imported if name and name.startswith(forbidden)]


def _simulate(a, b, n, seed=1):
    rng = random.Random(seed)
    pairs = []
    for _ in range(n):
        q_vol = rng.uniform(0.15, 0.85)
        truth = 1.0 / (1.0 + math.exp(-(a + b * math.log(q_vol / (1 - q_vol)))))
        pairs.append((q_vol, rng.random() < truth))
    return pairs


def test_fit_recovers_known_constants():
    fit = anchor.fit_anchor(_simulate(-0.2, 0.6, 20000))
    assert fit.a == pytest.approx(-0.2, abs=4 * fit.a_se)
    assert fit.b == pytest.approx(0.6, abs=4 * fit.b_se)
    assert fit.pairs == 20000
    assert 0 < fit.a_se < 0.05 and 0 < fit.b_se < 0.05


def test_fit_slope_is_near_zero_when_outcomes_ignore_the_projection():
    rng = random.Random(7)
    pairs = [(rng.uniform(0.1, 0.9), rng.random() < 0.5) for _ in range(20000)]
    fit = anchor.fit_anchor(pairs)
    assert abs(fit.b) < 4 * fit.b_se


def test_fit_matches_the_identity_when_the_projection_is_calibrated():
    fit = anchor.fit_anchor(_simulate(0.0, 1.0, 20000, seed=3))
    assert fit.b == pytest.approx(1.0, abs=4 * fit.b_se)


def test_fit_below_the_minimum_raises():
    with pytest.raises(ValueError, match="at least 400"):
        anchor.fit_anchor(_simulate(0.0, 1.0, anchor.ANCHOR_MIN_FIT_PAIRS - 1))
    anchor.fit_anchor(_simulate(0.0, 1.0, anchor.ANCHOR_MIN_FIT_PAIRS))


def test_perfectly_separated_sample_raises():
    pairs = [(0.2 + 0.001 * i, False) for i in range(250)] + [(0.6 + 0.001 * i, True) for i in range(250)]
    with pytest.raises(ValueError, match="separates"):
        anchor.fit_anchor(pairs)


def test_all_same_outcome_raises():
    with pytest.raises(ValueError, match="same"):
        anchor.fit_anchor([(0.5, True)] * 500)


def test_constant_projection_raises_as_singular():
    pairs = [(0.5, i % 2 == 0) for i in range(500)]
    with pytest.raises(ValueError, match="singular"):
        anchor.fit_anchor(pairs)


def test_frozen_parameters_match_the_recorded_run():
    assert anchor.NFL_VOLUME_ANCHOR_PARAMETERS == anchor.AnchorParameters(a=-0.0136, b=0.4341)


def test_frozen_parameters_shrink_toward_the_line():
    params = anchor.NFL_VOLUME_ANCHOR_PARAMETERS
    over, under = anchor.anchored_probability(0.8, 0.05, params.a, params.b)
    assert 0.5 < over / (over + under) < 0.8
    assert over + under + 0.05 == pytest.approx(1.0)
