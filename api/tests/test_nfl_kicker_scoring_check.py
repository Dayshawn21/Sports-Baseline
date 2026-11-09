import pytest

from app.core.nfl_kicker_scoring_check import (
    ANCHOR_OVER_RATE,
    CONSISTENT_Z,
    DECISION_THROUGH_WEEK,
    MIN_MATCHED,
    MatchedKick,
    candidate_read,
    kicker_scoring_verdict,
    residual,
)
from app.core.nfl_kicking import CANDIDATE_FORMULAS, FLAT_KICKING, KICKING_DISTANCE_COLUMNS, KickingFormula, kicking_points

DISTANCE = next(f for f in CANDIDATE_FORMULAS if f.name == "distance_pat1_fgmiss0_patmiss0")


def _stats(i: int, *, pat_missed: int = 0) -> dict[str, int | None]:
    # Half the games have a 40-49 make, a third a 50+ make, half an FG miss.
    long_40 = i % 2
    long_50 = int(i % 3 == 0)
    short = 1 + i % 2
    return {
        **{column: 0 for column in KICKING_DISTANCE_COLUMNS},
        "fg_made": short + long_40 + long_50,
        "fg_made_30_39": short,
        "fg_made_40_49": long_40,
        "fg_made_50_59": long_50,
        "fg_missed_40_49": (i + 1) % 2,
        "pat_made": 2 + i % 3,
        "pat_missed": pat_missed,
    }


def _games(
    n: int, *, truth: KickingFormula = DISTANCE, noise: float = 0.25, offset: float = 0.0,
    anchor_shift: float | None = None, pat_misses: int = 0,
) -> list[MatchedKick]:
    games = []
    for i in range(n):
        stats = _stats(i, pat_missed=int(i < pat_misses))
        flat = kicking_points(FLAT_KICKING, stats)
        true = kicking_points(truth, stats)
        assert flat is not None and true is not None
        # Kicking lines straddle flat outcomes, so the anchor sits at 50% unless shifted.
        kicking_line = flat + (anchor_shift if anchor_shift is not None else (0.5 if i % 2 else -0.5))
        fantasy_line = kicking_line + (true - flat) + offset + (noise if i % 4 < 2 else -noise)
        games.append(MatchedKick(fantasy_line, kicking_line, stats))
    return games


def test_the_registered_constants() -> None:
    assert DECISION_THROUGH_WEEK == 8
    assert MIN_MATCHED == 60
    assert CONSISTENT_Z == 1.96
    assert ANCHOR_OVER_RATE == (0.35, 0.65)


def test_the_residual_is_the_line_gap_minus_what_the_formula_adds_over_flat() -> None:
    stats = _stats(3)  # a 40-49 and a 50+ make: distance adds 1 + 2 over flat
    game = MatchedKick(fantasy_line=11.5, kicking_line=8.5, stats=stats)
    assert residual(DISTANCE, game) == 0.0
    assert residual(FLAT_KICKING, game) == 3.0


def test_lines_built_under_distance_scoring_pin_it() -> None:
    result = kicker_scoring_verdict(_games(80, pat_misses=40))
    assert result.outcome == "pinned"
    assert result.pinned == DISTANCE
    assert result.unresolved_terms == ()
    assert [read.formula for read in result.reads if read.consistent] == [DISTANCE]


def test_a_constant_offset_no_candidate_explains_is_unresolved() -> None:
    result = kicker_scoring_verdict(_games(80, offset=2.0))
    assert result.outcome == "unresolved"
    assert result.pinned is None


def test_fewer_than_the_minimum_is_insufficient_even_with_a_broken_anchor() -> None:
    assert kicker_scoring_verdict(_games(MIN_MATCHED - 1)).outcome == "insufficient"
    assert kicker_scoring_verdict(_games(MIN_MATCHED - 1, anchor_shift=-3.0)).outcome == "insufficient"
    assert kicker_scoring_verdict(_games(MIN_MATCHED)).outcome == "pinned"


def test_kicking_lines_far_below_flat_outcomes_break_the_anchor() -> None:
    result = kicker_scoring_verdict(_games(80, anchor_shift=-3.0))
    assert result.outcome == "anchor_broken"
    assert result.anchor_over_rate == 1.0


def test_an_anchor_with_only_pushes_is_broken() -> None:
    result = kicker_scoring_verdict(_games(80, anchor_shift=0.0))
    assert result.anchor_over_rate is None
    assert result.outcome == "anchor_broken"


def test_two_consistent_candidates_pin_fewer_penalties_and_name_the_differing_term() -> None:
    # Two PAT misses in 80 games shift the PAT-miss candidate by 0.025, inside its noise.
    result = kicker_scoring_verdict(_games(80, noise=1.0, pat_misses=2))
    consistent = {read.formula.name for read in result.reads if read.consistent}
    assert consistent == {"distance_pat1_fgmiss0_patmiss0", "distance_pat1_fgmiss0_patmiss1"}
    assert result.outcome == "pinned"
    assert result.pinned == DISTANCE
    assert [term.term for term in result.unresolved_terms] == ["pat_miss_points"]
    assert result.unresolved_terms[0].average_effect == pytest.approx(-2 / 80)


def test_a_sample_with_no_pat_misses_cannot_resolve_the_pat_miss_penalty() -> None:
    result = kicker_scoring_verdict(_games(80))
    assert result.pinned == DISTANCE
    assert [(term.term, term.average_effect) for term in result.unresolved_terms] == [("pat_miss_points", 0.0)]


def test_identical_residuals_give_a_zero_standard_error() -> None:
    stats = _stats(3) | {"fg_missed_40_49": 1, "pat_missed": 1}
    flat = kicking_points(FLAT_KICKING, stats)
    true = kicking_points(DISTANCE, stats)
    assert flat is not None and true is not None
    games = [MatchedKick(flat + 0.5 * s + true - flat, flat + 0.5 * s, stats) for s in (1, -1) * 40]
    assert candidate_read(DISTANCE, games).standard_error == 0.0
    result = kicker_scoring_verdict(games)
    assert result.outcome == "pinned"
    assert result.pinned == DISTANCE
    assert result.unresolved_terms == ()


def test_a_single_game_has_no_standard_error_and_is_never_consistent() -> None:
    read = candidate_read(DISTANCE, _games(1))
    assert read.standard_error is None
    assert not read.consistent


def test_a_game_missing_a_column_a_candidate_reads_is_an_error() -> None:
    game = MatchedKick(9.5, 8.5, _stats(0) | {"fg_made_50_59": None})
    with pytest.raises(ValueError):
        residual(DISTANCE, game)
