"""Shared fixtures and builders, first written for `test_props_audit_projection.py`."""
from datetime import UTC, datetime
from decimal import Decimal

from app.repositories.players import PlayerRollingStats
from app.repositories.props import Prop


NOW = datetime(2026, 4, 30, 12, 0, tzinfo=UTC)


def _prop(line: str = "5.0", *, player_id: int | None = 1, match_id: int | None = 10) -> Prop:
    return Prop(
        id=1,
        player_id=player_id,
        player_name="Test Player",
        match_id=match_id,
        source="prizepicks",
        stat_type="Aces",
        line=Decimal(line),
        odds_type=None,
        fetched_at=datetime(2026, 4, 30, 12, 0, tzinfo=UTC),
        start_time=datetime(2026, 4, 30, 18, 0, tzinfo=UTC),
        surface="Hard",
        raw_json={"match_link_method": "player_start_time"},
    )


def _stats(
    player_id: int = 1,
    *,
    matches_count: int = 30,
    computed_at: datetime | None = None,
    aces_per_game: float = 0.18,
    break_pct: float = 0.24,
) -> PlayerRollingStats:
    return PlayerRollingStats(
        player_id=player_id,
        surface="Hard",
        stat_period="last_52w",
        split_type="overall",
        split_value="all",
        win_rate=0.62,
        svc_pts_won=0.65,
        ret_pts_won=0.38,
        aces_per_game=aces_per_game,
        df_per_game=0.05,
        hold_pct=0.82,
        break_pct=break_pct,
        matches_count=matches_count,
        first_in_pct=0.62,
        first_won_pct=0.73,
        second_won_pct=0.52,
        dominance_ratio=1.08,
        computed_at=computed_at or NOW,
        allowed_aces_per_sp=0.08,
        allowed_df_per_sp=0.05,
        allowed_first_in_pct=0.62,
        allowed_first_won_pct=0.70,
        allowed_second_won_pct=0.50,
        allowed_hold_pct=0.78,
        break_points_created_per_return_game=0.65,
        allowed_break_points_per_service_game=0.60,
    )


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows
