"""
Single source of truth for all ML feature names, fill defaults, and tour exclusions.
No other file may use feature name string literals — import from here.
"""
from __future__ import annotations

from typing import Dict, List, Optional

# ── Moneyline market features ──────────────────────────────────────────────────
MONEYLINE_FEATURE_COLS: List[str] = [
    "has_moneyline",
    "market_ml_p1_implied",
    "market_ml_p2_implied",
    "market_ml_p1_no_vig",
    "market_ml_p2_no_vig",
    "market_ml_overround",
    "d_market_ml_no_vig",
]

# ── ELO features ───────────────────────────────────────────────────────────────
ELO_FEATURE_COLS: List[str] = [
    "d_elo",
    "d_surface_elo",
    "d_rank_log",
    "d_age",
    "has_p1_elo",
    "has_p2_elo",
    "has_both_elo",
]

# ── Momentum / streak features ─────────────────────────────────────────────────
MOMENTUM_FEATURE_COLS: List[str] = [
    "d_streak",
    "d_win_rate_last_3",
]

# ── Zero-importance features (excluded from V4+ training) ─────────────────────
ZERO_IMPORTANCE_FEATURES: List[str] = [
    "is_hard",
    "is_masters",
    "has_moneyline",
]

# ── Tour-specific low-importance features ──────────────────────────────────────
ATP_LOW_IMPORTANCE_FEATURES: List[str] = [
    "best_of", "has_both_elo", "is_clay", "is_grand_slam", "is_grass", "tournament_tier",
    "round_ordinal", "h2h_surface_matches", "market_ml_overround", "d_win_rate_last_3",
]

WTA_LOW_IMPORTANCE_FEATURES: List[str] = [
    "best_of", "d_age", "d_rank_log", "h2h_p1_win_pct", "h2h_surface_p1_win_pct",
]

# ── Tournament tier ────────────────────────────────────────────────────────────
# 1=Challenger/ITF, 2=250, 3=500, 4=Masters/WTA1000, 5=Grand Slam/Finals
TOURNAMENT_TIER_COL: str = "tournament_tier"

GRAND_SLAM_NAMES = frozenset([
    "australian open", "french open", "roland garros", "wimbledon", "us open",
])

MASTERS_1000_NAMES = frozenset([
    "indian wells", "miami", "monte carlo", "monte-carlo", "madrid", "rome",
    "internazionali", "montreal", "toronto", "canada", "canadian open",
    "national bank open", "cincinnati", "shanghai", "paris",
])

ATP_500_KEYWORDS = frozenset([
    "500", "dubai", "acapulco", "barcelona", "queen", "halle", "hamburg",
    "washington", "beijing", "tokyo", "vienna", "basel",
])


def tournament_tier(tournament_name: str, tourney_level: str = "") -> int:
    name = (tournament_name or "").lower().strip()
    level = (tourney_level or "").upper().strip()
    if level in ("G", "F") or any(gs in name for gs in GRAND_SLAM_NAMES):
        return 5
    if "atp finals" in name or "wta finals" in name or "tour finals" in name:
        return 5
    if level == "M" or "masters" in name or "1000" in name:
        return 4
    if any(m in name for m in MASTERS_1000_NAMES):
        return 4
    if any(k in name for k in ATP_500_KEYWORDS):
        return 3
    if level == "A" or "250" in name:
        return 2
    if name and level == "":
        return 2
    return 1


