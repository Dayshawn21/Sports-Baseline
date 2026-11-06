from datetime import datetime, timedelta
from decimal import Decimal
import asyncio

from app.core.poisson import over_under_push_probs
from app.core.rolling_stats import pick_stats_for_player
from app.repositories.matches import get_market_totals
from app.routers.props import (
    _compute_stat_avg,
    _enrich,
    _expected_break_point_chances,
    _expected_service_points,
)
from tests.helpers.props_audit_projection import NOW, _Rows, _prop, _stats


def test_poisson_integer_line_splits_push_probability():
    p_over, p_under, p_push = over_under_push_probs(5.0, 5.0)

    assert p_push > 0
    assert round(p_over + p_under + p_push, 6) == 1.0


def test_poisson_half_point_has_no_push_probability():
    p_over, p_under, p_push = over_under_push_probs(5.5, 5.0)

    assert p_push == 0.0
    assert round(p_over + p_under, 6) == 1.0


def test_prizepicks_stat_names_hit_projection_branches():
    stats = _stats()
    opponent = _stats(2)

    assert _compute_stat_avg("Break Points Won", stats, opponent, 0.55, "Hard") is not None
    assert _compute_stat_avg("Fantasy Score", stats, opponent, 0.55, "Hard") is not None
    assert _compute_stat_avg("Total Games Won", stats, opponent, 0.55, "Hard") is not None


def test_same_player_same_match_aces_projection_is_stable_across_lines():
    stats = _stats(aces_per_game=0.08)
    opponent = _stats(2)

    low_line = _enrich(_prop("2.5"), stats, opponent, 0.55, market_total_games=22.5, now=NOW)
    high_line = _enrich(_prop("4.5"), stats, opponent, 0.55, market_total_games=22.5, now=NOW)

    assert low_line.stat_avg == high_line.stat_avg
    assert low_line.expected_service_points == high_line.expected_service_points
    assert low_line.projection_source == "market_total"


def test_aces_projection_uses_market_total_when_available():
    stats = _stats(aces_per_game=0.08)
    opponent = _stats(2)

    market_projection = _compute_stat_avg("Aces", stats, opponent, 0.55, "Hard", market_total_games=26.5)
    fallback_projection = _compute_stat_avg("Aces", stats, opponent, 0.55, "Hard", market_total_games=None)

    assert market_projection is not None
    assert fallback_projection is not None
    assert market_projection != fallback_projection
    assert _expected_service_points(stats, opponent, 0.55, 26.5) > _expected_service_points(stats, opponent, 0.55, None)


def test_double_fault_projection_uses_opponent_allowed_rate():
    stats = _stats()
    low_pressure_opponent = _stats(2)
    high_pressure_opponent = _stats(3)
    low_pressure_opponent.allowed_df_per_sp = 0.03
    high_pressure_opponent.allowed_df_per_sp = 0.07

    low_projection = _compute_stat_avg(
        "Double Faults",
        stats,
        low_pressure_opponent,
        0.55,
        "Hard",
        market_total_games=22.5,
    )
    high_projection = _compute_stat_avg(
        "Double Faults",
        stats,
        high_pressure_opponent,
        0.55,
        "Hard",
        market_total_games=22.5,
    )

    assert low_projection is not None
    assert high_projection is not None
    assert high_projection > low_projection


def test_double_fault_projection_keeps_neutral_factor_without_opponent():
    stats = _stats()

    with_opponent = _compute_stat_avg(
        "Double Faults",
        stats,
        _stats(2),
        0.55,
        "Hard",
        market_total_games=22.5,
    )
    without_opponent = _compute_stat_avg(
        "Double Faults",
        stats,
        None,
        0.55,
        "Hard",
        market_total_games=22.5,
    )

    assert with_opponent is not None
    assert without_opponent is not None
    assert without_opponent < with_opponent


def test_aces_projection_falls_back_to_model_total_without_market_total():
    enriched = _enrich(_prop("2.5"), _stats(), _stats(2), 0.55, market_total_games=None, now=NOW)

    assert enriched.market_total_games is None
    assert enriched.projection_source == "model_total"
    assert enriched.projection_inputs["projection_source"] == "model_total"
    assert enriched.expected_service_points is not None


def test_break_points_use_chance_volume_then_conversion_rate():
    stats = _stats(break_pct=0.25)
    opponent = _stats(2)
    stats.break_points_created_per_return_game = 0.50
    opponent.allowed_break_points_per_service_game = 0.70

    chances = _expected_break_point_chances(stats, opponent, 0.55, 24.0)
    projection = _compute_stat_avg("Break Points Won", stats, opponent, 0.55, "Hard", market_total_games=24.0)

    assert round(chances, 2) == 7.20
    assert projection is not None
    assert round(projection, 2) == 1.80


