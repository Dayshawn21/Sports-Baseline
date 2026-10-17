"""The 27g P(over) fit's display table, per market, as recorded when the served tables were fitted.

Copied from `blueprint/history/features/27g-over-probability.md` (Step 4, run
2026-09-26 on the 2025 replay, cross-fitted by week parity). Re-running the fit
takes about 15 minutes and reads the 2025 holdout again, so the track record
page shows this record instead. Tests pin it to `nfl_over_probability_fit`, so
regenerating that module fails until this table is updated from the new run.

Pure constants: no DB, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FIT_SEASON = 2025
FIT_PROJECTION_MODEL_VERSION = "opponent-dvp-tg-blend-usage-snap-v4"


@dataclass(frozen=True)
class FitMarketRow:
    market: str
    cases: int
    pairs: int
    ece: float
    worst_gap: float | None
    brier: float
    normal_brier: float
    verdict: Literal["show", "hide"]
    # At the synthetic line nearest the projection: the OVER lean as a probability.
    at_projection_predicted: float
    at_projection_observed: float


FIT_MARKETS: tuple[FitMarketRow, ...] = (
    FitMarketRow("receiving_yards", 4549, 21857, 0.010, 0.014, 0.2248, 0.2326, "show", 0.380, 0.381),
    FitMarketRow("rushing_yards", 1892, 9000, 0.009, 0.038, 0.2232, 0.2261, "show", 0.390, 0.393),
    FitMarketRow("fantasy_points", 5235, 23013, 0.015, 0.068, 0.2164, 0.2209, "hide", 0.402, 0.404),
    FitMarketRow("receptions", 4570, 14352, 0.031, 0.052, 0.2045, 0.2084, "hide", 0.404, 0.415),
    FitMarketRow("rushing_attempts", 1360, 5781, 0.027, 0.053, 0.2050, 0.2000, "hide", 0.414, 0.419),
    FitMarketRow("passing_yards", 582, 2906, 0.013, 0.047, 0.1768, 0.1691, "hide", 0.495, 0.497),
    FitMarketRow("passing_attempts", 582, 2873, 0.013, 0.017, 0.1574, 0.1496, "hide", 0.463, 0.466),
    FitMarketRow("passing_completions", 582, 2865, 0.019, 0.023, 0.1573, 0.1515, "hide", 0.482, 0.488),
)
