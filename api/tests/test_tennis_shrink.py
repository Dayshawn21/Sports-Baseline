import pytest

from app.core import tennis_shrink as shrink
from app.core.tennis_grading import PairedDifference
from app.services.tennis.ensemble import fitted_group


def test_frozen_rule_constants():
    assert shrink.SHRINK_VERSION == "shrink-v1"
    assert shrink.SHRINK_THRESHOLD == 0.03
    assert shrink.SHRINK_WEIGHT == 0.5
    assert shrink.CHECK_VERSION == "tennis-shrink-check-v1"
    assert (shrink.MIN_AFFECTED, shrink.MIN_DAYS, shrink.SETTLEMENT_LAG_DAYS) == (400, 30, 3)
    assert shrink.MIN_COVERAGE == 0.98
    assert shrink.GATE_STANDARD_ERRORS == 2.0
    assert shrink.SLICES == ("ATP+WTA", "CHALLENGER")


@pytest.mark.parametrize("ensemble, market", [(0.53, 0.50), (0.50, 0.53), (0.36, 0.33)])
def test_a_three_point_gap_shrinks(ensemble, market):
    assert shrink.is_affected(ensemble, market)
    assert shrink.shrink_toward_market(ensemble, market) == pytest.approx(market + 0.5 * (ensemble - market))


def test_just_under_three_points_is_kept():
    assert not shrink.is_affected(0.5299, 0.50)
    assert shrink.shrink_toward_market(0.5299, 0.50) == 0.5299
    assert shrink.shrink_toward_market(0.4701, 0.50) == 0.4701


def test_shadow_keeps_half_the_gap_on_both_sides():
    assert shrink.shrink_toward_market(0.70, 0.60) == pytest.approx(0.65)
    assert shrink.shrink_toward_market(0.30, 0.40) == pytest.approx(0.35)


@pytest.mark.parametrize("ensemble, market", [(0.70, 0.60), (0.52, 0.50), (0.18, 0.25)])
def test_swapping_players_gives_one_minus(ensemble, market):
    p1 = shrink.shrink_toward_market(ensemble, market)
    p2 = shrink.shrink_toward_market(1 - ensemble, 1 - market)
    assert p1 + p2 == pytest.approx(1.0)


def test_shadow_version_appends_the_rule():
    assert shrink.shadow_version("ensemble-v3+lgbm-v6") == "ensemble-v3+lgbm-v6+shrink-v1"


@pytest.mark.parametrize("tour", ["ATP", "WTA", "CHALLENGER", "ITF", "", "wta"])
def test_slice_follows_the_served_blend_group(tour):
    expected = "ATP+WTA" if fitted_group(tour) in ("ATP", "WTA") else "CHALLENGER"
    assert shrink.slice_for(tour) == expected


@pytest.mark.parametrize("gap, bucket", [
    (0.0, "<1"), (0.0099, "<1"), (0.01, "1-3"), (0.0299, "1-3"), (0.03, "3-5"),
    (-0.03, "3-5"), (0.36 - 0.33, "3-5"), (0.0499, "3-5"), (0.05, "5+"), (-0.2, "5+"),
])
def test_gap_buckets(gap, bucket):
    assert shrink.gap_bucket(gap) == bucket


def test_three_to_five_bucket_matches_affected():
    for ensemble in (0.529, 0.53, 0.54, 0.56):
        affected = shrink.is_affected(ensemble, 0.50)
        assert affected == (shrink.gap_bucket(ensemble - 0.50) in ("3-5", "5+"))


def _diff(mean, se, n=400):
    return PairedDifference(n=n, mean=mean, standard_error=se)


def test_verdict_accrues_below_either_floor():
    better = _diff(-0.01, 0.001)
    assert shrink.verdict(better, 399, 30) == "accruing"
    assert shrink.verdict(better, 400, 29) == "accruing"


def test_verdict_adopts_only_beyond_two_standard_errors():
    assert shrink.verdict(_diff(-0.0021, 0.001), 400, 30) == "adopt"
    assert shrink.verdict(_diff(-0.002, 0.001), 400, 30) == "keep served"
    assert shrink.verdict(_diff(-0.001, 0.001), 400, 30) == "keep served"
    assert shrink.verdict(_diff(0.003, 0.001), 400, 30) == "keep served"


@pytest.mark.parametrize("se", [None, float("nan"), float("inf")])
def test_verdict_refuses_a_missing_standard_error(se):
    with pytest.raises(ValueError):
        shrink.verdict(_diff(-0.01, se), 400, 30)


def test_missing_standard_error_still_accrues_below_the_floor():
    assert shrink.verdict(_diff(-0.01, None, n=1), 1, 1) == "accruing"
