"""NUMERIC columns arrive as Decimal, and mixing those with float silently drops matches.

The newer stat columns are NUMERIC while the original ones are DOUBLE PRECISION, so
build_features would do `Decimal - 0.0` whenever one player had a value and the other
did not. That raises TypeError, which predict_today swallows, removing the match from
the slate with no error anywhere.
"""

from decimal import Decimal

from app.repositories.players import PlayerRollingStats
from app.services.tennis.feature_builder import build_features


def _stats(**overrides) -> PlayerRollingStats:
    base = dict(
        player_id=1, surface=None, stat_period="last_52w", split_type=None,
        split_value=None, win_rate=0.6, svc_pts_won=0.65, ret_pts_won=0.40,
        aces_per_game=0.5, df_per_game=0.2, hold_pct=0.8, break_pct=0.25,
        matches_count=30,
    )
    base.update(overrides)
    return PlayerRollingStats(**base)


class TestDecimalCoercion:
    def test_numeric_columns_are_coerced_to_float(self):
        s = _stats(first_in_pct=Decimal("0.62"), dominance_ratio=Decimal("1.05"))
        assert isinstance(s.first_in_pct, float)
        assert isinstance(s.dominance_ratio, float)
        assert s.first_in_pct == 0.62

    def test_none_stays_none(self):
        assert _stats(first_in_pct=None).first_in_pct is None

    def test_existing_floats_are_untouched(self):
        assert _stats().win_rate == 0.6

    def test_allowed_columns_are_coerced_too(self):
        s = _stats(allowed_hold_pct=Decimal("0.77"), break_points_created_per_return_game=Decimal("1.2"))
        assert isinstance(s.allowed_hold_pct, float)
        assert isinstance(s.break_points_created_per_return_game, float)

    def test_a_decimal_stat_can_be_subtracted_from_a_missing_one(self):
        # The exact production crash: one player has the stat, the other does not.
        p1 = _stats(player_id=1, first_in_pct=Decimal("0.62"))
        p2 = _stats(player_id=2, first_in_pct=None)
        assert (p1.first_in_pct or 0.0) - (p2.first_in_pct or 0.0) == 0.62


class TestBuildFeaturesSurvivesMixedStats:
    def test_features_build_when_only_one_player_has_numeric_stats(self):
        class _M:
            id = 1
            tour = "ATP"
            surface = "hard"
            tournament = "Test Open"
            round = "R32"
            best_of = 3
            match_date = None
            p1_id = 1
            p2_id = 2
            p1_rank = 10
            p2_rank = 20

        history = {"rest_days": 3.0, "experience": 50.0, "matches_10d": 2.0,
                   "matches_30d": 6.0, "streak": 1.0, "last_surface": "hard"}
        feat, _ = build_features(
            match=_M(), p1=None, p2=None, p1_elo=None, p2_elo=None,
            p1_stats=_stats(player_id=1, first_in_pct=Decimal("0.62")),
            p2_stats=_stats(player_id=2, first_in_pct=None),
            p1_surf_stats=None, p2_surf_stats=None,
            p1_last90_stats=None, p2_last90_stats=None,
            p1_top20_stats=None, p2_top20_stats=None,
            p1_top50_stats=None, p2_top50_stats=None,
            h2h_p1_wins=0, h2h_p2_wins=0, h2h_surf_p1_wins=0, h2h_surf_p2_wins=0,
            p1_odds_american=-150, p2_odds_american=130,
            p1_history=history, p2_history=history,
        )
        assert feat["d_first_in_pct"] == 0.62
        assert all(not isinstance(v, Decimal) for v in feat.values())
