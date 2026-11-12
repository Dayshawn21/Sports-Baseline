"""Pre-registered rules for `nba-minutes-v1` (item 65), fixed before any score of it is read.

The development gate (65a) decides which markets 65b freezes; the forward rule
(65c) decides adoption. Both reuse 20f's verdict and constants by import, so no
second copy of the thresholds exists. Pure: no DB, no I/O, no clock.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from math import sqrt

from app.core.nba_minutes import NBA_MINUTES_MODEL_VERSION
from app.core.nba_projection_backtest import (
    MIN_PAIRED_CASES, NBA_PROJECTION_MODEL_VERSION, NbaVerdict, nba_adoption_verdict,
)
from app.core.nfl_projection_backtest import PairedDiff

CANDIDATE_VERSION = NBA_MINUTES_MODEL_VERSION
COMPARISON_VERSION = NBA_PROJECTION_MODEL_VERSION
# k is fitted on 2023-24 only and the gate scores 2024-25 once; 2025-26 is the holdout, never read.
FIT_SEASON = 2023
DEVELOPMENT_SEASON = 2024
# A suspended player cannot play; Day-To-Day stays available (65a Step 1 status list).
OUT_STATUSES = frozenset({"Out", "Suspension"})
# Below this the two versions differ by under a minute of play, which is noise, not a rotation change.
AFFECTED_MINUTES = 1.0
FORWARD_MIN_PAIRS = MIN_PAIRED_CASES
FORWARD_MIN_DAYS = 28


def is_affected(minutes_change: float) -> bool:
    return abs(minutes_change) >= AFFECTED_MINUTES


def development_verdict(diff: PairedDiff) -> NbaVerdict:
    """65a's gate on one market's affected 2024-25 cases: 20f's rule unchanged."""
    return nba_adoption_verdict(diff)


@dataclass(frozen=True)
class ForwardPair:
    """One (player, game, market) with both versions frozen on the same line and settled."""

    game_id: int
    game_date: dt.date
    minutes_change: float
    candidate_error: float
    reference_error: float


def fixed_sample(
    pairs: Sequence[ForwardPair], first_freeze: dt.date, settled_through: dt.date,
) -> list[ForwardPair] | None:
    """The market's verdict sample, or None while it is still accruing.

    It runs from the first freeze through the Eastern date of the 300th affected pair,
    extended to at least 28 days, and closes only once every game to that date is settled.
    """
    affected = sorted(
        (p for p in pairs if is_affected(p.minutes_change) and p.game_date >= first_freeze),
        key=lambda p: p.game_date,
    )
    if len(affected) < FORWARD_MIN_PAIRS:
        return None
    end = max(affected[FORWARD_MIN_PAIRS - 1].game_date, first_freeze + dt.timedelta(days=FORWARD_MIN_DAYS - 1))
    if settled_through < end:
        return None
    return [p for p in affected if p.game_date <= end]


def clustered_paired_diff(pairs: Sequence[ForwardPair]) -> PairedDiff:
    """20f's paired difference with the standard error clustered by game.

    One absence moves every teammate's line in that game, so pairs within a game are
    not independent. CR1: sqrt(G / (G - 1) * sum over games of the summed deviations squared) / n.
    """
    if not pairs:
        raise ValueError("clustered_paired_diff needs at least one pair")
    n = len(pairs)
    diffs = [abs(p.candidate_error) - abs(p.reference_error) for p in pairs]
    mean_diff = sum(diffs) / n
    by_game: dict[int, float] = defaultdict(float)
    for pair, diff in zip(pairs, diffs, strict=True):
        by_game[pair.game_id] += diff - mean_diff
    games = len(by_game)
    spread = sum(total * total for total in by_game.values())
    standard_error = sqrt(games / (games - 1) * spread) / n if games > 1 else 0.0
    reference_mae = sum(abs(p.reference_error) for p in pairs) / n
    candidate_mae = sum(abs(p.candidate_error) for p in pairs) / n
    return PairedDiff(
        n=n, production_mae=reference_mae, variant_mae=candidate_mae, mean_diff=mean_diff,
        standard_error=standard_error,
        relative_mae_change=(candidate_mae - reference_mae) / reference_mae if reference_mae else 0.0,
    )


def forward_verdict(pairs: Sequence[ForwardPair], first_freeze: dt.date, settled_through: dt.date) -> NbaVerdict:
    """65c's verdict for one market; final for `nba-minutes-v1` once it is not `insufficient`."""
    sample = fixed_sample(pairs, first_freeze, settled_through)
    if sample is None:
        return "insufficient"
    return nba_adoption_verdict(clustered_paired_diff(sample))
