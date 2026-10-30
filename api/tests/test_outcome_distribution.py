import math

import numpy as np
import pytest

from app.core.outcome_distribution import CompoundYards, NegativeBinomial


def _yards(mean: float = 6.0, dispersion: float = 4.0, yards_mean: float = 8.0, yards_sd: float = 9.0) -> CompoundYards:
    return CompoundYards(NegativeBinomial(mean, dispersion), yards_mean, yards_sd)


@pytest.mark.parametrize("mean, dispersion", [(0.3, 0.5), (4.0, 2.0), (25.0, 30.0)])
def test_count_pmf_sums_to_one_and_matches_closed_form_moments(mean: float, dispersion: float) -> None:
    pmf = NegativeBinomial(mean, dispersion).pmf
    k = np.arange(len(pmf))

    assert abs(pmf.sum() - 1.0) < 1e-9
    assert np.sum(k * pmf) == pytest.approx(mean, rel=1e-4)
    assert np.sum((k - mean) ** 2 * pmf) == pytest.approx(mean + mean**2 / dispersion, rel=1e-3)


def test_yards_mean_and_variance_match_the_compound_closed_form() -> None:
    yards = _yards()
    step = 0.5
    grid = np.arange(-300.0, 900.0, step) + step / 2
    cdf = np.array([yards.cdf(y) for y in grid])
    mean = np.sum((1.0 - cdf[grid >= 0]) * step) - np.sum(cdf[grid < 0] * step)
    second = np.sum(2 * grid[grid >= 0] * (1.0 - cdf[grid >= 0]) * step) - np.sum(2 * grid[grid < 0] * cdf[grid < 0] * step)

    n_var = 6.0 + 6.0**2 / 4.0
    assert mean == pytest.approx(6.0 * 8.0, rel=1e-2)
    assert second - mean**2 == pytest.approx(6.0 * 9.0**2 + n_var * 8.0**2, rel=2e-2)


def test_the_median_of_a_right_skewed_case_sits_below_its_mean() -> None:
    assert NegativeBinomial(3.0, 1.0).median() < 3.0
    assert _yards(mean=2.0, dispersion=0.8, yards_mean=10.0, yards_sd=12.0).median() < 20.0


def test_the_median_is_where_the_cdf_first_reaches_one_half() -> None:
    counts = NegativeBinomial(4.0, 2.0)
    m = counts.median()
    assert counts.cdf(m) >= 0.5 and counts.cdf(m - 1) < 0.5

    yards = _yards()
    assert yards.cdf(yards.median()) == pytest.approx(0.5, abs=1e-9)


def test_a_mostly_zero_yards_case_has_its_median_on_the_point_mass() -> None:
    assert _yards(mean=0.3, dispersion=1.0).median() == 0.0


@pytest.mark.parametrize("line", [-1.0, 0.0, 2.0, 3.5, 40.0])
def test_count_over_under_and_push_sum_to_one_with_push_only_on_whole_lines(line: float) -> None:
    result = NegativeBinomial(4.0, 2.0).p_over(line)

    assert result.over + result.under + result.push == pytest.approx(1.0, abs=1e-12)
    assert min(result.over, result.under, result.push) >= 0.0
    if line != math.floor(line) or line < 0:
        assert result.push == 0.0


def test_a_whole_count_line_pushes_with_its_own_probability() -> None:
    counts = NegativeBinomial(4.0, 2.0)

    assert counts.p_over(2.0).push == pytest.approx(float(counts.pmf[2]))
    assert counts.p_over(2.0).over == pytest.approx(1.0 - counts.cdf(2.0))


@pytest.mark.parametrize("line", [0.0, 24.5, 60.5])
def test_yards_over_under_and_push_sum_to_one(line: float) -> None:
    yards = _yards(mean=1.5, dispersion=2.0)
    result = yards.p_over(line)

    assert result.over + result.under + result.push == pytest.approx(1.0, abs=1e-12)
    assert result.push == (pytest.approx(float(yards.opportunities.pmf[0])) if line == 0 else 0.0)


def test_crps_by_hand_for_a_point_mass_away_from_the_actual() -> None:
    # F is 1 from zero on and the actual's indicator is 0 until it, so CRPS is the gap.
    assert NegativeBinomial(0.0, 1.0).crps(3) == pytest.approx(3.0)
    assert _yards(mean=0.0).crps(5.0) == pytest.approx(5.0)


def test_crps_is_zero_for_a_point_mass_at_the_actual() -> None:
    assert NegativeBinomial(0.0, 1.0).crps(0) == 0.0
    assert _yards(mean=0.0).crps(0.0) == 0.0


@pytest.mark.parametrize("actual", [0, 2, 9])
def test_count_crps_matches_the_energy_form(actual: int) -> None:
    counts = NegativeBinomial(3.0, 1.5)
    pmf = counts.pmf
    k = np.arange(len(pmf))
    energy = np.sum(pmf * np.abs(k - actual)) - 0.5 * np.sum(np.outer(pmf, pmf) * np.abs(k[:, None] - k[None, :]))

    assert counts.crps(actual) == pytest.approx(energy, abs=1e-9)


def test_yards_crps_rewards_the_closer_forecast_and_reaches_actuals_off_the_grid() -> None:
    yards = _yards()

    assert yards.crps(48.0) < yards.crps(150.0)
    assert yards.crps(700.0) > yards.crps(590.0)
    assert yards.crps(-30.0) > yards.crps(-10.0)


def test_a_count_crps_refuses_a_fractional_or_negative_actual() -> None:
    with pytest.raises(ValueError):
        NegativeBinomial(3.0, 1.5).crps(2.5)
    with pytest.raises(ValueError):
        NegativeBinomial(3.0, 1.5).crps(-1)


@pytest.mark.parametrize("mean, dispersion", [(-1.0, 2.0), (float("nan"), 2.0), (3.0, 0.0), (3.0, -1.0), (3.0, float("inf"))])
def test_invalid_count_parameters_raise(mean: float, dispersion: float) -> None:
    with pytest.raises(ValueError):
        NegativeBinomial(mean, dispersion)


@pytest.mark.parametrize("yards_mean, yards_sd", [(8.0, 0.0), (8.0, -2.0), (float("nan"), 9.0), (8.0, float("inf"))])
def test_invalid_yards_parameters_raise(yards_mean: float, yards_sd: float) -> None:
    with pytest.raises(ValueError):
        CompoundYards(NegativeBinomial(4.0, 2.0), yards_mean, yards_sd)
