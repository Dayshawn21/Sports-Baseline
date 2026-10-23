"""Pre-registered rules for NBA P(over) v2 (item 44a).

Committed before any 2024-25 fit was run. After that commit, changing the target
markets, candidate order, selection rule or confirmation rule needs a new version
and a recorded reason.

- **Selection (44a, 2024-25 only):** each candidate family is cross-fitted by
  ISO-week parity (fit on one half, score the other, both ways, pooled) at
  20g1's synthetic x.5 lines. A family is eligible only if it passes the
  display rule there; the eligible family with the lower Brier is picked, an
  exact tie going to the earlier one in `CANDIDATE_ORDER`. A market with no
  eligible family is not carried to 44b.
- **Confirmation (44b, once):** the selected family and parameters, fitted on
  all of 2024-25 and frozen by 44a, scored on 2026-27 regular-season weeks 1-4
  once every game in them is final with box scores loaded, under the same
  display rule. 2025-26 was already read twice (20f, 20g1) and is not used.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

# Imported, not copied: the display rule is 20g1's, unchanged.
from app.core.nba_over_probability import MAX_BIN_GAP, MAX_ECE, MIN_BIN_PAIRS, MIN_CASES, NbaDisplayVerdict
from app.core.nba_projection_backtest import DEVELOPMENT_SEASON, NbaReplayCase
from app.nba.markets import NbaPropMarket

NBA_OVER_PROBABILITY_V2_VERSION = "nba-pover-v2"

Family = Literal["negbin", "scaled_normal"]
CANDIDATE_ORDER: tuple[Family, ...] = ("negbin", "scaled_normal")

# The eight markets 20g1 hid; assists stays on nba-pover-v1.
TARGET_MARKETS: tuple[str, ...] = (
    NbaPropMarket.POINTS,
    NbaPropMarket.REBOUNDS,
    NbaPropMarket.THREES_MADE,
    NbaPropMarket.BLOCKS,
    NbaPropMarket.POINTS_REBOUNDS_ASSISTS,
    NbaPropMarket.POINTS_REBOUNDS,
    NbaPropMarket.POINTS_ASSISTS,
    NbaPropMarket.REBOUNDS_ASSISTS,
)

FIT_SEASON = DEVELOPMENT_SEASON
CONFIRMATION_SEASON = 2026
CONFIRMATION_WEEKS: tuple[int, ...] = (1, 2, 3, 4)

DISPLAY_RULE = (MIN_CASES, MAX_ECE, MAX_BIN_GAP, MIN_BIN_PAIRS)


@dataclass(frozen=True)
class CandidateResult:
    family: Family
    cases: int
    brier: float
    verdict: NbaDisplayVerdict


def parity(case: NbaReplayCase) -> int:
    return case.game_date.isocalendar().week % 2


def split_by_parity(cases: Iterable[NbaReplayCase]) -> tuple[list[NbaReplayCase], list[NbaReplayCase]]:
    """(even ISO weeks, odd ISO weeks)."""
    halves: tuple[list[NbaReplayCase], list[NbaReplayCase]] = ([], [])
    for case in cases:
        halves[parity(case)].append(case)
    return halves


def select_family(results: Sequence[CandidateResult]) -> Family | None:
    """The eligible family with the lowest Brier, ties to candidate order; None means not carried."""
    eligible = [result for result in results if result.verdict == "show"]
    if not eligible:
        return None
    return min(eligible, key=lambda result: (result.brier, CANDIDATE_ORDER.index(result.family))).family
