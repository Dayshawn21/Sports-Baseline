"""Kicking stats by distance (item 27l), named as in the NFLverse weekly stats file,
and the candidate kicker fantasy formulas 27l2 tests against PrizePicks' lines."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import product

KICKING_DISTANCE_BANDS = ("0_19", "20_29", "30_39", "40_49", "50_59", "60_")
KICKING_DISTANCE_COLUMNS: tuple[str, ...] = (
    *(f"fg_made_{band}" for band in KICKING_DISTANCE_BANDS),
    *(f"fg_missed_{band}" for band in KICKING_DISTANCE_BANDS),
    "pat_missed",
)

# PrizePicks' playbook bands (0-39, 40-49, 50+) over NFLverse's six.
_DISTANCE_FG_POINTS = {"0_19": 3, "20_29": 3, "30_39": 3, "40_49": 4, "50_59": 5, "60_": 5}
_FLAT_FG_POINTS = 3


@dataclass(frozen=True)
class KickingFormula:
    name: str
    fg_by_distance: bool
    pat_points: int
    fg_miss_points: int
    pat_miss_points: int


def _terms(formula: KickingFormula) -> tuple[tuple[str, int], ...]:
    # Zero-weight terms are left out, so a formula never goes None on a column it ignores.
    if formula.fg_by_distance:
        terms = [(f"fg_made_{band}", points) for band, points in _DISTANCE_FG_POINTS.items()]
    else:
        terms = [("fg_made", _FLAT_FG_POINTS)]
    terms.append(("pat_made", formula.pat_points))
    terms.extend((f"fg_missed_{band}", formula.fg_miss_points) for band in KICKING_DISTANCE_BANDS)
    terms.append(("pat_missed", formula.pat_miss_points))
    return tuple((column, weight) for column, weight in terms if weight)


def kicking_points(formula: KickingFormula, row: Mapping[str, int | None]) -> float | None:
    """A kicker's points under `formula`; None when any column it reads is NULL (not loaded)."""
    total = 0
    for column, weight in _terms(formula):
        value = row.get(column)
        if value is None:
            return None
        total += weight * value
    return float(total)


def _formula(fg_by_distance: bool, pat_points: int, fg_miss_points: int, pat_miss_points: int) -> KickingFormula:
    name = (
        f"{'distance' if fg_by_distance else 'flat'}_pat{pat_points}"
        f"_fgmiss{-fg_miss_points}_patmiss{-pat_miss_points}"
    )
    return KickingFormula(name, fg_by_distance, pat_points, fg_miss_points, pat_miss_points)


# The anchor: PrizePicks' kicking-points market, 3 per field goal and 1 per extra point.
FLAT_KICKING = _formula(False, 1, 0, 0)

# 27l2's pre-registered grid: FG scoring x PAT value x FG-miss penalty x PAT-miss penalty.
CANDIDATE_FORMULAS: tuple[KickingFormula, ...] = tuple(
    _formula(by_distance, pat, fg_miss, pat_miss)
    for by_distance, pat, fg_miss, pat_miss in product((False, True), (1, 0), (0, -1), (0, -1))
)
