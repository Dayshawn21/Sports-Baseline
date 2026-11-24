from datetime import date, timedelta

import pytest

from app.core.track_record import (
    TIER_BREAK_EVEN,
    TIER_MATURITY_DAYS,
    TIER_RULE_TIERS,
    TIER_RULE_VERSION,
    TIER_VERDICT_SAMPLE,
    loss_signal,
    rate_signal,
    tier_verdict,
    verdict_signal,
)
from app.services.tennis.prop_snapshots import PROJECTION_VERSION

AS_OF = date(2026, 10, 30)
MATURE = AS_OF - timedelta(days=TIER_MATURITY_DAYS)


def _day(offset: int) -> date:
    return MATURE - timedelta(days=offset)


def _picks(day: date, hits: int, misses: int) -> list[tuple[date, bool]]:
    return [(day, True)] * hits + [(day, False)] * misses


def test_rule_constants_are_pinned():
    # The tier record is props-v2 history; snapshots moved on without tiers (48f).
    assert (TIER_RULE_VERSION, PROJECTION_VERSION) == ("props-v2", "props-v3")
    assert TIER_RULE_TIERS == ("LOCK", "STRONG", "LEAN")
    assert TIER_VERDICT_SAMPLE == 200
    assert TIER_MATURITY_DAYS == 3
    assert TIER_BREAK_EVEN == pytest.approx(0.5774, abs=1e-4)


def test_loss_signal():
    assert loss_signal(-0.05, 0.01) == "positive"
    assert loss_signal(-0.2, 0.1) == "neutral"  # exactly 2 SE is not enough
    assert loss_signal(0.05, 0.01) == "neutral"  # worse than the market is never red
    assert loss_signal(-0.05, None) == "neutral"


def test_rate_signal():
    assert rate_signal(0.8, 0.05, 0.5) == "positive"
    assert rate_signal(0.2, 0.05, 0.5) == "negative"
    assert rate_signal(0.55, 0.05, 0.5) == "neutral"
    assert rate_signal(0.75, 0.125, 0.5) == "neutral"  # boundary, above
    assert rate_signal(0.25, 0.125, 0.5) == "neutral"  # boundary, below
    assert rate_signal(0.9, None, 0.5) == "neutral"


def test_accruing_below_the_sample():
    result = tier_verdict(_picks(_day(0), 150, 49), AS_OF)
    assert result.verdict == "accruing"
    assert result.sample_size == 199
    assert result.signal == "neutral"


def test_immature_day_is_ignored_until_three_days_old():
    picks = _picks(_day(1), 100, 50) + _picks(MATURE + timedelta(days=1), 100, 0)
    assert tier_verdict(picks, AS_OF).sample_size == 150
    later = tier_verdict(picks, AS_OF + timedelta(days=1))
    assert later.sample_size == 250
    assert later.verdict != "accruing"


def test_pass_takes_whole_days_past_the_sample():
    picks = _picks(_day(2), 150, 30) + _picks(_day(1), 40, 10)
    result = tier_verdict(picks, AS_OF)
    assert result.sample_size == 230
    assert result.verdict == "pass"
    assert result.signal == "positive"


def test_reject_below_break_even():
    result = tier_verdict(_picks(_day(0), 90, 110), AS_OF)
    assert result.verdict == "reject"
    assert result.signal == "negative"
    assert result.hit_rate == pytest.approx(0.45)


def test_reject_near_break_even_stays_neutral():
    result = tier_verdict(_picks(_day(0), 118, 82), AS_OF)
    assert result.verdict == "reject"
    assert result.signal == "neutral"


def test_later_days_never_change_the_verdict():
    first = _picks(_day(5), 90, 110)
    later = _picks(_day(1), 500, 0)
    assert tier_verdict(first, AS_OF) == tier_verdict(first + later, AS_OF)


def test_verdict_signal_stays_neutral_until_decided():
    assert verdict_signal(False, 0.90, 0.01, 0.577) == "neutral"
    assert verdict_signal(False, 0.10, 0.01, 0.577) == "neutral"
    assert verdict_signal(True, None, None, 0.577) == "neutral"


def test_verdict_signal_colors_a_decided_result_past_2_se():
    assert verdict_signal(True, 0.70, 0.05, 0.577) == "positive"
    assert verdict_signal(True, 0.45, 0.05, 0.577) == "negative"
    assert verdict_signal(True, 0.60, 0.05, 0.577) == "neutral"
    assert verdict_signal(True, 0.60, None, 0.577) == "neutral"
    assert verdict_signal(True, 0.42, 0.21, 0.0) == "neutral"  # exactly 2 SE is not enough
    assert verdict_signal(True, -0.43, 0.21, 0.0) == "negative"
