"""Odds conversion and devig utilities."""
from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Optional, TypeVar

# The odds job refreshes hourly, so a healthy line is under an hour old. Six
# hours is wide enough that an ordinary skipped or delayed run never trips the
# flag, and narrow enough to catch a job that has actually stopped. It is a
# liveness check on the ingest, not a judgement about how fast a market moves.
STALE_ODDS_HOURS = 6.0


def odds_are_stale(
    fetched_at: Optional[dt.datetime],
    now: Optional[dt.datetime] = None,
    max_age_hours: float = STALE_ODDS_HOURS,
) -> bool:
    """Whether an odds row is too old to weight as a live market.

    `now` is injectable so tests assert against a fixed clock rather than
    wall time. A missing timestamp returns False: absent odds are already
    reported as `market_missing`, and guessing staleness on top would halve the
    weight of a market that may be perfectly current.
    """
    if fetched_at is None:
        return False
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=dt.timezone.utc)
    reference = now or dt.datetime.now(dt.timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=dt.timezone.utc)
    # A clock skew that puts the fetch in the future is not staleness.
    age_hours = (reference - fetched_at).total_seconds() / 3600.0
    return age_hours > max_age_hours


def american_to_prob(odds: int) -> float:
    """Convert American odds to implied probability."""
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)


def prob_to_american(p: float) -> int:
    """Convert probability to American odds."""
    p = max(1e-6, min(0.999999, p))
    if p >= 0.5:
        return int(round(-100 * p / (1 - p)))
    return int(round(100 * (1 - p) / p))


def devig_two_way(p1_raw: float, p2_raw: float) -> tuple[float, float]:
    """Remove vig from two-way market — normalize raw probs to sum to 1."""
    total = p1_raw + p2_raw
    if total <= 0:
        return 0.5, 0.5
    return p1_raw / total, p2_raw / total


def overround(p1_raw: float, p2_raw: float) -> float:
    """Return market overround as a fraction (e.g. 0.05 = 5%)."""
    return (p1_raw + p2_raw) - 1.0


# FanDuel's alternate lines carry almost no margin at the extremes (20.5 at -50000
# on a 47.5 NFL total, 2026-10-27), so least-vig alone picks one of them.
MAX_MAIN_LINE_PROBABILITY = 0.75

_Rung = TypeVar("_Rung")


def near_even_rungs(rungs: list[_Rung], prices: Callable[[_Rung], tuple[float, float]]) -> list[_Rung]:
    """Ladder rungs (decimal prices) with neither side above the main-line ceiling; all rungs when none qualify."""
    near = [rung for rung in rungs if max(1 / price for price in prices(rung)) <= MAX_MAIN_LINE_PROBABILITY]
    return near or rungs


def implied_prob_from_american(p1_odds: int, p2_odds: int) -> tuple[float, float]:
    """Get no-vig probabilities from a two-way American odds pair."""
    return devig_two_way(american_to_prob(p1_odds), american_to_prob(p2_odds))


def american_to_decimal(odds: int) -> float:
    """Convert American odds to decimal odds."""
    if odds >= 0:
        return 1.0 + odds / 100.0
    return 1.0 + 100.0 / abs(odds)


def decimal_to_american(dec: float) -> int:
    """Convert decimal odds to American odds."""
    if dec >= 2.0:
        return round((dec - 1) * 100)
    if dec <= 1.0:
        return -10000
    return round(-100 / (dec - 1))
