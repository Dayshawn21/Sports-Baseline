import ast
from math import exp, inf
from pathlib import Path

import numpy as np
import pytest

from app.core.count_over_probability import (
    MIN_R,
    MIN_VARIANCE,
    NegBinParams,
    ScaledNormalParams,
    fit_negbin,
    fit_scaled_normal,
    negbin_over_under_push,
    scaled_normal_over_under_push,
)

POISSON = NegBinParams(r=inf)
GEOMETRIC = NegBinParams(r=1.0)


def _sums_to_one(result):
    assert result.p_over + result.p_under + result.p_push == pytest.approx(1.0)


def test_poisson_half_line_matches_hand_value():
    result = negbin_over_under_push(POISSON, 2.0, 1.5)
    assert result.p_under == pytest.approx(3 * exp(-2))
    assert result.p_push == 0.0
    _sums_to_one(result)


def test_geometric_half_and_whole_lines():
    # r = 1, mean 2: p = 1/3, pmf(k) = (1/3)(2/3)^k.
    half = negbin_over_under_push(GEOMETRIC, 2.0, 1.5)
    assert half.p_under == pytest.approx(5 / 9)
    whole = negbin_over_under_push(GEOMETRIC, 2.0, 2.0)
    assert whole.p_under == pytest.approx(5 / 9)
    assert whole.p_push == pytest.approx(4 / 27)
    _sums_to_one(whole)


def test_large_r_approaches_poisson():
    near = negbin_over_under_push(NegBinParams(r=1e6), 3.0, 2.5)
    assert near.p_over == pytest.approx(negbin_over_under_push(POISSON, 3.0, 2.5).p_over, abs=1e-5)


def test_large_counts_do_not_overflow():
    result = negbin_over_under_push(NegBinParams(r=20.0), 48.0, 47.5)
    assert 0.3 < result.p_over < 0.7
    _sums_to_one(result)


@pytest.mark.parametrize("read, params", [
    (negbin_over_under_push, NegBinParams(r=4.0)),
    (scaled_normal_over_under_push, ScaledNormalParams(a=2.0, b=0.8)),
])
def test_over_falls_as_the_line_rises(read, params):
    overs = [read(params, 6.0, line).p_over for line in (2.5, 4.0, 5.5, 7.0, 8.5, 12.0)]
    assert overs == sorted(overs, reverse=True)


@pytest.mark.parametrize("read, params", [
    (negbin_over_under_push, NegBinParams(r=4.0)),
    (scaled_normal_over_under_push, ScaledNormalParams(a=2.0, b=0.8)),
])
def test_half_lines_never_push_and_whole_lines_do(read, params):
    assert read(params, 6.0, 5.5).p_push == 0.0
    whole = read(params, 6.0, 6.0)
    assert whole.p_push > 0
    _sums_to_one(whole)


@pytest.mark.parametrize("read, params", [
    (negbin_over_under_push, NegBinParams(r=4.0)),
    (scaled_normal_over_under_push, ScaledNormalParams(a=2.0, b=0.8)),
])
def test_no_projection_reads_none(read, params):
    assert read(params, 0.0, 0.5) is None
    assert read(params, -1.0, 0.5) is None


def test_scaled_normal_continuity_correction():
    # Variance 4 at projection 10: P(X <= 9) reads the normal at 9.5, z = -0.25.
    result = scaled_normal_over_under_push(ScaledNormalParams(a=4.0, b=0.0), 10.0, 9.5)
    assert result.p_under == pytest.approx(0.401294, abs=1e-6)


def test_scaled_normal_variance_floor():
    floored = scaled_normal_over_under_push(ScaledNormalParams(a=-5.0, b=0.0), 3.0, 3.5)
    at_floor = scaled_normal_over_under_push(ScaledNormalParams(a=MIN_VARIANCE, b=0.0), 3.0, 3.5)
    assert floored == at_floor


def test_fit_negbin_recovers_r():
    rng = np.random.default_rng(44)
    means = rng.uniform(1.0, 12.0, 40_000)
    actuals = rng.negative_binomial(5.0, 5.0 / (5.0 + means))
    assert fit_negbin(zip(means, actuals)).r == pytest.approx(5.0, rel=0.1)


def test_fit_negbin_underdispersed_is_poisson():
    pairs = [(4.0, 4.0), (4.0, 5.0), (4.0, 3.0), (6.0, 6.0)]
    assert fit_negbin(pairs).r == inf


def test_fit_negbin_floors_r():
    pairs = [(0.1, 30.0), (0.1, 0.0)]
    assert fit_negbin(pairs).r == MIN_R


def test_fit_scaled_normal_recovers_a_and_b():
    rng = np.random.default_rng(44)
    means = rng.uniform(5.0, 40.0, 80_000)
    actuals = rng.normal(means, np.sqrt(3.0 + 0.9 * means))
    params = fit_scaled_normal(zip(means, actuals))
    assert params.a == pytest.approx(3.0, abs=1.0)
    assert params.b == pytest.approx(0.9, abs=0.05)


def test_fit_scaled_normal_constant_projection():
    params = fit_scaled_normal([(5.0, 3.0), (5.0, 7.0)])
    assert params == ScaledNormalParams(a=4.0, b=0.0)


@pytest.mark.parametrize("fit", [fit_negbin, fit_scaled_normal])
def test_fitters_need_two_positive_projections(fit):
    with pytest.raises(ValueError):
        fit([(0.0, 3.0), (2.0, 1.0)])


def test_module_imports_no_sport_code():
    source = Path(__file__).resolve().parents[1] / "app" / "core" / "count_over_probability.py"
    names: list[str] = []
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not [name for name in names if any(sport in name for sport in ("nba", "nfl", "tennis"))]