def test_total_games_probability_uses_match_closeness():
    prop = _prop("28.5")
    prop.stat_type = "Total Games"
    prop.best_of = 3
    stats = _stats()
    opponent = _stats(2)

    close = _enrich(prop, stats, opponent, 0.50, market_total_games=23.0, now=NOW)
    lopsided = _enrich(prop, stats, opponent, 0.90, market_total_games=23.0, now=NOW)

    assert close.market_total_games == lopsided.market_total_games
    assert close.p_over is not None
    assert lopsided.p_over is not None
    assert close.p_over > lopsided.p_over


def test_total_games_probability_uses_match_closeness_for_best_of_five():
    prop = _prop("32.5")
    prop.stat_type = "Total Games"
    prop.best_of = 5
    stats = _stats()
    opponent = _stats(2)

    close = _enrich(prop, stats, opponent, 0.50, market_total_games=30.0, now=NOW)
    lopsided = _enrich(prop, stats, opponent, 0.90, market_total_games=30.0, now=NOW)

    assert close.market_total_games == lopsided.market_total_games
    assert close.p_over is not None
    assert lopsided.p_over is not None
    assert close.p_over > lopsided.p_over


class _Db:
    def __init__(self):
        self.params = None

    async def execute(self, _query, params):
        self.params = params
        return _Rows([(10, Decimal("22.5"), -110, -110)])


def test_market_total_games_lookup_returns_latest_lines_by_match_id():
    db = _Db()

    totals = asyncio.run(get_market_totals(db, [_prop(match_id=10)]))

    assert db.params == {"mids": [10]}
    assert {match_id: total.line for match_id, total in totals.items()} == {10: 22.5}


def test_favorite_fantasy_projection_is_not_flatlined_under_line():
    stats = _stats(aces_per_game=0.06)
    opponent = _stats(2, aces_per_game=0.04)

    projection = _compute_stat_avg("Fantasy Score", stats, opponent, 0.70, "Hard")

    assert projection is not None
    assert projection > 17.0


def test_fantasy_projection_does_not_add_break_points_as_separate_bonus():
    stats = _stats(aces_per_game=0.02, break_pct=0.50)
    opponent = _stats(2, aces_per_game=0.04)

    projection_high_break = _compute_stat_avg("Fantasy Score", stats, opponent, 0.70, "Hard")

    stats.break_pct = 0.0
    projection_zero_break = _compute_stat_avg("Fantasy Score", stats, opponent, 0.70, "Hard")

    assert projection_high_break is not None
    assert projection_zero_break is not None
    assert round(projection_high_break, 2) == round(projection_zero_break, 2)


def test_stale_stats_are_flagged_and_keep_their_side():
    stale = NOW - timedelta(days=3)
    enriched = _enrich(_prop(), _stats(computed_at=stale), _stats(2, computed_at=stale), 0.65, market_total_games=22.5, now=NOW)

    assert "stale_stats" in enriched.data_quality_flags
    assert enriched.confidence is None
    assert enriched.recommendation is not None


def test_staleness_is_measured_from_the_now_passed_in():
    def flags(now: datetime) -> list[str]:
        return _enrich(_prop(), _stats(), _stats(2), 0.65, market_total_games=22.5, now=now).data_quality_flags

    assert "stale_stats" not in flags(NOW + timedelta(hours=47))
    assert "stale_stats" in flags(NOW + timedelta(hours=49))


def test_missing_match_blocks_prizepicks_recommendation():
    enriched = _enrich(_prop(match_id=None), _stats(), None, None, now=NOW)

    assert "missing_match" in enriched.data_quality_flags
    assert enriched.projection_status == "missing_match"
    assert enriched.recommendation is None
    assert enriched.confidence is None


def test_finished_match_blocks_prizepicks_recommendation():
    prop = _prop()
    prop.match_status = "completed"

    enriched = _enrich(prop, _stats(), _stats(2), 0.65, now=NOW)

    assert enriched.match_status == "completed"
    assert enriched.match_finished is True
    assert "match_finished" in enriched.data_quality_flags
    assert enriched.recommendation is None
    assert enriched.confidence is None


def test_invalid_match_link_blocks_prizepicks_recommendation():
    prop = _prop()
    prop.match_status = "scheduled"
    prop.match_link_invalid = True

    enriched = _enrich(prop, _stats(), _stats(2), 0.65, now=NOW)

    assert enriched.match_status == "scheduled"
    assert enriched.match_finished is False
    assert enriched.match_link_invalid is True
    assert "match_link_invalid" in enriched.data_quality_flags
    assert enriched.recommendation is None
    assert enriched.confidence is None


def test_small_sample_is_flagged():
    enriched = _enrich(_prop(), _stats(matches_count=4), _stats(2), 0.65, market_total_games=22.5, now=NOW)

    assert "small_sample" in enriched.data_quality_flags
    assert enriched.confidence is None


def test_surface_stats_fall_back_to_all_surface_when_sample_is_tiny():
    clay = _stats(matches_count=9)
    clay.surface = "Clay"
    overall = _stats(matches_count=47)
    overall.surface = None

    picked = pick_stats_for_player(1, "Clay", {(1, "Clay"): clay, (1, None): overall})

    assert picked is overall
