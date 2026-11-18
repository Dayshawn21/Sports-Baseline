"""Odds-API.io's hourly request balance, one rule for the tennis, NFL and NHL odds scripts.

The three scripts spend one shared hourly allowance, so a balance that cannot
be read stops a run instead of being taken as plenty.
"""
from __future__ import annotations

from collections.abc import Mapping

# The free plan's hourly allowance (45a, 48b). A header above it means the plan
# or the header changed, so it reads as unknown and stops every script until
# this constant is updated on purpose.
HOURLY_ALLOWANCE = 100
REMAINING_HEADER = "x-ratelimit-remaining"


def remaining_requests(headers: Mapping[str, str]) -> int | None:
    """Requests left this hour, or None when the header is missing, malformed or outside 0 to the allowance."""
    raw = headers.get(REMAINING_HEADER)
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if 0 <= value <= HOURLY_ALLOWANCE else None


def can_request(balance: int | None, floor: int) -> bool:
    """Whether one more request still leaves `floor` (never below 0); an unknown balance never can."""
    return balance is not None and balance - 1 >= max(0, floor)
