import pytest

from app.core.tennis_match_chain import p_over_line, solve_holds


@pytest.mark.parametrize(
    ("win_prob", "best_of", "line", "p_over"),
    [(0.66, 3, 22.5, 0.509), (0.65, 5, 37.5, 0.5)],
)
def test_both_targets_are_reproduced(win_prob: float, best_of: int, line: float, p_over: float) -> None:
    solution = solve_holds(win_prob, best_of, total_line=line, p_over=p_over)

    assert not solution.clamped
    assert solution.distribution.win_prob == pytest.approx(win_prob, abs=1e-4)
    assert p_over_line(solution.distribution.total_games, line) == pytest.approx(p_over, abs=1e-4)


def test_swapping_the_players_mirrors_the_holds() -> None:
    forward = solve_holds(0.66, total_line=22.5, p_over=0.509)
    reverse = solve_holds(0.34, total_line=22.5, p_over=0.509)

    assert reverse.hold_a == pytest.approx(forward.hold_b, abs=1e-4)
    assert reverse.hold_b == pytest.approx(forward.hold_a, abs=1e-4)


def test_a_higher_line_at_the_same_price_raises_the_holds() -> None:
    lower = solve_holds(0.6, total_line=22.5)
    higher = solve_holds(0.6, total_line=23.5)

    assert higher.hold_a + higher.hold_b > lower.hold_a + lower.hold_b


def test_without_a_total_the_level_comes_from_stats() -> None:
    solution = solve_holds(0.65, stats_level=0.78)

    assert not solution.clamped
    assert (solution.hold_a + solution.hold_b) / 2 == pytest.approx(0.78)
    assert solution.distribution.win_prob == pytest.approx(0.65, abs=1e-4)


def test_an_unreachable_total_is_clamped_not_looped() -> None:
    # At 0.65 the chain never prices 21.5 below about 0.51 over, at any level.
    solution = solve_holds(0.65, total_line=21.5, p_over=0.45)

    assert solution.clamped
    assert solution.distribution.win_prob == pytest.approx(0.65, abs=1e-4)


def test_an_unreachable_win_prob_is_clamped() -> None:
    assert solve_holds(0.999, stats_level=0.95).clamped


def test_a_level_or_line_is_required() -> None:
    with pytest.raises(ValueError):
        solve_holds(0.6)
