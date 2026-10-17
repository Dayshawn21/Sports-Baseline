from dataclasses import replace

import pytest

from app.core.nfl_fantasy import NflFantasyComponents, nflverse_ppr_points, ppr_fantasy_points, prizepicks_fantasy_points


def test_ppr_scoring_formula_is_explicit() -> None:
    # 250/25 + 2*4 - 1*2 + 10/10 + 0 + 50/10 + 1*6 + 5 = 33.0
    assert ppr_fantasy_points(250, 2, 1, 10, 0, 50, 1, 5) == 33.0


def test_ppr_scoring_penalizes_interceptions() -> None:
    assert ppr_fantasy_points(0, 0, 2, 0, 0, 0, 0, 0) == -4.0


# Tua Tagovailoa, 2025 week 1, copied from stats_player_week_2025.csv:
# 2 interceptions, 1 lost sack fumble, 1 two-point pass. fantasy_points_ppr = 5.26.
_TUA_2025_WEEK_1 = NflFantasyComponents(
    passing_yards=114, passing_tds=1, interceptions=2, rushing_yards=7, receiving_yards=0,
    touchdowns=0, receptions=0, fumbles_lost=1, two_point_conversions=1, return_tds=0,
    fumble_recovery_tds=0,
)


def test_components_rebuild_nflverse_ppr_from_a_real_row() -> None:
    assert nflverse_ppr_points(_TUA_2025_WEEK_1) == 5.26


def test_prizepicks_charges_one_point_per_interception_and_lost_fumble() -> None:
    # 2 interceptions and 1 lost fumble: 3 points more than PPR's -2 each.
    assert prizepicks_fantasy_points(_TUA_2025_WEEK_1) == 8.26


def test_a_qb_week_with_one_interception_and_one_lost_fumble_scores_two_more_under_prizepicks() -> None:
    week = replace(_TUA_2025_WEEK_1, interceptions=1, fumbles_lost=1)

    assert prizepicks_fantasy_points(week) - nflverse_ppr_points(week) == pytest.approx(2.0)


def test_a_fumble_recovery_touchdown_counts_only_under_prizepicks() -> None:
    clean = replace(_TUA_2025_WEEK_1, interceptions=0, fumbles_lost=0)
    recovered = replace(clean, fumble_recovery_tds=1)

    assert prizepicks_fantasy_points(recovered) - prizepicks_fantasy_points(clean) == pytest.approx(6.0)
    assert nflverse_ppr_points(recovered) == nflverse_ppr_points(clean)
