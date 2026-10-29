import pytest

from app.core.tennis_first_set import _final_scores, first_set_distribution, pmf_mean
from app.core.tennis_match_chain import match_distribution, mixed_match_distribution


@pytest.mark.parametrize("best_of", [3, 5])
@pytest.mark.parametrize(("hold_a", "hold_b"), [(0.78, 0.78), (0.9, 0.6), (0.55, 0.85), (0.99, 0.01)])
def test_distributions_sum_to_one(hold_a: float, hold_b: float, best_of: int) -> None:
    dist = match_distribution(hold_a, hold_b, best_of)

    assert sum(dist.set_scores.values()) == pytest.approx(1.0, abs=1e-9)
    assert sum(dist.total_games.values()) == pytest.approx(1.0, abs=1e-9)
    sets_to_win = best_of // 2 + 1
    assert all(max(score) == sets_to_win for score in dist.set_scores)
    assert set(dist.set_count) <= set(range(sets_to_win, best_of + 1))


@pytest.mark.parametrize("best_of", [3, 5])
def test_equal_holds_split_the_match_evenly(best_of: int) -> None:
    dist = match_distribution(0.8, 0.8, best_of)

    assert dist.win_prob == pytest.approx(0.5, abs=1e-12)
    for (a_sets, b_sets), p in dist.set_scores.items():
        assert p == pytest.approx(dist.set_scores[(b_sets, a_sets)], abs=1e-12)


def test_one_set_is_the_first_set_chain() -> None:
    dist = match_distribution(0.83, 0.71, best_of=1)
    first = first_set_distribution(0.83, 0.71)

    set_win = sum(
        p / 2
        for a_first in (True, False)
        for (a_games, b_games), p in _final_scores(0.83, 0.71, a_first).items()
        if a_games > b_games
    )

    assert dist.total_games == pytest.approx(first.total_games, abs=1e-12)
    assert dist.win_prob == pytest.approx(set_win, abs=1e-12)


def test_one_set_win_prob_is_symmetric_under_swap() -> None:
    forward = match_distribution(0.83, 0.71, best_of=1)
    reverse = match_distribution(0.71, 0.83, best_of=1)

    assert forward.win_prob + reverse.win_prob == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("best_of", [3, 5])
def test_a_stronger_server_wins_more(best_of: int) -> None:
    base = match_distribution(0.75, 0.75, best_of)
    stronger = match_distribution(0.85, 0.75, best_of)

    assert stronger.win_prob > base.win_prob


@pytest.mark.parametrize("best_of", [3, 5])
def test_better_serving_on_both_sides_lengthens_the_match(best_of: int) -> None:
    shorter = match_distribution(0.70, 0.65, best_of)
    longer = match_distribution(0.80, 0.75, best_of)

    assert pmf_mean(longer.total_games) > pmf_mean(shorter.total_games)


def test_no_effect_is_the_plain_chain() -> None:
    assert mixed_match_distribution(0.8, 0.7, 3, 0.0) == match_distribution(0.8, 0.7, 3)


@pytest.mark.parametrize("best_of", [3, 5])
def test_the_effect_keeps_a_distribution_and_symmetry(best_of: int) -> None:
    dist = mixed_match_distribution(0.8, 0.8, best_of, 0.14)

    assert sum(dist.set_scores.values()) == pytest.approx(1.0, abs=1e-9)
    assert sum(dist.total_games.values()) == pytest.approx(1.0, abs=1e-9)
    assert dist.win_prob == pytest.approx(0.5, abs=1e-12)


def test_the_effect_cuts_deciding_sets() -> None:
    plain = match_distribution(0.8, 0.8, 3)
    mixed = mixed_match_distribution(0.8, 0.8, 3, 0.14)

    assert mixed.set_count[3] < plain.set_count[3]


def test_holds_are_clamped() -> None:
    assert match_distribution(1.0, 0.0) == match_distribution(0.99, 0.01)
