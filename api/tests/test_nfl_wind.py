import random

import pytest

from app.backtest.nfl_wind_fit import report
from app.core.nfl_game_environment import NflEnvironmentGame
from app.core.nfl_wind import WIND_MARKETS, WIND_SLOPES, excess_wind, fit_wind_slope, wind_adjustment_pct, wind_samples
from app.nfl.markets import NflPropMarket

YARDS = NflPropMarket.PASSING_YARDS


@pytest.mark.parametrize(("roof", "wind", "expected"), [
    ("dome", None, 0.0),
    ("closed", 25, 0.0),
    ("outdoors", 25, 1.5),
    ("open", 20, 1.0),
    ("outdoors", 10, 0.0),
    ("outdoors", 4, 0.0),
    ("outdoors", None, None),
    (None, 25, None),
    ("retractable", 25, None),
])
def test_excess_wind_counts_only_outdoor_wind_above_ten_mph(roof: str | None, wind: int | None, expected: float | None) -> None:
    assert excess_wind(roof, wind) == expected


def test_adjustment_follows_the_slope_sign_and_is_capped() -> None:
    assert wind_adjustment_pct(YARDS, 1.0, {YARDS: -0.06}) == -6.0
    assert wind_adjustment_pct(YARDS, 1.0, {YARDS: 0.04}) == 4.0
    assert wind_adjustment_pct(YARDS, 3.0, {YARDS: -0.2}) == -15.0
    assert wind_adjustment_pct(YARDS, 0.0, {YARDS: -0.2}) == 0.0


def test_no_adjustment_without_wind_or_a_slope() -> None:
    assert wind_adjustment_pct(YARDS, None, {YARDS: -0.06}) is None
    assert wind_adjustment_pct(NflPropMarket.RECEIVING_YARDS, 1.0, {YARDS: -0.06}) is None


def _game(player_id: int, yards: float | None, roof: str | None = "outdoors", wind: int | None = 5) -> NflEnvironmentGame:
    return NflEnvironmentGame(player_id, "QB", 22.0, 0.0, {"passing_yards": yards}, roof=roof, wind=wind)


def test_unknown_wind_games_are_no_sample_but_stay_in_the_baseline() -> None:
    games = [_game(1, 200.0) for _ in range(3)] + [_game(1, 300.0, wind=None), _game(1, 150.0, wind=30)]

    samples = wind_samples(games, YARDS)

    assert len(samples) == 4
    windy = next(sample for sample in samples if sample.x > 0)
    # The leave-one-out mean includes the unknown-wind 300-yard game.
    assert windy.weight == pytest.approx(225.0)
    assert windy.y == pytest.approx(150.0 / 225.0 - 1)
    assert windy.x == pytest.approx(2.0)


def test_players_need_enough_other_games_and_a_passing_position() -> None:
    few = [_game(1, 200.0) for _ in range(4)]
    receiver = [NflEnvironmentGame(2, "WR", 22.0, 0.0, {"passing_yards": 10.0}, roof="outdoors", wind=20) for _ in range(6)]

    assert wind_samples(few + receiver, YARDS) == []


def _synthetic_games(slope: float, noise: float, players: int, seed: int) -> list[NflEnvironmentGame]:
    rng = random.Random(seed)
    games = []
    for player_id in range(players):
        base = rng.uniform(180.0, 280.0)
        for _ in range(14):
            wind = rng.choice([0, 5, 8, 12, 15, 20, 25])
            excess = max(0.0, wind - 10) / 10
            games.append(_game(player_id, base * (1 + slope * excess + rng.gauss(0.0, noise)), wind=wind))
    return games


def test_the_fit_recovers_a_known_slope() -> None:
    fit = fit_wind_slope(wind_samples(_synthetic_games(slope=-0.08, noise=0.02, players=50, seed=5), YARDS))

    assert fit is not None and fit.players == 50 and fit.windy > 0
    assert fit.slope == pytest.approx(-0.08, abs=0.01)
    assert fit.kept() == fit.slope


def test_a_noisy_slope_is_zeroed() -> None:
    fit = fit_wind_slope(wind_samples(_synthetic_games(slope=-0.02, noise=0.6, players=4, seed=3), YARDS))

    assert fit is not None
    assert fit.kept() == 0.0


def test_too_few_players_cannot_be_fitted() -> None:
    assert fit_wind_slope(wind_samples(_synthetic_games(slope=-0.08, noise=0.02, players=2, seed=1), YARDS)) is None


def test_frozen_slopes_cover_exactly_the_wind_markets() -> None:
    assert set(WIND_SLOPES) == WIND_MARKETS


def test_fit_report_counts_coverage_and_prints_each_market() -> None:
    games = [
        *_synthetic_games(slope=-0.08, noise=0.02, players=5, seed=2),
        _game(99, 200.0, roof="dome", wind=None), _game(99, 210.0, wind=None),
    ]

    text = report(2024, games)

    assert "72 total, 1 indoor" in text and "1 wind unknown" in text
    assert all(market.value in text for market in WIND_MARKETS)
    assert "passing_attempts" in text and "not enough players" in text