# ── Fill defaults for missing features ────────────────────────────────────────
FILL_DEFAULTS: Dict[str, float] = {
    "d_elo": 0.0,
    "d_surface_elo": 0.0,
    "d_rank_log": 0.0,
    "d_age": 0.0,
    "has_p1_elo": 0.0,
    "has_p2_elo": 0.0,
    "has_both_elo": 0.0,
    "d_win_rate_last_20": 0.0,
    "d_win_rate_surface": 0.0,
    "d_experience": 0.0,
    "d_rest_days": 0.0,
    "d_matches_10d": 0.0,
    "d_matches_30d": 0.0,
    "h2h_p1_win_pct": 0.5,
    "h2h_total_matches": 0.0,
    "h2h_surface_p1_win_pct": 0.5,
    "h2h_surface_matches": 0.0,
    "has_moneyline": 0.0,
    "market_ml_p1_implied": 0.5,
    "market_ml_p2_implied": 0.5,
    "market_ml_p1_no_vig": 0.5,
    "market_ml_p2_no_vig": 0.5,
    "market_ml_overround": 0.0,
    "d_market_ml_no_vig": 0.0,
    "round_ordinal": 0.0,
    "tournament_tier": 2.0,
    "d_streak": 0.0,
    "d_win_rate_last_3": 0.0,
    # Serve/return deltas (TennisAbstract last 52 weeks)
    "d_svc_pts_w": 0.0,
    "d_ret_pts_w": 0.0,
    "d_ace_pg": 0.0,
    "d_bp_save": 0.0,
    "d_bp_win": 0.0,
    "d_first_in_pct": 0.0,
    "d_first_won_pct": 0.0,
    "d_second_won_pct": 0.0,
    "d_dominance_ratio": 0.0,
    "d_surf_dominance_ratio": 0.0,
    "d_surf_first_won_pct": 0.0,
    "d_surf_second_won_pct": 0.0,
    "d_last5_hold": 0.0,
    "d_last5_break": 0.0,
    "d_last10_hold": 0.0,
    "d_last10_break": 0.0,
    "d_surf_last10_hold": 0.0,
    "d_surf_last10_break": 0.0,
    "d_last10_aces_pg": 0.0,
    "d_surf_last10_aces_pg": 0.0,
    "d_last10_df_pg": 0.0,
    "d_surf_last10_df_pg": 0.0,
    "d_last10_tb_match_rate": 0.0,
    "d_last10_tb_win_pct": 0.0,
    "d_surf_last10_tb_match_rate": 0.0,
    "d_surf_last10_tb_win_pct": 0.0,
    # V5 features
    "d_surf_switch": 0.0,
    "d_fatigue": 0.0,
    # Contextual Tennis Abstract features
    "d_form_90d_minus_52w_spw": 0.0,
    "d_form_90d_minus_52w_rpw": 0.0,
    "d_form_90d_minus_52w_hold": 0.0,
    "d_form_90d_minus_52w_break": 0.0,
    "d_form_90d_minus_52w_dom": 0.0,
    "d_top20_win_rate": 0.0,
    "d_top20_spw": 0.0,
    "d_top20_rpw": 0.0,
    "d_top20_dom": 0.0,
    "d_top50_win_rate": 0.0,
    "d_top50_dom": 0.0,
    "d_matchup_srv_ret": 0.0,
    "d_matchup_surf_srv_ret": 0.0,
    "p1_last90_matches": 0.0,
    "p2_last90_matches": 0.0,
    "p1_top20_matches": 0.0,
    "p2_top20_matches": 0.0,
    "p1_top50_matches": 0.0,
    "p2_top50_matches": 0.0,
}

# The training export writes these as None when an input is unknown, so the model
# learned them as NaN. Seeding 0.0 at serving would read an unranked player as
# "equal rank", so serving leaves them absent and the registry applies its NaN fill.
NO_DEFAULT_FEATURES: frozenset[str] = frozenset({
    "d_elo", "d_surface_elo", "d_rank_log", "d_age",
})


# Round ordinals, shared by training and serving.
#
# The two sides previously kept separate maps: feature_builder uppercased and held only
# code keys, train_model did not uppercase and held only some word keys. The database
# contains both vocabularies ("R32" and "Round of 32", "QF" and "Quarterfinals"), so each
# map scored 0 for the forms the other handled, and the same match got different values
# in training and serving. Keys here are matched after lowercasing and stripping.
_ROUND_ORDINALS: Dict[str, int] = {
    "rr": 0, "round robin": 0,
    "er": 1, "q": 1, "q1": 1, "qualification round 1": 1,
    "q2": 2, "qualification round 2": 2,
    "q3": 3, "qualification round 3": 3, "qualification final": 3,
    "q4": 4,
    "r128": 1, "round of 128": 1,
    "r64": 2, "round of 64": 2,
    "r32": 3, "round of 32": 3,
    "r16": 4, "round of 16": 4,
    "qf": 5, "quarterfinal": 5, "quarterfinals": 5,
    "sf": 6, "semifinal": 6, "semifinals": 6, "br": 6,
    "f": 7, "final": 7, "g": 7,
}


def round_ordinal(round_name: Optional[str]) -> float:
    """How deep into the draw a round is. 0 when unknown."""
    return float(_ROUND_ORDINALS.get((round_name or "").strip().lower(), 0))


# Shared so training and serving agree on what counts as a slam.
GRAND_SLAM_KEYWORDS = frozenset({
    "australian open", "french open", "roland garros", "wimbledon", "us open",
})


def is_grand_slam(tournament_name: Optional[str]) -> float:
    name = (tournament_name or "").lower()
    return 1.0 if any(gs in name for gs in GRAND_SLAM_KEYWORDS) else 0.0
