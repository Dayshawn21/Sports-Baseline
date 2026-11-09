import pytest

from app.core.nfl_kicking import (
    CANDIDATE_FORMULAS,
    FLAT_KICKING,
    KICKING_DISTANCE_BANDS,
    KICKING_DISTANCE_COLUMNS,
    KickingFormula,
    PRIZEPICKS_KICKING_FORMULA,
    kicking_points,
)
from app.core.nfl_line_only import line_only_value
from app.nfl.markets import NflLineOnlyMarket

ZERO_ROW: dict[str, int | None] = {"fg_made": 0, "pat_made": 0, **{column: 0 for column in KICKING_DISTANCE_COLUMNS}}
# One make in every band (3+3+3+4+5+5 = 23 by distance), 3 PATs, one FG miss and one PAT miss.
ROW: dict[str, int | None] = {
    **ZERO_ROW,
    "fg_made": 6,
    "pat_made": 3,
    **{f"fg_made_{band}": 1 for band in KICKING_DISTANCE_BANDS},
    "fg_missed_40_49": 1,
    "pat_missed": 1,
}
DISTANCE = KickingFormula("distance", True, 1, 0, 0)


@pytest.mark.parametrize(
    ("band", "points"), [("0_19", 3), ("20_29", 3), ("30_39", 3), ("40_49", 4), ("50_59", 5), ("60_", 5)],
)
def test_each_distance_band_scores_its_playbook_value(band: str, points: int) -> None:
    row = ZERO_ROW | {"fg_made": 1, f"fg_made_{band}": 1}
    assert kicking_points(DISTANCE, row) == points
    assert kicking_points(FLAT_KICKING, row) == 3


def test_flat_matches_kicking_points_settlement() -> None:
    for row in (ZERO_ROW, ROW, ZERO_ROW | {"fg_made": 4, "pat_made": 5}):
        assert kicking_points(FLAT_KICKING, row) == line_only_value(NflLineOnlyMarket.KICKING_POINTS, row)


@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        (DISTANCE, 26.0),
        (KickingFormula("no_pat", True, 0, 0, 0), 23.0),
        (KickingFormula("fg_miss", True, 1, -1, 0), 25.0),
        (KickingFormula("pat_miss", True, 1, 0, -1), 25.0),
        (KickingFormula("both", False, 1, -1, -1), 19.0),
    ],
)
def test_each_term_is_applied(formula: KickingFormula, expected: float) -> None:
    assert kicking_points(formula, ROW) == expected


def test_every_missed_band_counts_toward_the_fg_miss_penalty() -> None:
    row = ZERO_ROW | {f"fg_missed_{band}": 1 for band in KICKING_DISTANCE_BANDS}
    assert kicking_points(KickingFormula("fg_miss", False, 1, -1, 0), row) == -6.0


def test_a_null_band_is_unknown_only_for_formulas_that_read_it() -> None:
    row = ROW | {"fg_made_50_59": None}
    assert kicking_points(DISTANCE, row) is None
    assert kicking_points(FLAT_KICKING, row) == 21.0


def test_a_null_miss_column_is_unknown_only_with_its_penalty() -> None:
    row = ROW | {"pat_missed": None}
    assert kicking_points(DISTANCE, row) == 26.0
    assert kicking_points(KickingFormula("pat_miss", True, 1, 0, -1), row) is None


def test_the_grid_is_sixteen_named_candidates_including_the_anchor() -> None:
    names = [formula.name for formula in CANDIDATE_FORMULAS]
    assert len(names) == 16
    assert len(set(names)) == 16
    assert FLAT_KICKING in CANDIDATE_FORMULAS
    assert FLAT_KICKING.name == "flat_pat1_fgmiss0_patmiss0"
    assert "distance_pat1_fgmiss1_patmiss1" in names


def test_the_pinned_formula_is_the_registered_distance_candidate() -> None:
    assert PRIZEPICKS_KICKING_FORMULA in CANDIDATE_FORMULAS
    assert PRIZEPICKS_KICKING_FORMULA == KickingFormula("distance_pat1_fgmiss0_patmiss0", True, 1, 0, 0)
