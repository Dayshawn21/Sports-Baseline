"""The router must apply the linked match's format, and refuse to guess sets.

Covers the two behaviors a men's Slam slate depends on: length-derived stats
scale up on best-of-5, and set-count stats are suppressed rather than projected
off a best-of-3 formula.
"""
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.repositories.players import PlayerRollingStats
from app.repositories.props import Prop
from app.routers.props import _enrich


def _stats(player_id: int = 1) -> PlayerRollingStats:
    return PlayerRollingStats(
        player_id=player_id, surface="Hard", stat_period="last_52w",
        split_type="overall", split_value="all",
        win_rate=0.62, svc_pts_won=0.65, ret_pts_won=0.38,
        aces_per_game=0.18, df_per_game=0.05, hold_pct=0.82, break_pct=0.24,
        matches_count=30, first_in_pct=0.62, first_won_pct=0.73,
        second_won_pct=0.52, dominance_ratio=1.08, computed_at=datetime.now(UTC),
        allowed_aces_per_sp=0.08, allowed_df_per_sp=0.05,
        allowed_first_in_pct=0.62, allowed_first_won_pct=0.70,
        allowed_second_won_pct=0.50, allowed_hold_pct=0.78,
        break_points_created_per_return_game=0.65,
        allowed_break_points_per_service_game=0.60,
    )


def _prop(stat_type: str, line: str, best_of: int | None) -> Prop:
    return Prop(
        id=1, player_id=1, player_name="Test Player", match_id=10,
        source="prizepicks", stat_type=stat_type, line=Decimal(line),
        odds_type=None,
        fetched_at=datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
        start_time=datetime(2026, 8, 30, 18, 0, tzinfo=UTC),
        surface="Hard", raw_json={"match_link_method": "player_start_time"},
        match_status="scheduled", best_of=best_of,
    )


def _enriched(stat_type: str, line: str, best_of: int | None):
    return _enrich(_prop(stat_type, line, best_of), _stats(), _stats(2), 0.55,
                   market_total_games=None)


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
