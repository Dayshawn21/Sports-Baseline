import datetime as dt

import pytest

from app.core.rate_limits import RateRule
from app.rate_limit import retry_after_seconds
from app.services.ask.guardrails import DailySpend, question_retry_after

DAY = dt.date(2026, 10, 28)
NEXT_DAY = dt.date(2026, 10, 29)


def test_spend_accumulates_within_a_day():
    spend = DailySpend()
    assert spend.record(DAY, 0.25) == pytest.approx(0.25)
    assert spend.record(DAY, 0.10) == pytest.approx(0.35)
    assert spend.spent(DAY) == pytest.approx(0.35)


def test_a_new_utc_day_starts_from_zero():
    spend = DailySpend()
    spend.record(DAY, 0.90)
    assert spend.spent(NEXT_DAY) == 0.0
    assert spend.record(NEXT_DAY, 0.05) == pytest.approx(0.05)
    # The older day is dropped, not kept beside the new one.
    assert spend.spent(DAY) == 0.0


def test_nothing_spent_before_the_first_question():
    assert DailySpend().spent(DAY) == 0.0


def test_exhausted_flips_exactly_at_the_cap():
    spend = DailySpend()
    spend.record(DAY, 0.75)
    assert not spend.exhausted(DAY, 1.0)
    spend.record(DAY, 0.25)
    assert spend.exhausted(DAY, 1.0)


def test_the_twenty_first_question_waits_while_another_ip_does_not():
    for _ in range(20):
        assert question_retry_after("203.0.113.5", 20) is None
    wait = question_retry_after("203.0.113.5", 20)
    assert wait is not None and wait > 0
    assert question_retry_after("198.51.100.7", 20) is None


def test_the_daily_count_is_separate_from_the_per_minute_bucket():
    # Same client and same limiter storage, but its own scope: /ask's heavy
    # per-minute hits never use up the daily questions.
    for _ in range(10):
        retry_after_seconds("203.0.113.5", RateRule("10/minute", "/ask"))
    assert question_retry_after("203.0.113.5", 20) is None
