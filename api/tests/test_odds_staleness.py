"""Odds staleness must reach the ensemble's market downweight.

`odds_stale` existed as a build_features parameter and an ensemble branch for a
long time without anything ever passing it True, so the market weight was never
halved for a dead line. These tests pin the whole path.
"""
import datetime as dt

import pytest

from app.core.odds import STALE_ODDS_HOURS, odds_are_stale
from app.services.tennis.ensemble import EnsembleInput, hand_set_blend

NOW = dt.datetime(2026, 8, 30, 12, 0, tzinfo=dt.timezone.utc)


def _ago(hours: float) -> dt.datetime:
    return NOW - dt.timedelta(hours=hours)


@pytest.mark.parametrize("hours", [0.0, 0.5, 1.0, 3.0, STALE_ODDS_HOURS])
def test_fresh_odds_are_not_stale(hours):
    # The job runs hourly, so anything inside the threshold is normal operation.
    assert odds_are_stale(_ago(hours), NOW) is False


@pytest.mark.parametrize("hours", [STALE_ODDS_HOURS + 0.1, 12.0, 48.0])
def test_old_odds_are_stale(hours):
    assert odds_are_stale(_ago(hours), NOW) is True


def test_missing_timestamp_is_not_stale():
    # Absent odds already surface as market_missing. Calling that stale too
    # would halve the weight of a market that may be perfectly current.
    assert odds_are_stale(None, NOW) is False


def test_a_naive_timestamp_is_read_as_utc():
    naive = _ago(1.0).replace(tzinfo=None)
    assert odds_are_stale(naive, NOW) is False


def test_a_future_timestamp_is_not_stale():
    # Clock skew between the ingest host and the reader is not staleness.
    assert odds_are_stale(NOW + dt.timedelta(hours=2), NOW) is False


def test_threshold_is_overridable():
    assert odds_are_stale(_ago(2.0), NOW, max_age_hours=1.0) is True


def _blend(stale: bool):
    return hand_set_blend(EnsembleInput(
        tour="ATP", elo_prob=0.60, ml_prob=0.62, market_prob=0.55,
        market_stale=stale,
    ))


def test_stale_odds_flag_and_shrink_the_market_share():
    fresh, stale = _blend(False), _blend(True)
    assert "stale_odds" not in fresh.quality_flags
    assert "stale_odds" in stale.quality_flags
    # Weights are renormalized to sum to 1, so the halved market term shows up
    # as a smaller share rather than exactly half the previous number.
    assert stale.weights["market"] < fresh.weights["market"]
    assert sum(stale.weights.values()) == pytest.approx(1.0)


def test_stale_odds_move_the_blend_toward_the_model():
    # Downweighting must actually change the answer, or the flag is cosmetic.
    # Market is the low side here, so trusting it less lifts the blend.
    fresh, stale = _blend(False), _blend(True)
    assert stale.p1_win_prob > fresh.p1_win_prob
