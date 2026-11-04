"""Pre-registered rule for NHL P(over) from the reference projection (item 56c2).

Everything here is fixed in its own commit before any NHL family is fitted or
scored, so a later reader can show the rule preceded the data. NHL keeps its own
constants: a change to NBA's or NFL's rule must never move this one.

Selection (2024-25 development season, free to rerun): each candidate family is
cross-fitted by ISO-week parity of the game date at 20g1's synthetic x.5 lines. A
family is eligible only if it passes the display rule there; the eligible family
with the lower Brier is selected, an exact tie going to the earlier one in
`CANDIDATE_ORDER`. A market with no eligible family is hidden and never touches
the holdout.

Confirmation (2025-26 holdout, read once): the selected family and parameters,
fitted on all of 2024-25, scored under the same display rule. A market that
passes is shown; the rest are hidden until a new version is pre-registered.

Pure: no DB, no I/O.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.core.nfl_over_probability_calibration import CalibrationReport
from app.core.nhl_projection_backtest import DEVELOPMENT_SEASON, HOLDOUT_SEASON, NHL_PROJECTION_REFERENCE_VERSION
from app.nhl.markets import NhlLineOnlyMarket

NHL_PROJECTION_MODEL_VERSION = NHL_PROJECTION_REFERENCE_VERSION
NHL_OVER_PROBABILITY_VERSION = "nhl-pover-v1"

FIT_SEASON = DEVELOPMENT_SEASON
CONFIRMATION_SEASON = HOLDOUT_SEASON

Family = Literal["negbin", "scaled_normal", "ratio"]
# Tie-break order: the earlier family wins an exact Brier tie.
CANDIDATE_ORDER: tuple[Family, ...] = ("negbin", "scaled_normal", "ratio")

# A family reads only the stats it can represent: a negative binomial needs a non-negative
# count, and a ratio needs a positive projection. Plus/Minus is signed and Time On Ice is minutes.
FAMILY_EXCLUDED_MARKETS: dict[Family, frozenset[NhlLineOnlyMarket]] = {
    "negbin": frozenset({NhlLineOnlyMarket.PLUS_MINUS, NhlLineOnlyMarket.TIME_ON_ICE}),
    "scaled_normal": frozenset(),
    "ratio": frozenset({NhlLineOnlyMarket.PLUS_MINUS}),
}

# NBA's 20g1 values and 27g's before them, held as NHL's own.
MIN_CASES = 300
MAX_ECE = 0.02
MAX_BIN_GAP = 0.05
MIN_BIN_PAIRS = 200

NhlDisplayVerdict = Literal["show", "hide", "insufficient"]

RULE_TEXT = (
    "Show a market only if its selected family has >= 300 cases, ECE <= 0.02, every bin of >= 200 pairs within "
    "0.05 of its observed rate, and a Brier no worse than the constant-sigma normal's. The family is selected "
    "on 2024-25 by ISO-week-parity cross-fit and confirmed once on 2025-26."
)


@dataclass(frozen=True)
class CandidateResult:
    family: Family
    cases: int
    brier: float
    verdict: NhlDisplayVerdict


def family_applies(family: Family, market: NhlLineOnlyMarket) -> bool:
    return market not in FAMILY_EXCLUDED_MARKETS[family]


def parity(game_date: dt.date) -> int:
    """Which half of the season a game belongs to for the cross-fit: its ISO week, even or odd."""
    return game_date.isocalendar().week % 2


def nhl_display_verdict(cases_n: int, report: CalibrationReport, normal_brier: float) -> NhlDisplayVerdict:
    if cases_n < MIN_CASES:
        return "insufficient"
    # Recomputed from the bins so NHL's minimum bin size governs, not the one `calibrate` was built with.
    large_gaps = [b.gap for b in report.bins if b.n >= MIN_BIN_PAIRS]
    calibrated = report.ece <= MAX_ECE and all(gap <= MAX_BIN_GAP for gap in large_gaps)
    return "show" if calibrated and report.brier <= normal_brier else "hide"


def select_family(results: Sequence[CandidateResult]) -> Family | None:
    """The eligible family with the lowest Brier, ties to candidate order; None means the market is hidden."""
    eligible = [result for result in results if result.verdict == "show"]
    if not eligible:
        return None
    return min(eligible, key=lambda result: (result.brier, CANDIDATE_ORDER.index(result.family))).family
