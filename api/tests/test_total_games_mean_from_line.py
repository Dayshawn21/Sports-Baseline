import pytest

from app.core.prop_probs import total_games_mean_from_line, total_games_probs


def _p_over(line: float, mean: float, best_of: int = 3, p_deciding_set: float | None = None) -> float:
    probs = total_games_probs(line, mean, p_deciding_set=p_deciding_set, best_of=best_of)
    return probs.p_over / (probs.p_over + probs.p_under)


def test_even_price_reproduces_the_line_as_the_midpoint():
    mean = total_games_mean_from_line(21.5, 0.5, best_of=3, p_deciding_set=0.4)
    assert _p_over(21.5, mean, p_deciding_set=0.4) == pytest.approx(0.5, abs=1e-6)


def test_deciding_set_mode_puts_the_mean_above_the_line():
    assert total_games_mean_from_line(21.5, 0.5, best_of=3, p_deciding_set=0.4) > 21.5


def test_over_favored_price_raises_the_mean():
    even = total_games_mean_from_line(21.5, 0.5, p_deciding_set=0.4)
    over = total_games_mean_from_line(21.5, 0.58, p_deciding_set=0.4)
    assert over > even
    assert _p_over(21.5, over, p_deciding_set=0.4) == pytest.approx(0.58, abs=1e-6)


def test_best_of_five_solves_the_same_way():
    low = total_games_mean_from_line(38.5, 0.45, best_of=5, p_deciding_set=0.3)
    high = total_games_mean_from_line(38.5, 0.55, best_of=5, p_deciding_set=0.3)
    assert low < high
    assert _p_over(38.5, high, best_of=5, p_deciding_set=0.3) == pytest.approx(0.55, abs=1e-6)


def test_unknown_deciding_set_uses_the_marginal_spread():
    mean = total_games_mean_from_line(22.5, 0.5)
    assert _p_over(22.5, mean) == pytest.approx(0.5, abs=1e-6)


@pytest.mark.parametrize("p_over", [0.0, 1.0, -3.0, 7.0])
def test_extreme_prices_are_clamped_and_stay_bounded(p_over):
    mean = total_games_mean_from_line(21.5, p_over, p_deciding_set=0.4)
    assert 21.5 - 30.0 <= mean <= 21.5 + 30.0
    expected = 0.02 if p_over < 0.5 else 0.98
    assert _p_over(21.5, mean, p_deciding_set=0.4) == pytest.approx(expected, abs=1e-4)
