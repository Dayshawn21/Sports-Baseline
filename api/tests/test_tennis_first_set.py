import pytest

from app.core.tennis_first_set import first_set_distribution, pmf_probabilities


@pytest.mark.parametrize(("player_hold", "opponent_hold"), [(0.78, 0.78), (0.9, 0.6), (0.55, 0.85), (0.99, 0.01)])
def test_each_distribution_sums_to_one(player_hold: float, opponent_hold: float) -> None:
    dist = first_set_distribution(player_hold, opponent_hold)

    assert sum(dist.total_games.values()) == pytest.approx(1.0)
    assert sum(dist.player_games.values()) == pytest.approx(1.0)
    assert set(dist.total_games) <= set(range(6, 14))
    assert set(dist.player_games) <= set(range(0, 8))


def test_a_player_who_wins_every_game_takes_it_six_love() -> None:
    dist = first_set_distribution(0.99, 0.01)

    assert dist.total_games[6] > 0.9
    assert dist.player_games[6] > 0.9
    assert dist.mean_total_games == pytest.approx(6.0, abs=0.15)


def test_two_perfect_servers_reach_a_tiebreak() -> None:
    dist = first_set_distribution(0.99, 0.99)

    assert dist.total_games[13] > 0.85
    # Equal servers split the tiebreak, so the player's games centre on 6.5.
    assert dist.mean_player_games == pytest.approx(dist.mean_total_games / 2)
    assert dist.player_games[7] > 0.44 and dist.player_games[6] > 0.44


def test_equal_holds_split_the_games_evenly() -> None:
    dist = first_set_distribution(0.8, 0.8)

    assert dist.mean_player_games == pytest.approx(dist.mean_total_games / 2)


def test_holds_are_clamped() -> None:
    assert first_set_distribution(1.0, 0.0) == first_set_distribution(0.99, 0.01)


def test_the_stronger_server_wins_more_games() -> None:
    assert first_set_distribution(0.9, 0.7).mean_player_games > first_set_distribution(0.7, 0.9).mean_player_games


def test_half_lines_never_push() -> None:
    pmf = first_set_distribution(0.78, 0.78).total_games

    probs = pmf_probabilities(pmf, 9.5)

    assert probs.p_push == 0.0
    assert probs.p_over == pytest.approx(sum(p for games, p in pmf.items() if games >= 10))
    assert probs.p_over + probs.p_under == pytest.approx(1.0)


def test_integer_lines_push_on_the_exact_count() -> None:
    pmf = first_set_distribution(0.78, 0.78).total_games

    probs = pmf_probabilities(pmf, 10.0)

    assert probs.p_push == pytest.approx(pmf[10])
    assert probs.p_over + probs.p_under + probs.p_push == pytest.approx(1.0)
