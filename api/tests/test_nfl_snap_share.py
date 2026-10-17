from math import exp, inf, nan

import pytest

from app.core.nfl_projection import NflSeasonTouchdowns, anytime_td_probability, anytime_td_rate
from app.core.nfl_snap_share import (
    SNAP_SHARE_BLEND_WEIGHT,
    SNAP_SHARE_COEFFICIENTS,
    NflSnapCoefficients,
    NflSnapEvidence,
    NflSnapSeason,
    production_anytime_td_probability,
    recent_snap_share,
    season_snap_share,
    snap_evidence,
    snap_td_probability,
)

COEFFICIENTS = NflSnapCoefficients(intercept=0.05, per_share=0.40)


def test_a_zero_blend_weight_reproduces_the_production_rate_unrounded() -> None:
    seasons = [NflSeasonTouchdowns(2025, 17, 0.6), NflSeasonTouchdowns(2026, 2, 1.0)]
    historical_rate, _ = anytime_td_rate(seasons, 2026, 0.3)

    assert snap_td_probability(historical_rate, 0.95, COEFFICIENTS, 0.0) == 1 - exp(-historical_rate)


def test_a_higher_share_raises_the_probability() -> None:
    assert snap_td_probability(0.3, 0.8, COEFFICIENTS, 0.5) > snap_td_probability(0.3, 0.3, COEFFICIENTS, 0.5)


def test_the_blend_is_linear_in_rate_before_the_poisson_step() -> None:
    # Half history (0.3) and half the snap model (0.05 + 0.40 * 0.5 = 0.25).
    assert snap_td_probability(0.3, 0.5, COEFFICIENTS, 0.5) == pytest.approx(1 - exp(-0.275))


def test_no_snap_history_falls_back_to_the_position_share() -> None:
    assert season_snap_share([], 2026, 0.45) == (pytest.approx(0.45), 0.0)
    assert recent_snap_share([], 0.45) == (pytest.approx(0.45), 0)


def test_season_share_weights_recent_seasons_and_shrinks_toward_the_position() -> None:
    seasons = [NflSnapSeason(2025, 10, 0.8), NflSnapSeason(2026, 5, 0.4), NflSnapSeason(2022, 17, 1.0)]

    share, weighted_games = season_snap_share(seasons, 2026, 0.5, prior_games=10.0)

    # 2026 weight 1.0 * 5 games, 2025 weight 0.6 * 10 games, 2022 is outside the window.
    assert weighted_games == pytest.approx(11.0)
    assert share == pytest.approx((10 * 0.5 + 5 * 0.4 + 6 * 0.8) / 21)


def test_both_forms_default_to_the_light_snap_prior() -> None:
    # Four games at 0.9 against a 0.3 position: (2 * 0.3 + 4 * 0.9) / 6.
    assert recent_snap_share([0.9, 0.9, 0.9, 0.9], 0.3)[0] == pytest.approx(0.7)
    assert season_snap_share([NflSnapSeason(2026, 4, 0.9)], 2026, 0.3)[0] == pytest.approx(0.7)


def test_seasons_without_snap_games_contribute_no_evidence() -> None:
    assert season_snap_share([NflSnapSeason(2026, 0, 0.9)], 2026, 0.5) == (pytest.approx(0.5), 0.0)


def test_recent_share_uses_only_the_latest_window_of_games() -> None:
    share, games = recent_snap_share([1.0, 1.0, 0.2, 0.4, 0.6, 0.8], 0.5, window=4, prior_games=2.0)

    assert games == 4
    assert share == pytest.approx((2 * 0.5 + 0.2 + 0.4 + 0.6 + 0.8) / 6)


def test_out_of_range_and_non_finite_shares_are_clamped() -> None:
    share, _ = recent_snap_share([-0.5, 1.7, nan, inf], 0.5, prior_games=0.0)

    # Out of range clamps to [0, 1]; non-finite (including inf) counts as 0, like red-zone inputs.
    assert share == pytest.approx((0.0 + 1.0 + 0.0 + 0.0) / 4)
    assert snap_td_probability(0.3, 5.0, COEFFICIENTS, 1.0) == pytest.approx(1 - exp(-0.45))
    assert snap_td_probability(0.3, nan, COEFFICIENTS, 1.0) == pytest.approx(1 - exp(-0.05))


def test_negative_or_non_finite_rates_and_weights_are_clamped() -> None:
    assert snap_td_probability(-1.0, 0.5, NflSnapCoefficients(-2.0, 0.0), 0.5) == 0.0
    assert snap_td_probability(0.3, 0.5, COEFFICIENTS, nan) == pytest.approx(1 - exp(-0.3))
    assert snap_td_probability(0.3, 0.5, COEFFICIENTS, 3.0) == pytest.approx(1 - exp(-0.25))


def test_production_probability_is_the_backtested_blend_rounded() -> None:
    td = [NflSeasonTouchdowns(2025, 16, 0.5)]
    snaps = [NflSnapSeason(2025, 16, 0.7)]
    rate, weighted = anytime_td_rate(td, 2026, 0.25)
    share, _ = season_snap_share(snaps, 2026, 0.4)

    probability, games = production_anytime_td_probability("RB", td, snaps, 2026, 0.25, 0.4)

    expected = snap_td_probability(rate, share, SNAP_SHARE_COEFFICIENTS["RB"], SNAP_SHARE_BLEND_WEIGHT)
    assert (probability, games) == (round(expected, 2), round(weighted, 2))


def test_production_probability_leaves_other_positions_on_the_baseline() -> None:
    td, snaps = [NflSeasonTouchdowns(2025, 16, 0.5)], [NflSnapSeason(2025, 16, 0.95)]

    for position in ("QB", "WR", None):
        assert production_anytime_td_probability(position, td, snaps, 2026, 0.25, 0.4) == anytime_td_probability(
            td, 2026, 0.25,
        )


def test_snap_evidence_counts_only_games_inside_the_recency_weights() -> None:
    evidence = snap_evidence([NflSnapSeason(2022, 17, 1.0), NflSnapSeason(2025, 12, 0.8)], 2026, 0.4)

    assert evidence.games == 12
    assert evidence.share == pytest.approx(season_snap_share([NflSnapSeason(2025, 12, 0.8)], 2026, 0.4)[0])
    assert snap_evidence([NflSnapSeason(2022, 17, 1.0)], 2026, 0.4) == NflSnapEvidence(None, 0)
