import pytest

from app.core.nfl_over_probability import QUANTILE_LEVELS, over_probability, ratio_quantiles

SYMMETRIC = tuple(0.5 + level for level in QUANTILE_LEVELS)
# Median ratio 0.85: the skewed shape of a yards market.
SKEWED = ratio_quantiles((1.0, r) for r in [0.0, 0.3, 0.6, 0.85, 0.85, 0.85, 1.2, 1.8, 2.6])


def test_levels_run_zero_to_one_in_41_steps() -> None:
    assert len(QUANTILE_LEVELS) == 41
    assert QUANTILE_LEVELS[0] == 0.0 and QUANTILE_LEVELS[20] == 0.5 and QUANTILE_LEVELS[-1] == 1.0


def test_symmetric_table_is_even_money_at_the_projection() -> None:
    probability = over_probability(SYMMETRIC, 50.0, 50.5)

    assert probability is not None
    assert probability.p_over == pytest.approx(0.5 - 0.5 / 50.0)
    assert probability.p_over + probability.p_under == pytest.approx(1.0)


def test_skewed_table_leans_under_at_the_projection() -> None:
    probability = over_probability(SKEWED, 60.0, 60.5)

    assert probability is not None and probability.p_over < 0.5


def test_over_probability_falls_as_the_line_rises() -> None:
    values = [over_probability(SKEWED, 60.0, line).p_over for line in (20.5, 40.5, 60.5, 80.5, 120.5)]

    assert values == sorted(values, reverse=True)
    assert values[0] > values[-1]


def test_table_ends_clamp() -> None:
    assert over_probability(SYMMETRIC, 10.0, 0.5).p_over == 1.0 - 0.0
    assert over_probability(SYMMETRIC, 10.0, 15.5).p_over == 0.0


def test_a_mass_at_zero_never_counts_as_over() -> None:
    # 21 of 101 so the 20% level lands on a zero; the 2.5% grid otherwise blurs the step by up to one level.
    quantiles = ratio_quantiles((10.0, actual) for actual in [0.0] * 21 + list(range(5, 85)))

    probability = over_probability(quantiles, 40.0, 0.5)

    assert probability is not None and probability.p_over <= 0.8


@pytest.mark.parametrize(("projection", "line"), [(40.0, 40.0), (0.0, 10.5), (-3.0, 10.5)])
def test_integer_lines_and_non_positive_projections_are_unreadable(projection: float, line: float) -> None:
    assert over_probability(SYMMETRIC, projection, line) is None


def test_ratio_quantiles_on_a_known_list() -> None:
    quantiles = ratio_quantiles([(10.0, 0.0), (10.0, 10.0), (10.0, 20.0), (10.0, 30.0), (10.0, 40.0), (0.0, 99.0)])

    assert quantiles[0] == 0.0
    assert quantiles[20] == pytest.approx(2.0)
    assert quantiles[-1] == pytest.approx(4.0)
    assert quantiles[10] == pytest.approx(1.0)


def test_ratio_quantiles_rejects_an_empty_input() -> None:
    with pytest.raises(ValueError):
        ratio_quantiles([(0.0, 5.0)])
