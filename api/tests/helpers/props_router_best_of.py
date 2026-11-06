"""Shared fixtures and builders, first written for `test_props_router_best_of.py`."""
from datetime import UTC, datetime
from decimal import Decimal


from app.repositories.players import PlayerRollingStats
from app.repositories.props import Prop
from app.routers.props import _enrich


NOW = datetime(2026, 4, 30, 12, 0, tzinfo=UTC)


def _stats(player_id: int = 1) -> PlayerRollingStats:
    return PlayerRollingStats(
        player_id=player_id, surface="Hard", stat_period="last_52w",
        split_type="overall", split_value="all",
        win_rate=0.62, svc_pts_won=0.65, ret_pts_won=0.38,
        aces_per_game=0.18, df_per_game=0.05, hold_pct=0.82, break_pct=0.24,
        matches_count=30, first_in_pct=0.62, first_won_pct=0.73,
        second_won_pct=0.52, dominance_ratio=1.08, computed_at=NOW,
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
                   market_total_games=None, now=NOW)
