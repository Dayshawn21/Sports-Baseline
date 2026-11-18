import pytest

from app.core.odds_api_io_quota import HOURLY_ALLOWANCE, can_request, remaining_requests


@pytest.mark.parametrize(("value", "expected"), [
    ("0", 0), ("21", 21), (str(HOURLY_ALLOWANCE), HOURLY_ALLOWANCE), (" 7 ", 7),
])
def test_a_readable_balance_within_the_allowance_is_kept(value: str, expected: int) -> None:
    assert remaining_requests({"x-ratelimit-remaining": value}) == expected


def test_a_missing_header_is_unknown() -> None:
    assert remaining_requests({}) is None


@pytest.mark.parametrize("value", ["", "bad", "12.5", "none"])
def test_a_malformed_header_is_unknown(value: str) -> None:
    assert remaining_requests({"x-ratelimit-remaining": value}) is None


@pytest.mark.parametrize("value", ["-1", str(HOURLY_ALLOWANCE + 1), "500"])
def test_a_balance_outside_the_hourly_allowance_is_unknown(value: str) -> None:
    assert remaining_requests({"x-ratelimit-remaining": value}) is None


def test_a_request_needs_the_balance_above_the_floor() -> None:
    assert can_request(21, 20)
    assert not can_request(20, 20)
    assert not can_request(19, 20)


def test_an_unknown_balance_never_requests() -> None:
    assert not can_request(None, 0)


def test_a_negative_floor_counts_as_zero() -> None:
    assert can_request(1, -5)
    assert not can_request(0, -5)
