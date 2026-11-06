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


def test_a_reservation_fits_exactly_at_the_cap_and_recorded_spend_refuses():
    spend = DailySpend()
    spend.record(DAY, 0.75)
    assert spend.reserve(DAY, 0.25, 1.0) is not None
    spend = DailySpend()
    spend.record(DAY, 1.0)
    assert spend.reserve(DAY, 0.01, 1.0) is None


def test_questions_in_flight_fill_the_cap_before_any_cost_is_recorded():
    spend = DailySpend()
    first = spend.reserve(DAY, 0.4, 1.0)
    second = spend.reserve(DAY, 0.4, 1.0)
    assert first is not None and second is not None
    # Nothing is spent yet, but the two holds leave no room for a third.
    assert spend.spent(DAY) == 0.0
    assert spend.held(DAY) == pytest.approx(0.8)
    assert spend.reserve(DAY, 0.4, 1.0) is None


def test_settling_replaces_the_hold_with_the_real_cost():
    spend = DailySpend()
    first = spend.reserve(DAY, 0.4, 1.0)
    spend.reserve(DAY, 0.4, 1.0)
    assert first.settle(0.05) == pytest.approx(0.05)
    assert spend.spent(DAY) == pytest.approx(0.05)
    assert spend.held(DAY) == pytest.approx(0.4)
    assert spend.reserve(DAY, 0.4, 1.0) is not None


def test_a_reservation_settles_once():
    spend = DailySpend()
    reservation = spend.reserve(DAY, 0.4, 1.0)
    reservation.settle(0.05)
    reservation.release()
    reservation.settle(0.30)
    assert spend.spent(DAY) == pytest.approx(0.05)
    assert spend.held(DAY) == 0.0


def test_a_release_frees_the_hold_and_records_nothing():
    spend = DailySpend()
    spend.reserve(DAY, 0.4, 1.0).release()
    assert (spend.spent(DAY), spend.held(DAY)) == (0.0, 0.0)


def test_a_question_that_ran_past_midnight_leaves_the_new_day_alone():
    spend = DailySpend()
    late = spend.reserve(DAY, 0.4, 1.0)
    spend.reserve(NEXT_DAY, 0.3, 1.0)
    late.settle(0.05)
    assert spend.spent(NEXT_DAY) == 0.0
    assert spend.held(NEXT_DAY) == pytest.approx(0.3)


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
