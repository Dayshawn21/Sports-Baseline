"""best_of must reach every projection derived from match length.

The regression bar is that omitting best_of reproduces the old best-of-3 numbers
exactly, so the whole pre-existing suite passing unchanged is the proof.
"""
from datetime import UTC, datetime

import pytest

from app.core.prop_projection import (
    _downstream_total_games,
    compute_stat_avg,
    expected_break_point_chances,
    expected_service_points,
)
from app.repositories.players import PlayerRollingStats


def _stats(player_id: int = 1) -> PlayerRollingStats:
    return PlayerRollingStats(
        player_id=player_id,
        surface="Hard",
        stat_period="last_52w",
        split_type="overall",
        split_value="all",
        win_rate=0.62,
        svc_pts_won=0.65,
        ret_pts_won=0.38,
        aces_per_game=0.18,
        df_per_game=0.05,
        hold_pct=0.82,
        break_pct=0.24,
        matches_count=30,
        first_in_pct=0.62,
        first_won_pct=0.73,
        second_won_pct=0.52,
        dominance_ratio=1.08,
        computed_at=datetime.now(UTC),
        allowed_aces_per_sp=0.08,
        allowed_df_per_sp=0.05,
        allowed_first_in_pct=0.62,
        allowed_first_won_pct=0.70,
        allowed_second_won_pct=0.50,
        allowed_hold_pct=0.78,
        break_points_created_per_return_game=0.65,
        allowed_break_points_per_service_game=0.60,
    )


def _args():
    return _stats(), _stats(2), 0.55, None


LENGTH_DERIVED = (_downstream_total_games, expected_service_points, expected_break_point_chances)


@pytest.mark.parametrize("fn", LENGTH_DERIVED, ids=lambda f: f.__name__)
def test_best_of_five_projects_higher_than_best_of_three(fn):
    stats, opp, wp, mkt = _args()
    assert fn(stats, opp, wp, mkt, 5) > fn(stats, opp, wp, mkt, 3)


@pytest.mark.parametrize("fn", LENGTH_DERIVED, ids=lambda f: f.__name__)
def test_omitting_best_of_reproduces_best_of_three_exactly(fn):
    stats, opp, wp, mkt = _args()
    assert fn(stats, opp, wp, mkt) == fn(stats, opp, wp, mkt, 3)


@pytest.mark.parametrize("stat", ["aces", "double_faults", "break_points_won", "games_won"])
def test_compute_stat_avg_forwards_best_of_to_length_derived_stats(stat):
    # These branches all scale off match length. compute_stat_avg accepted
    # best_of long before this fix but only forwarded it to total_games, so
    # every one of these silently stayed best-of-3.
    stats, opp, wp, mkt = _args()
    bo3 = compute_stat_avg(stat, stats, opp, wp, "Hard", mkt, 3)
    bo5 = compute_stat_avg(stat, stats, opp, wp, "Hard", mkt, 5)
    assert bo3 is not None and bo5 is not None
    assert bo5 > bo3, f"{stat} did not scale with best_of"


def test_market_total_still_wins_over_the_format():
    # A book total is already the real match length, so best_of must not
    # re-scale it. This is the one path where BO3 and BO5 agree by design.
    stats, opp, wp, _ = _args()
    market = 30.5
    assert _downstream_total_games(stats, opp, wp, market, 5) == pytest.approx(
        _downstream_total_games(stats, opp, wp, market, 3)
    )


def test_total_games_scales_by_the_documented_bo5_factor():
    from app.core.tennis_props import _BEST_OF_5_TOTAL_SCALE

    stats, opp, wp, mkt = _args()
    ratio = _downstream_total_games(stats, opp, wp, mkt, 5) / _downstream_total_games(
        stats, opp, wp, mkt, 3
    )
    assert ratio == pytest.approx(_BEST_OF_5_TOTAL_SCALE)
