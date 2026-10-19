import numpy as np
import pytest

from app.core.nfl_game_environment import (
    ENVIRONMENT_ADJUSTMENT_MAX, GAME_ENVIRONMENT_SLOPES, KEEP_SLOPE_STANDARD_ERRORS, NflEnvironmentGame, NflEnvironmentSlopes,
    environment_adjustment_pct, environment_samples, fit_environment_slopes, team_lines,
)
from app.nfl.markets import NFL_V4_PROP_MARKETS, NflPropMarket

ATTEMPTS = NflPropMarket.PASSING_ATTEMPTS
SLOPES = {ATTEMPTS: NflEnvironmentSlopes(total=0.5, margin=-0.1)}


def _environment(team_total: float = 22.0, team_margin: float = 0.0) -> dict:
    return {"games": 17, "team_total": team_total, "team_margin": team_margin}


def test_both_sides_of_one_game_mirror_their_margin_and_split_the_total() -> None:
    home_total, home_margin = team_lines(3.5, 44.5, is_home=True)
    away_total, away_margin = team_lines(3.5, 44.5, is_home=False)

    assert (home_total, home_margin) == (24.0, 3.5)
    assert (away_total, away_margin) == (20.5, -3.5)
    assert home_total + away_total == 44.5


def test_a_game_like_the_baseline_games_does_not_move_the_projection() -> None:
    assert environment_adjustment_pct(ATTEMPTS, 22.0, 0.0, _environment(), SLOPES) == 0.0


def test_each_slope_moves_the_projection_in_its_own_direction() -> None:
    # 10% above the usual team total, times a 0.5 slope: +5%.
    assert environment_adjustment_pct(ATTEMPTS, 24.2, 0.0, _environment(), SLOPES) == pytest.approx(5.0)
    # A touchdown more favored than usual, times a -0.1 slope: -10%.
    assert environment_adjustment_pct(ATTEMPTS, 22.0, 7.0, _environment(), SLOPES) == pytest.approx(-10.0)
    # Trailing by a touchdown more than usual raises passing volume.
    assert environment_adjustment_pct(ATTEMPTS, 22.0, -7.0, _environment(), SLOPES) == pytest.approx(10.0)


def test_the_adjustment_is_capped_both_ways() -> None:
    cap = ENVIRONMENT_ADJUSTMENT_MAX * 100

    assert environment_adjustment_pct(ATTEMPTS, 44.0, -21.0, _environment(), SLOPES) == cap
    assert environment_adjustment_pct(ATTEMPTS, 11.0, 21.0, _environment(), SLOPES) == -cap


@pytest.mark.parametrize(("team_total", "team_margin", "environment"), [
    (None, 0.0, {"games": 17, "team_total": 22.0, "team_margin": 0.0}),
    (22.0, None, {"games": 17, "team_total": 22.0, "team_margin": 0.0}),
    (22.0, 0.0, None),
    (22.0, 0.0, {"games": 17, "team_total": 0.0, "team_margin": 0.0}),
])
def test_missing_or_invalid_inputs_give_no_adjustment(
    team_total: float | None, team_margin: float | None, environment: dict | None,
) -> None:
    assert environment_adjustment_pct(ATTEMPTS, team_total, team_margin, environment, SLOPES) is None


def test_a_market_without_slopes_gives_no_adjustment() -> None:
    assert environment_adjustment_pct(NflPropMarket.RECEPTIONS, 24.2, 0.0, _environment(), SLOPES) is None


def _game(player_id: int, team_total: float, team_margin: float, attempts: float | None, position: str = "QB") -> NflEnvironmentGame:
    return NflEnvironmentGame(player_id, position, team_total, team_margin, {"passing_attempts": attempts})


def _synthetic_games(total_slope: float, margin_slope: float, noise: float, players: int, seed: int) -> list[NflEnvironmentGame]:
    rng = np.random.default_rng(seed)
    games = []
    for player_id in range(players):
        base = rng.uniform(25, 40)
        usual_total = rng.uniform(18, 27)
        for _ in range(16):
            team_total = usual_total * (1 + rng.normal(0, 0.12))
            team_margin = rng.normal(0, 6)
            ratio = 1 + total_slope * (team_total / usual_total - 1) + margin_slope * team_margin / 7
            games.append(_game(player_id, team_total, team_margin, base * ratio * (1 + rng.normal(0, noise))))
    return games


def test_the_fit_recovers_known_slopes() -> None:
    games = _synthetic_games(total_slope=0.6, margin_slope=-0.08, noise=0.02, players=60, seed=7)

    fit = fit_environment_slopes(environment_samples(games, ATTEMPTS))

    assert fit is not None and fit.players == 60
    assert fit.total == pytest.approx(0.6, abs=0.05)
    assert fit.margin == pytest.approx(-0.08, abs=0.01)
    assert fit.kept() == NflEnvironmentSlopes(fit.total, fit.margin)


def test_a_noisy_slope_is_zeroed() -> None:
    games = _synthetic_games(total_slope=0.0, margin_slope=-0.08, noise=0.6, players=4, seed=3)

    fit = fit_environment_slopes(environment_samples(games, ATTEMPTS))

    assert fit is not None
    assert abs(fit.total) < KEEP_SLOPE_STANDARD_ERRORS * fit.total_se
    assert fit.kept().total == 0.0


def test_samples_compare_each_game_with_the_players_other_games() -> None:
    games = [_game(1, 20.0, 0.0, 30.0) for _ in range(4)] + [_game(1, 30.0, 7.0, 45.0)]

    samples = environment_samples(games, ATTEMPTS)

    last = samples[-1]
    assert len(samples) == 5
    assert (last.y, last.x_total, last.x_margin, last.weight) == pytest.approx((0.5, 0.5, 1.0, 30.0))


def test_samples_skip_thin_players_unbet_positions_missing_stats_and_zero_means() -> None:
    four_games = [_game(1, 22.0, 0.0, 30.0) for _ in range(4)]
    receiver = [_game(2, 22.0, 0.0, 1.0, position="WR") for _ in range(6)]
    missing = [_game(3, 22.0, 0.0, None) for _ in range(6)]
    zeros = [_game(4, 22.0, 0.0, 0.0) for _ in range(6)]

    assert environment_samples(four_games + receiver + missing + zeros, ATTEMPTS) == []


def test_too_few_players_cannot_be_fitted() -> None:
    games = _synthetic_games(total_slope=0.5, margin_slope=0.0, noise=0.05, players=2, seed=1)

    assert fit_environment_slopes(environment_samples(games, ATTEMPTS)) is None


def test_frozen_slopes_cover_v4_markets_but_anytime_td() -> None:
    assert set(GAME_ENVIRONMENT_SLOPES) == NFL_V4_PROP_MARKETS - {NflPropMarket.ANYTIME_TOUCHDOWN}
