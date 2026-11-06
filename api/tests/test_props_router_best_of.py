"""The router must apply the linked match's format, and refuse to guess sets.

Covers the two behaviors a men's Slam slate depends on: length-derived stats
scale up on best-of-5, and set-count stats are suppressed rather than projected
off a best-of-3 formula.
"""

import pytest

from tests.helpers.props_router_best_of import _enriched


@pytest.mark.parametrize("stat,line", [
    ("Total Games", "22.5"),
    ("Aces", "6.5"),
    ("Total Games Won", "11.5"),
    ("Fantasy Score", "25.5"),
])
def test_best_of_five_projects_higher_than_best_of_three(stat, line):
    bo3 = _enriched(stat, line, 3)
    bo5 = _enriched(stat, line, 5)
    assert bo3.stat_avg is not None and bo5.stat_avg is not None
    assert bo5.stat_avg > bo3.stat_avg, f"{stat} ignored best_of"


def test_total_games_scales_by_roughly_the_bo5_factor():
    bo3 = _enriched("Total Games", "22.5", 3)
    bo5 = _enriched("Total Games", "22.5", 5)
    assert bo5.stat_avg / bo3.stat_avg == pytest.approx(30.45 / 22.29, rel=1e-3)


def test_an_unlinked_prop_falls_back_to_best_of_three():
    # None means "no linked match", not "best-of-3", but the projection has to
    # pick something and 3 preserves the previous behavior.
    assert _enriched("Total Games", "22.5", None).stat_avg == pytest.approx(
        _enriched("Total Games", "22.5", 3).stat_avg
    )


@pytest.mark.parametrize("stat", ["Total Sets", "Total Tie Breaks"])
def test_set_count_stats_are_suppressed_on_best_of_five(stat):
    enriched = _enriched(stat, "3.5", 5)
    assert "bo5_unsupported_stat" in enriched.data_quality_flags
    # In hard_blocks, so nothing actionable surfaces off a best-of-3 set formula.
    assert enriched.recommendation is None
    assert enriched.confidence is None


@pytest.mark.parametrize("stat", ["Total Sets", "Total Tie Breaks"])
def test_set_count_stats_are_untouched_on_best_of_three(stat):
    enriched = _enriched(stat, "2.5", 3)
    assert "bo5_unsupported_stat" not in enriched.data_quality_flags


def test_length_derived_stats_are_not_suppressed_on_best_of_five():
    # Only the set-count stats are blocked; the ones this fix repaired must
    # still be playable.
    enriched = _enriched("Total Games", "22.5", 5)
    assert "bo5_unsupported_stat" not in enriched.data_quality_flags
    assert enriched.recommendation is not None
