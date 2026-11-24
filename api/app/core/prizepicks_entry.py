"""PrizePicks power and flex entry EV from per-leg hit probabilities.

Pure math for the /tools calculator; `web/src/utils/prizepicksEntry.ts` is a
port held to the same cases in `tests/fixtures/calculator_cases.json`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EntryKind = Literal["power", "flex"]

MIN_LEGS = 2
MAX_LEGS = 6

# Standard (non-goblin, non-demon) payout multiples, checked 2026-11-11.
# PrizePicks retunes these; a change here flows to the API tests and, through
# the fixture, to the web port.
POWER_PAYOUTS: dict[int, float] = {2: 3.0, 3: 6.0, 4: 10.0, 5: 20.0, 6: 37.5}
FLEX_PAYOUTS: dict[int, dict[int, float]] = {
    3: {3: 3.0, 2: 1.0},
    4: {4: 6.0, 3: 1.5},
    5: {5: 10.0, 4: 2.0, 3: 0.4},
    6: {6: 25.0, 5: 2.0, 4: 0.4},
}


@dataclass(frozen=True)
class EntryResult:
    distribution: list[float]
    """P(exactly k legs hit), indexed by k."""
    expected_multiple: float
    ev: float
    """Expected return per unit entered: expected_multiple - 1."""


def hit_count_distribution(probs: list[float]) -> list[float]:
    """Exact Poisson-binomial distribution: legs need not share a hit rate."""
    dist = [1.0]
    for p in probs:
        nxt = [0.0] * (len(dist) + 1)
        for hits, mass in enumerate(dist):
            nxt[hits] += mass * (1.0 - p)
            nxt[hits + 1] += mass * p
        dist = nxt
    return dist


def payout_table(kind: EntryKind, legs: int) -> dict[int, float]:
    """Payout multiple by hit count; raises ValueError for an entry PrizePicks does not offer."""
    if not MIN_LEGS <= legs <= MAX_LEGS:
        raise ValueError(f"an entry has {MIN_LEGS} to {MAX_LEGS} legs, not {legs}")
    if kind == "power":
        return {legs: POWER_PAYOUTS[legs]}
    if kind == "flex":
        if legs not in FLEX_PAYOUTS:
            raise ValueError(f"flex needs at least 3 legs, not {legs}")
        return FLEX_PAYOUTS[legs]
    raise ValueError(f"unknown entry kind {kind!r}")


def entry_ev(probs: list[float], kind: EntryKind) -> EntryResult:
    table = payout_table(kind, len(probs))
    if any(not 0.0 <= p <= 1.0 for p in probs):
        raise ValueError("leg probabilities must be between 0 and 1")
    dist = hit_count_distribution(probs)
    expected = sum(dist[hits] * multiple for hits, multiple in table.items())
    return EntryResult(distribution=dist, expected_multiple=expected, ev=expected - 1.0)
