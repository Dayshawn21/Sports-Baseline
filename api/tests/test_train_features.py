"""The training feature lists are an allowlist of things knowable at match time.

Two classes of feature are deliberately excluded, and both are easy to reintroduce by
accident because the column names still exist elsewhere in the codebase:

- market price, which the ensemble already blends in separately, so including it here
  counts the market twice and stops the model disagreeing with the book
- anything derived from player_rolling_stats, which holds only a current snapshot and
  would describe a 2023 match with 2026 form
"""

from train_model import ATP_FEATURES, WTA_FEATURES

ALL = ATP_FEATURES + WTA_FEATURES

# Named rather than pattern-matched, so adding one back is a deliberate act.
LEAKY_ROLLING_STAT_FEATURES = {
    "d_svc_pts_w", "d_ret_pts_w", "d_ace_pg", "d_bp_save", "d_bp_win",
    "d_last5_hold", "d_last5_break", "d_last10_hold", "d_last10_break",
    "d_surf_last10_hold", "d_surf_last10_break", "d_last10_aces_pg",
    "d_surf_last10_aces_pg", "d_last10_df_pg", "d_surf_last10_df_pg",
    "d_last10_tb_match_rate", "d_last10_tb_win_pct",
    "d_surf_last10_tb_match_rate", "d_surf_last10_tb_win_pct",
    "d_form_90d_minus_52w_spw", "d_form_90d_minus_52w_rpw",
    "d_form_90d_minus_52w_hold", "d_form_90d_minus_52w_break",
    "d_form_90d_minus_52w_dom",
    "d_top20_win_rate", "d_top20_spw", "d_top20_rpw", "d_top20_dom",
    "d_top50_win_rate", "d_top50_dom",
    "d_matchup_srv_ret", "d_matchup_surf_srv_ret",
    "p1_last90_matches", "p2_last90_matches",
    "p1_top20_matches", "p2_top20_matches",
    "p1_top50_matches", "p2_top50_matches",
}


class TestNoMarketPrice:
    def test_no_market_feature_appears_in_either_list(self):
        assert [f for f in ALL if "market" in f] == []


class TestNoSnapshotDerivedFeatures:
    def test_no_rolling_stat_feature_survives(self):
        assert sorted(f for f in ALL if f in LEAKY_ROLLING_STAT_FEATURES) == []

    def test_the_two_reconstructible_win_rates_are_kept(self):
        # These come from match results via HistoryIndex, not from the snapshot table.
        for f in ("d_win_rate_last_20", "d_win_rate_surface"):
            assert f in ATP_FEATURES, f
            assert f in WTA_FEATURES, f


class TestListShape:
    def test_feature_names_are_unique(self):
        assert len(set(ATP_FEATURES)) == len(ATP_FEATURES)
        assert len(set(WTA_FEATURES)) == len(WTA_FEATURES)

    def test_core_signal_is_present(self):
        for f in ("d_elo", "d_surface_elo", "h2h_p1_win_pct", "d_streak", "d_rank_log"):
            assert f in ATP_FEATURES, f
            assert f in WTA_FEATURES, f

    def test_both_tours_carry_a_usable_number_of_features(self):
        assert len(ATP_FEATURES) >= 20
        assert len(WTA_FEATURES) >= 20
