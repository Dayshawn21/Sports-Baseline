from math import exp, inf, nan

import pytest

from app.core.nfl_projection import NflSeasonTouchdowns, anytime_td_probability, anytime_td_rate
from app.core.nfl_red_zone import (
    NflRedZoneCoefficients,
    NflRedZoneRates,
    NflRedZoneSeason,
    expected_td_rate,
    red_zone_rates,
    red_zone_td_probability,
)

COEFFICIENTS = NflRedZoneCoefficients(
    intercept=0.05, rz5_carry=0.40, rz6_20_carry=0.10, rz5_target=0.45, rz6_20_target=0.15,
)
POSITION = NflRedZoneRates(rz20_carries=1.0, rz20_targets=0.5, rz5_carries=0.3, rz5_targets=0.1)
ZERO = NflRedZoneRates(0.0, 0.0, 0.0, 0.0)


def test_a_zero_blend_weight_reproduces_the_production_baseline() -> None:
    seasons = [NflSeasonTouchdowns(2025, 17, 0.6), NflSeasonTouchdowns(2026, 2, 1.0)]
    historical_rate, _ = anytime_td_rate(seasons, 2026, 0.3)
    busy = NflRedZoneRates(4.0, 2.0, 2.0, 1.0)

    probability = red_zone_td_probability(historical_rate, busy, COEFFICIENTS, 0.0)

    assert round(probability, 2) == anytime_td_probability(seasons, 2026, 0.3)[0]


def test_more_goal_line_carries_raise_the_probability() -> None:
    light = NflRedZoneRates(1.0, 0.0, 0.2, 0.0)
    heavy = NflRedZoneRates(1.0, 0.0, 0.8, 0.0)

    assert red_zone_td_probability(0.3, heavy, COEFFICIENTS, 0.5) > red_zone_td_probability(0.3, light, COEFFICIENTS, 0.5)


def test_expected_rate_uses_disjoint_bands() -> None:
    # 2 inside-20 carries of which 1 is inside the 5: one goal-line carry, one 6-20 carry.
    rates = NflRedZoneRates(rz20_carries=2.0, rz20_targets=1.0, rz5_carries=1.0, rz5_targets=0.0)

    assert expected_td_rate(rates, COEFFICIENTS) == pytest.approx(0.05 + 0.40 + 0.10 + 0.15)


def test_a_player_without_red_zone_evidence_falls_back_to_the_position() -> None:
    rates, weighted_games = red_zone_rates([], 2026, POSITION)

    assert rates == pytest.approx(POSITION)
    assert weighted_games == 0.0


def test_seasons_without_loaded_play_by_play_are_not_evidence() -> None:
    unloaded = NflRedZoneSeason(2025, games=0, rates=ZERO)

    assert red_zone_rates([unloaded], 2026, POSITION) == red_zone_rates([], 2026, POSITION)


def test_player_history_is_recency_weighted_and_shrunk_toward_the_position() -> None:
    busy = NflRedZoneRates(3.0, 0.5, 1.0, 0.1)
    rates, weighted_games = red_zone_rates([NflRedZoneSeason(2025, 10, busy)], 2026, POSITION)

    # Last season weighs 0.6, so 10 games count as 6 against a 10-game position prior.
    assert weighted_games == pytest.approx(6.0)
    assert rates.rz20_carries == pytest.approx((10 * 1.0 + 6 * 3.0) / 16)
    assert rates.rz5_carries == pytest.approx((10 * 0.3 + 6 * 1.0) / 16)


def test_seasons_outside_the_recency_window_are_ignored() -> None:
    too_old = NflRedZoneSeason(2023, 17, NflRedZoneRates(9.0, 9.0, 9.0, 9.0))
    future = NflRedZoneSeason(2027, 17, NflRedZoneRates(9.0, 9.0, 9.0, 9.0))

    assert red_zone_rates([too_old, future], 2026, POSITION) == red_zone_rates([], 2026, POSITION)


@pytest.mark.parametrize("bad", [-1.0, nan, inf])
def test_negative_or_non_finite_inputs_are_clamped(bad: float) -> None:
    poisoned = NflRedZoneRates(bad, bad, bad, bad)

    rates, _ = red_zone_rates([NflRedZoneSeason(2026, 4, poisoned)], 2026, poisoned)
    probability = red_zone_td_probability(bad, poisoned, COEFFICIENTS, bad)

    assert rates == ZERO
    assert expected_td_rate(poisoned, COEFFICIENTS) == pytest.approx(0.05)
    assert 0.0 <= probability < 1.0


def test_blend_weight_is_bounded_to_the_red_zone_side() -> None:
    rates = NflRedZoneRates(2.0, 1.0, 1.0, 0.0)
    full = red_zone_td_probability(0.1, rates, COEFFICIENTS, 1.0)

    assert red_zone_td_probability(0.1, rates, COEFFICIENTS, 5.0) == full
    assert full == pytest.approx(1 - exp(-expected_td_rate(rates, COEFFICIENTS)))
