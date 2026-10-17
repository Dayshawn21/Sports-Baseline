"""
Assembles ML feature vector from DB-loaded match data.
All feature name strings come from feature_contract — never hardcoded here.
"""
from __future__ import annotations

import math
from typing import Optional

from app.ml.feature_contract import (
    FILL_DEFAULTS,
    NO_DEFAULT_FEATURES,
    is_grand_slam,
    round_ordinal,
    tournament_tier,
)
from app.repositories.matches import Match
from app.repositories.players import Player, PlayerElo, PlayerRollingStats


SURFACE_MAP = {"Hard": "hard", "Clay": "clay", "Grass": "grass"}

# Keys are the livetennisapi `round_code` vocabulary. The old Sofascore ingest
# stored free-text labels ("Round of 32"), none of which are keys here, so
# round_ordinal scored 0.0 for effectively every match.
ROUND_ORDINALS = {
    "RR": 0, "ER": 1, "Q": 1, "Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4,
    "R128": 1, "R64": 2, "R32": 3, "R16": 4,
    "QF": 5, "SF": 6, "BR": 6, "F": 7, "G": 7,
}


def _safe_log(x: Optional[float]) -> float:
    if x is None or x <= 0:
        return 0.0
    return math.log(x)


def build_features(
    match: Match,
    p1: Player,
    p2: Player,
    p1_elo: Optional[PlayerElo],
    p2_elo: Optional[PlayerElo],
    p1_stats: Optional[PlayerRollingStats],      # overall season stats
    p2_stats: Optional[PlayerRollingStats],
    p1_surf_stats: Optional[PlayerRollingStats], # surface-specific stats
    p2_surf_stats: Optional[PlayerRollingStats],
    h2h_p1_wins: int,
    h2h_p2_wins: int,
    h2h_surf_p1_wins: int,
    h2h_surf_p2_wins: int,
    p1_last90_stats: Optional[PlayerRollingStats] = None,
    p2_last90_stats: Optional[PlayerRollingStats] = None,
    p1_top20_stats: Optional[PlayerRollingStats] = None,
    p2_top20_stats: Optional[PlayerRollingStats] = None,
    p1_top50_stats: Optional[PlayerRollingStats] = None,
    p2_top50_stats: Optional[PlayerRollingStats] = None,
    p1_odds_american: Optional[int] = None,
    p2_odds_american: Optional[int] = None,
    odds_stale: bool = False,
    overround: Optional[float] = None,
    p1_history: Optional[dict] = None,
    p2_history: Optional[dict] = None,
    asof: Optional[dict] = None,
) -> tuple[dict, list[str]]:
    """
    Build feature dict for ML inference. Also returns quality flags.

    Returns:
        (features: dict, quality_flags: list[str])
    """
    from app.core.odds import american_to_prob, devig_two_way

    feat: dict = {k: v for k, v in FILL_DEFAULTS.items() if k not in NO_DEFAULT_FEATURES}
    flags: list[str] = []
    surf = SURFACE_MAP.get(match.surface or "", None)

    # ── ELO features ─────────────────────────────────────────────────────────
    if p1_elo and p2_elo:
        feat["has_p1_elo"] = 1.0
        feat["has_p2_elo"] = 1.0
        feat["has_both_elo"] = 1.0
        feat["d_elo"] = (p1_elo.elo or 0.0) - (p2_elo.elo or 0.0)

        surf_elo_map = {"hard": ("elo_hard", "elo_hard"), "clay": ("elo_clay", "elo_clay"), "grass": ("elo_grass", "elo_grass")}
        if surf and surf in surf_elo_map:
            p1_s, p2_s = surf_elo_map[surf]
            s1 = getattr(p1_elo, p1_s, None)
            s2 = getattr(p2_elo, p2_s, None)
            if s1 is not None and s2 is not None:
                feat["has_surface_elo"] = 1.0
                feat["d_surface_elo"] = s1 - s2
    elif p1_elo:
        feat["has_p1_elo"] = 1.0
        flags.append("p2_elo_missing")
    elif p2_elo:
        feat["has_p2_elo"] = 1.0
        flags.append("p1_elo_missing")
    else:
        flags.append("elo_missing")

    # ── Rank features ─────────────────────────────────────────────────────────
    if match.p1_rank and match.p2_rank:
        feat["d_rank_log"] = _safe_log(match.p2_rank) - _safe_log(match.p1_rank)

    # ── Age ───────────────────────────────────────────────────────────────────
    if getattr(p1, "birth_date", None) and getattr(p2, "birth_date", None) and match.match_date:
        from datetime import date as _date
        ref = match.match_date if isinstance(match.match_date, _date) else _date.today()
        p1_age = (ref - p1.birth_date).days / 365.25
        p2_age = (ref - p2.birth_date).days / 365.25
        feat["d_age"] = p1_age - p2_age

    # ── Match history (rest days, experience, streak, recent activity) ──────
    p1_h = p1_history or {}
    p2_h = p2_history or {}
    if p1_h.get("rest_days") is not None and p2_h.get("rest_days") is not None:
        feat["d_rest_days"] = p1_h["rest_days"] - p2_h["rest_days"]
    feat["d_experience"] = p1_h.get("experience", 0.0) - p2_h.get("experience", 0.0)
    feat["d_matches_10d"] = p1_h.get("matches_10d", 0.0) - p2_h.get("matches_10d", 0.0)
    feat["d_matches_30d"] = p1_h.get("matches_30d", 0.0) - p2_h.get("matches_30d", 0.0)
    feat["d_streak"] = p1_h.get("streak", 0.0) - p2_h.get("streak", 0.0)

    # ── Surface transition (1 = switching surfaces, 0 = same) ────────────────
    current_surface = match.surface
    p1_switch = 0.0
    p2_switch = 0.0
    p1_last_surf = p1_h.get("last_surface")
    p2_last_surf = p2_h.get("last_surface")
    if p1_last_surf and current_surface and p1_last_surf != current_surface:
        p1_switch = 1.0
    if p2_last_surf and current_surface and p2_last_surf != current_surface:
        p2_switch = 1.0
    feat["d_surf_switch"] = p1_switch - p2_switch

    # ── Fatigue index (weighted recent match load) ───────────────────────────
    p1_fatigue = p1_h.get("matches_10d", 0.0) * 1.5 + p1_h.get("matches_30d", 0.0) * 0.3
    p2_fatigue = p2_h.get("matches_10d", 0.0) * 1.5 + p2_h.get("matches_30d", 0.0) * 0.3
    feat["d_fatigue"] = p1_fatigue - p2_fatigue

    # ── H2H ───────────────────────────────────────────────────────────────────
    h2h_total = h2h_p1_wins + h2h_p2_wins
    if h2h_total > 0:
        feat["h2h_p1_win_pct"] = h2h_p1_wins / h2h_total
        feat["h2h_total_matches"] = float(h2h_total)
    h2h_surf_total = h2h_surf_p1_wins + h2h_surf_p2_wins
    if h2h_surf_total > 0:
        feat["h2h_surface_p1_win_pct"] = h2h_surf_p1_wins / h2h_surf_total
        feat["h2h_surface_matches"] = float(h2h_surf_total)

    # ── Rolling stats (TennisAbstract last 52 weeks) ──────────────────────────
    if p1_stats and p2_stats:
        feat["d_svc_pts_w"] = (p1_stats.svc_pts_won or 0.0) - (p2_stats.svc_pts_won or 0.0)
        feat["d_ret_pts_w"] = (p1_stats.ret_pts_won or 0.0) - (p2_stats.ret_pts_won or 0.0)
        feat["d_ace_pg"] = (p1_stats.aces_per_game or 0.0) - (p2_stats.aces_per_game or 0.0)
        feat["d_bp_save"] = (p1_stats.hold_pct or 0.0) - (p2_stats.hold_pct or 0.0)
        feat["d_bp_win"] = (p1_stats.break_pct or 0.0) - (p2_stats.break_pct or 0.0)
        feat["d_win_rate_last_20"] = (p1_stats.win_rate or 0.0) - (p2_stats.win_rate or 0.0)
        feat["d_first_in_pct"] = (p1_stats.first_in_pct or 0.0) - (p2_stats.first_in_pct or 0.0)
        feat["d_first_won_pct"] = (p1_stats.first_won_pct or 0.0) - (p2_stats.first_won_pct or 0.0)
        feat["d_second_won_pct"] = (p1_stats.second_won_pct or 0.0) - (p2_stats.second_won_pct or 0.0)
        feat["d_dominance_ratio"] = (p1_stats.dominance_ratio or 0.0) - (p2_stats.dominance_ratio or 0.0)

    if p1_surf_stats and p2_surf_stats:
        feat["d_win_rate_surface"] = (p1_surf_stats.win_rate or 0.0) - (p2_surf_stats.win_rate or 0.0)
        feat["d_last10_hold"] = (p1_surf_stats.hold_pct or 0.0) - (p2_surf_stats.hold_pct or 0.0)
        feat["d_last10_break"] = (p1_surf_stats.break_pct or 0.0) - (p2_surf_stats.break_pct or 0.0)
        feat["d_surf_last10_hold"] = feat["d_last10_hold"]
        feat["d_surf_last10_break"] = feat["d_last10_break"]
        feat["d_last10_aces_pg"] = (p1_surf_stats.aces_per_game or 0.0) - (p2_surf_stats.aces_per_game or 0.0)
        feat["d_surf_last10_aces_pg"] = feat["d_last10_aces_pg"]
        feat["d_last10_df_pg"] = (p1_surf_stats.df_per_game or 0.0) - (p2_surf_stats.df_per_game or 0.0)
        feat["d_surf_last10_df_pg"] = feat["d_last10_df_pg"]
        feat["d_surf_dominance_ratio"] = (p1_surf_stats.dominance_ratio or 0.0) - (p2_surf_stats.dominance_ratio or 0.0)
        feat["d_surf_first_won_pct"] = (p1_surf_stats.first_won_pct or 0.0) - (p2_surf_stats.first_won_pct or 0.0)
        feat["d_surf_second_won_pct"] = (p1_surf_stats.second_won_pct or 0.0) - (p2_surf_stats.second_won_pct or 0.0)

    # Contextual splits used for the next training pass. Current model artifacts
    # will ignore any features not listed in their saved feature files.
    if p1_stats and p2_stats:
        feat["d_matchup_srv_ret"] = (
            ((p1_stats.svc_pts_won or 0.0) - (p2_stats.ret_pts_won or 0.0))
            - ((p2_stats.svc_pts_won or 0.0) - (p1_stats.ret_pts_won or 0.0))
        )
    if p1_surf_stats and p2_surf_stats:
        feat["d_matchup_surf_srv_ret"] = (
            ((p1_surf_stats.svc_pts_won or 0.0) - (p2_surf_stats.ret_pts_won or 0.0))
            - ((p2_surf_stats.svc_pts_won or 0.0) - (p1_surf_stats.ret_pts_won or 0.0))
        )

    if p1_last90_stats and p2_last90_stats and p1_stats and p2_stats:
        feat["d_form_90d_minus_52w_spw"] = (
            ((p1_last90_stats.svc_pts_won or 0.0) - (p1_stats.svc_pts_won or 0.0))
            - ((p2_last90_stats.svc_pts_won or 0.0) - (p2_stats.svc_pts_won or 0.0))
        )
        feat["d_form_90d_minus_52w_rpw"] = (
            ((p1_last90_stats.ret_pts_won or 0.0) - (p1_stats.ret_pts_won or 0.0))
            - ((p2_last90_stats.ret_pts_won or 0.0) - (p2_stats.ret_pts_won or 0.0))
        )
        feat["d_form_90d_minus_52w_hold"] = (
            ((p1_last90_stats.hold_pct or 0.0) - (p1_stats.hold_pct or 0.0))
            - ((p2_last90_stats.hold_pct or 0.0) - (p2_stats.hold_pct or 0.0))
        )
        feat["d_form_90d_minus_52w_break"] = (
            ((p1_last90_stats.break_pct or 0.0) - (p1_stats.break_pct or 0.0))
            - ((p2_last90_stats.break_pct or 0.0) - (p2_stats.break_pct or 0.0))
        )
        feat["d_form_90d_minus_52w_dom"] = (
            ((p1_last90_stats.dominance_ratio or 0.0) - (p1_stats.dominance_ratio or 0.0))
            - ((p2_last90_stats.dominance_ratio or 0.0) - (p2_stats.dominance_ratio or 0.0))
        )
        feat["p1_last90_matches"] = float(p1_last90_stats.matches_count or 0)
        feat["p2_last90_matches"] = float(p2_last90_stats.matches_count or 0)
    else:
        flags.append("ctx_last90_missing")

    if p1_top20_stats and p2_top20_stats:
        feat["d_top20_win_rate"] = (p1_top20_stats.win_rate or 0.0) - (p2_top20_stats.win_rate or 0.0)
        feat["d_top20_spw"] = (p1_top20_stats.svc_pts_won or 0.0) - (p2_top20_stats.svc_pts_won or 0.0)
        feat["d_top20_rpw"] = (p1_top20_stats.ret_pts_won or 0.0) - (p2_top20_stats.ret_pts_won or 0.0)
        feat["d_top20_dom"] = (p1_top20_stats.dominance_ratio or 0.0) - (p2_top20_stats.dominance_ratio or 0.0)
        feat["p1_top20_matches"] = float(p1_top20_stats.matches_count or 0)
        feat["p2_top20_matches"] = float(p2_top20_stats.matches_count or 0)
    else:
        flags.append("ctx_top20_missing")

    if p1_top50_stats and p2_top50_stats:
        feat["d_top50_win_rate"] = (p1_top50_stats.win_rate or 0.0) - (p2_top50_stats.win_rate or 0.0)
        feat["d_top50_dom"] = (p1_top50_stats.dominance_ratio or 0.0) - (p2_top50_stats.dominance_ratio or 0.0)
        feat["p1_top50_matches"] = float(p1_top50_stats.matches_count or 0)
        feat["p2_top50_matches"] = float(p2_top50_stats.matches_count or 0)
    else:
        flags.append("ctx_top50_missing")

    # ── Tournament / round ────────────────────────────────────────────────────
    surf_lower = (match.surface or "").lower()
    feat["is_clay"] = 1.0 if surf_lower == "clay" else 0.0
    feat["is_grass"] = 1.0 if surf_lower == "grass" else 0.0
    feat["is_grand_slam"] = is_grand_slam(match.tournament)
    feat["tournament_tier"] = float(tournament_tier(match.tournament or ""))
    feat["round_ordinal"] = round_ordinal(match.round)
    feat["best_of"] = float(match.best_of or 3)

    # ── Market odds ───────────────────────────────────────────────────────────
    if p1_odds_american and p2_odds_american:
        p1_imp = american_to_prob(p1_odds_american)
        p2_imp = american_to_prob(p2_odds_american)
        p1_nv, p2_nv = devig_two_way(p1_imp, p2_imp)
        vig = (p1_imp + p2_imp) - 1.0

        feat["has_moneyline"] = 1.0
        feat["market_ml_p1_implied"] = p1_imp
        feat["market_ml_p2_implied"] = p2_imp
        feat["market_ml_p1_no_vig"] = p1_nv
        feat["market_ml_p2_no_vig"] = p2_nv
        feat["market_ml_overround"] = vig
        feat["d_market_ml_no_vig"] = p1_nv - p2_nv

        if overround is None:
            overround = vig
        if overround > 0.08:
            flags.append("high_overround")
        if odds_stale:
            flags.append("stale_odds")
    else:
        flags.append("market_missing")

    # ── Check if key feature groups are present ───────────────────────────────
    has_rolling = p1_stats is not None and p2_stats is not None
    has_surf_stats = p1_surf_stats is not None and p2_surf_stats is not None
    if not has_rolling or not has_surf_stats:
        flags.append("ml_features_partial")

    # As-of-date features win over anything computed above. The snapshot tables give
    # d_win_rate_* over TennisAbstract's 52-week window and h2h_* from a running total,
    # while the model learned both from match results over a fixed recent window. Serving
    # the snapshot versions would hand the model a differently-defined vector.
    if asof:
        for key, value in asof.items():
            if value is None:
                feat.pop(key, None)
            else:
                feat[key] = value

    return feat, flags
