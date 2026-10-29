import math
import time

import numpy as np
import pytest

from app.core.prop_projection import markov_hold
from app.core.tennis_match_chain import SET_EFFECT_SD, mixed_match_distribution, p_over_line
from app.core.tennis_match_sim import MatchDraws, serve_point_prob, service_game_table, simulate_match

SPWS = [0.35, 0.5, 0.62, 0.7, 0.85, 0.97]


@pytest.mark.parametrize("hold", [0.25, 0.5, 0.78, 0.92, 0.99])
def test_serve_point_prob_inverts_markov_hold(hold: float) -> None:
    assert markov_hold(serve_point_prob(hold)) == pytest.approx(hold, abs=1e-6)


def test_serve_point_prob_rises_with_hold() -> None:
    assert serve_point_prob(0.6) < serve_point_prob(0.8) < serve_point_prob(0.95)


@pytest.mark.parametrize("spw", SPWS)
def test_table_sums_to_one(spw: float) -> None:
    assert sum(service_game_table(spw).values()) == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("spw", SPWS)
def test_held_mass_is_markov_hold(spw: float) -> None:
    held = sum(p for (is_held, _, _), p in service_game_table(spw).items() if is_held)

    assert held == pytest.approx(markov_hold(spw), abs=1e-6)


@pytest.mark.parametrize("spw", SPWS)
def test_every_row_is_a_finished_game(spw: float) -> None:
    for held, won, lost in service_game_table(spw):
        winner, loser = (won, lost) if held else (lost, won)
        assert winner >= 4
        assert winner - loser == 2 or (winner == 4 and loser <= 2)


def test_long_deuce_games_keep_their_own_rows() -> None:
    table = service_game_table(0.5)

    # Reach deuce (20 orders of 3-3), return to it 7 times, then win two points.
    assert table[(True, 12, 10)] == pytest.approx(20 * 0.5**6 * 0.5**7 * 0.25)


def test_love_hold_and_love_break_have_exact_mass() -> None:
    table = service_game_table(0.6)

    assert table[(True, 4, 0)] == pytest.approx(0.6**4)
    assert table[(False, 0, 4)] == pytest.approx(0.4**4)


def _draws(best_of: int = 3, draws: int = 4_000, seed: int = 7, **kwargs: float) -> MatchDraws:
    return simulate_match(0.82, 0.74, best_of, 0.08, 0.05, 0.03, 0.045, draws=draws, seed=seed, **kwargs)


def test_the_same_seed_repeats_and_another_does_not() -> None:
    first, again, other = _draws(seed=3), _draws(seed=3), _draws(seed=4)

    assert np.array_equal(first.games_won, again.games_won)
    assert np.array_equal(first.aces, again.aces)
    assert not np.array_equal(first.games_won, other.games_won)


@pytest.mark.parametrize(("best_of", "line"), [(3, 22.5), (5, 37.5)])
def test_draws_agree_with_the_exact_chain(best_of: int, line: float) -> None:
    draws = 20_000
    sim = _draws(best_of, draws=draws)
    exact = mixed_match_distribution(0.82, 0.74, best_of, SET_EFFECT_SD)

    def within_three_se(sampled: float, expected: float) -> bool:
        return abs(sampled - expected) <= 3 * math.sqrt(expected * (1 - expected) / draws)

    total = sim.total_games
    sim_over = (total > line).sum() / ((total > line).sum() + (total < line).sum())
    assert within_three_se(sim.a_wins.mean(), exact.win_prob)
    assert within_three_se(sim_over, p_over_line(exact.total_games, line))
    for sets, p in exact.set_count.items():
        assert within_three_se((sim.sets_won.sum(axis=0) == sets).mean(), p)


@pytest.mark.parametrize("best_of", [3, 5])
def test_every_draw_is_a_finished_match(best_of: int) -> None:
    sim = _draws(best_of)
    sets_to_win = best_of // 2 + 1

    assert np.all(sim.sets_won.max(axis=0) == sets_to_win)
    assert np.all(sim.sets_won.min(axis=0) < sets_to_win)
    first = sim.first_set_games
    assert np.all((first.max(axis=0) == 7) | ((first.max(axis=0) == 6) & (first.min(axis=0) <= 4)))
    assert np.all(sim.tie_breaks <= best_of)


def test_aces_and_double_faults_fit_their_serve_points() -> None:
    sim = _draws(ace_shape=2.0, df_shape=2.0)

    assert np.all(sim.aces <= sim.serve_points_won)
    assert np.all(sim.double_faults <= sim.serve_points_lost)


def test_breaks_come_from_the_opponents_lost_serve_points() -> None:
    sim = _draws()

    # A broken service game costs its server at least 4 points.
    assert np.all(4 * sim.breaks[0] <= sim.serve_points_lost[1])
    assert np.all(4 * sim.breaks[1] <= sim.serve_points_lost[0])
    assert np.all(sim.breaks <= sim.games_won)


def test_the_weaker_server_is_broken_more() -> None:
    even = simulate_match(0.8, 0.8, 3, 0.0, 0.0, 0.0, 0.0, draws=20_000, seed=5, effect_sd=0.0)
    uneven = simulate_match(0.9, 0.7, 3, 0.0, 0.0, 0.0, 0.0, draws=20_000, seed=5, effect_sd=0.0)

    assert even.breaks[0].mean() == pytest.approx(even.breaks[1].mean(), rel=0.05)
    assert uneven.breaks[0].mean() > 2 * uneven.breaks[1].mean()


def test_aces_scale_with_the_rate() -> None:
    low = simulate_match(0.8, 0.8, 3, 0.04, 0.05, 0.03, 0.03, seed=11)
    high = simulate_match(0.8, 0.8, 3, 0.08, 0.05, 0.03, 0.03, seed=11)

    assert high.aces[0].mean() == pytest.approx(2 * low.aces[0].mean(), rel=0.08)


def test_dispersion_widens_aces_without_moving_their_mean() -> None:
    fixed = _draws(draws=20_000)
    dispersed = _draws(draws=20_000, ace_shape=2.0)

    assert dispersed.aces[0].mean() == pytest.approx(fixed.aces[0].mean(), rel=0.03)
    assert dispersed.aces[0].var() > 1.5 * fixed.aces[0].var()


def test_four_thousand_best_of_five_draws_take_under_a_second() -> None:
    started = time.perf_counter()
    _draws(best_of=5)

    assert time.perf_counter() - started < 1.0
