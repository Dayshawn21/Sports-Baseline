"""
Shared prop projection logic used by both the props router and best_picks service.

Centralizing here ensures both endpoints produce identical projections for the same
player/match inputs, eliminating the divergence between the props page and BestPicks cards.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from app.core.tennis_first_set import (
    FIRST_SET_STATS, FirstSetDistribution, first_set_distribution, pmf_mean, shift_underdog_hold, stat_pmf,
)
from app.core.tennis_props import (
    _DOWNSTREAM_GAMES_CALIBRATION,
    clamp,
    expected_sets_won_lost_from_win_prob,
    expected_total_games_from_matchup,
    games_won_share_from_matchup,
)

if TYPE_CHECKING:
    from app.repositories.players import PlayerRollingStats

# ── Constants ─────────────────────────────────────────────────────────────────

_SERVICE_GAMES_PER_MATCH = 11.0
_SERVE_POINTS_PER_MATCH = 65.0
_BREAK_CHANCES_PER_MATCH = 3.5
_BASELINE_HOLD_PCT = 0.78
_BREAK_POINTS_PER_BREAK_GAME = _BREAK_CHANCES_PER_MATCH / (_SERVICE_GAMES_PER_MATCH * (1.0 - _BASELINE_HOLD_PCT))
_BREAK_CHANCE_FACTOR_MIN = 0.55
_BREAK_CHANCE_FACTOR_MAX = 1.60
_BASELINE_RET_PTS_WON = 0.38
_ACE_MATCHUP_FACTOR_MIN = 0.75
_ACE_MATCHUP_FACTOR_MAX = 1.25
# League rates per serve point, keyed by players.tour: what a typical same-tour
# opponent allows, so a typical opponent's matchup factor is 1.0. Measured
# 2026-10-28 by app.backtest.tennis_league_rates (48a step 2, players with 5+
# matches). The single 0.075 / 0.045 they replace overstated ATP and WTA aces
# and understated WTA double faults. The pooled values serve an unknown tour.
_LEAGUE_ACE_RATE_BY_TOUR: dict[str, float] = {"ATP": 0.0582, "CHALLENGER": 0.0470, "WTA": 0.0263}
_LEAGUE_DF_RATE_BY_TOUR: dict[str, float] = {"ATP": 0.0401, "CHALLENGER": 0.0426, "WTA": 0.0544}
_LEAGUE_ACE_RATE = 0.0431
_DF_MATCHUP_FACTOR_MIN = 0.80
_DF_MATCHUP_FACTOR_MAX = 1.20
_LEAGUE_DF_RATE = 0.0466
# The first-set chain gave WTA underdogs about 0.31 games too many while their
# favorites were close (48a step 3, 3,906 completed 2026 matches), so only the
# weaker server's hold drops. Fitted by tennis_first_set_level
# --fit-underdog-shift WTA. ATP stayed under the pre-registered 0.25 threshold.
_FIRST_SET_UNDERDOG_HOLD_SHIFT: dict[str, float] = {"WTA": 0.0522}
_GAMES_WIN_SCALE = 1.25
_GAMES_LOSE_SCALE = 0.75

# Stats whose projection scales with the match total (48a). Without a book
# total they run on the model total, which ran low, so they are never a pick.
TOTALS_DEPENDENT_STATS = frozenset({
    "total_games", "total_games_won", "games_won", "aces", "double_faults",
    "break_points_won", "break_points_converted", "fantasy_score",
})

_SURFACE_ACE_FACTOR: dict[str, float] = {
    "Hard": 1.0,
    "Clay": 0.78,
    "Grass": 1.25,
    "Carpet": 1.10,
}

_SURFACE_DF_FACTOR: dict[str, float] = {
    "Hard": 1.0,
    "Clay": 0.90,
    "Grass": 1.08,
    "Carpet": 1.05,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _f(v) -> Optional[float]:
    return float(v) if v is not None else None


def normalize_stat_type(stat_type: str) -> str:
    return stat_type.strip().lower().replace(" ", "_")


# ── Core projection functions ─────────────────────────────────────────────────

def markov_hold(spw: float) -> float:
    """P(hold service game) given serve point win probability (Markov chain formula)."""
    p, q = float(spw), 1.0 - float(spw)
    return p**4 * (1 + 4*q + 10*q**2) + 20*(p**3)*(q**3) * (p**2 / (p**2 + q**2))


def serve_hold(stats: "PlayerRollingStats") -> float:
    """Best available hold% estimate: Markov from serve components, else empirical, else baseline."""
    fip = _f(stats.first_in_pct)
    fwon = _f(stats.first_won_pct)
    swon = _f(stats.second_won_pct)
    if fip is not None and fwon is not None and swon is not None:
        spw = fip * fwon + (1 - fip) * swon
        return markov_hold(spw)
    return _f(stats.hold_pct) or _BASELINE_HOLD_PCT


def _league_rate(rates: dict[str, float], pooled: float, tour: Optional[str]) -> float:
    return rates.get((tour or "").upper(), pooled)


def ace_matchup_factor(opponent_stats: Optional["PlayerRollingStats"], tour: Optional[str] = None) -> float:
    """Multiplier on a player's baseline ace rate based on how the opponent defends serves.

    Prefers the opponent's actual allowed-ace rate (`allowed_aces_per_sp`).
    Falls back to ret_pts_won proxy when that stat isn't populated.
    """
    if opponent_stats is None:
        return 1.0
    allowed_ace = _f(getattr(opponent_stats, "allowed_aces_per_sp", None))
    if allowed_ace is not None and allowed_ace > 0:
        league = _league_rate(_LEAGUE_ACE_RATE_BY_TOUR, _LEAGUE_ACE_RATE, tour)
        return clamp(allowed_ace / league, _ACE_MATCHUP_FACTOR_MIN, _ACE_MATCHUP_FACTOR_MAX)
    opp_ret_pts_won = _f(opponent_stats.ret_pts_won)
    if opp_ret_pts_won is None:
        return 1.0
    baseline_nonreturn = max(1e-6, 1.0 - _BASELINE_RET_PTS_WON)
    opp_nonreturn = max(0.05, 1.0 - opp_ret_pts_won)
    return clamp(opp_nonreturn / baseline_nonreturn, _ACE_MATCHUP_FACTOR_MIN, _ACE_MATCHUP_FACTOR_MAX)


def double_fault_matchup_factor(
    opponent_stats: Optional["PlayerRollingStats"], tour: Optional[str] = None,
) -> float:
    """Multiplier on a player's baseline double-fault rate from opponent pressure."""
    if opponent_stats is None:
        return 1.0
    allowed_df = _f(getattr(opponent_stats, "allowed_df_per_sp", None))
    if allowed_df is not None and allowed_df > 0:
        league = _league_rate(_LEAGUE_DF_RATE_BY_TOUR, _LEAGUE_DF_RATE, tour)
        return clamp(allowed_df / league, _DF_MATCHUP_FACTOR_MIN, _DF_MATCHUP_FACTOR_MAX)
    opp_ret_pts_won = _f(opponent_stats.ret_pts_won)
    if opp_ret_pts_won is None:
        return 1.0
    return clamp(opp_ret_pts_won / _BASELINE_RET_PTS_WON, _DF_MATCHUP_FACTOR_MIN, _DF_MATCHUP_FACTOR_MAX)


def expected_total_games(
    stats: "PlayerRollingStats",
    opponent_stats: Optional["PlayerRollingStats"],
    win_prob: Optional[float],
    market_total_games: Optional[float],
    best_of: int = 3,
) -> float:
    """Expected total games in the match. Prioritizes market line when available."""
    if market_total_games is not None and market_total_games >= 17.0:
        return market_total_games
    hold = serve_hold(stats)
    opp_hold = serve_hold(opponent_stats) if opponent_stats is not None else _BASELINE_HOLD_PCT
    return expected_total_games_from_matchup(hold, opp_hold, win_prob, best_of)


def _downstream_total_games(
    stats: "PlayerRollingStats",
    opponent_stats: Optional["PlayerRollingStats"],
    win_prob: Optional[float],
    market_total_games: Optional[float],
    best_of: int = 3,
) -> float:
    """Match total as the per-player stat models expect to receive it.

    Those models (games won, service points, break-point chances) have their own
    coefficients fitted against the *model* total back when it ran ~9% high, so
    they need that level restored — see _DOWNSTREAM_GAMES_CALIBRATION. A market
    total was never inflated, so it passes through untouched.
    """
    if market_total_games is not None and market_total_games >= 17.0:
        return market_total_games
    return (
        expected_total_games(stats, opponent_stats, win_prob, market_total_games, best_of)
        * _DOWNSTREAM_GAMES_CALIBRATION
    )


def expected_service_points(
    stats: "PlayerRollingStats",
    opponent_stats: Optional["PlayerRollingStats"],
    win_prob: Optional[float],
    market_total_games: Optional[float],
    best_of: int = 3,
) -> float:
    """Expected serve points for this player in the match, scaled to actual match length."""
    total_games = _downstream_total_games(
        stats, opponent_stats, win_prob, market_total_games, best_of
    )
    expected_svc_games = max(1.0, total_games / 2.0)
    hold = serve_hold(stats)
    opp_hold = serve_hold(opponent_stats) if opponent_stats is not None else _BASELINE_HOLD_PCT
    hold_pressure = clamp(
        ((1.0 - hold) + (1.0 - opp_hold)) / (2.0 * (1.0 - _BASELINE_HOLD_PCT)),
        0.85,
        1.15,
    )
    return expected_svc_games * (_SERVE_POINTS_PER_MATCH / _SERVICE_GAMES_PER_MATCH) * hold_pressure


def expected_break_point_chances(
    stats: "PlayerRollingStats",
    opponent_stats: Optional["PlayerRollingStats"],
    win_prob: Optional[float],
    market_total_games: Optional[float],
    best_of: int = 3,
) -> float:
    """Expected break point chances for this player as returner."""
    opp_hold = serve_hold(opponent_stats) if opponent_stats is not None else _BASELINE_HOLD_PCT
    return_games = _downstream_total_games(
        stats, opponent_stats, win_prob, market_total_games, best_of
    ) / 2.0

    created_rate = _f(getattr(stats, "break_points_created_per_return_game", None))
    allowed_rate = (
        _f(getattr(opponent_stats, "allowed_break_points_per_service_game", None))
        if opponent_stats is not None
        else None
    )
    rates = [r for r in (created_rate, allowed_rate) if r is not None and r > 0]
    if rates:
        return return_games * (sum(rates) / len(rates))

    opp_break_rate = max(0.01, 1.0 - opp_hold)
    chances_per_return_game = opp_break_rate * _BREAK_POINTS_PER_BREAK_GAME
    volume_factor = clamp(
        opp_break_rate / max(1e-6, 1.0 - _BASELINE_HOLD_PCT),
        _BREAK_CHANCE_FACTOR_MIN,
        _BREAK_CHANCE_FACTOR_MAX,
    )
    return return_games * chances_per_return_game * volume_factor


def first_set_for_matchup(
    stats: "PlayerRollingStats",
    opponent_stats: Optional["PlayerRollingStats"],
    tour: Optional[str] = None,
) -> FirstSetDistribution:
    """The first-set chain on the two holds, the opponent at baseline when unknown."""
    opponent_hold = serve_hold(opponent_stats) if opponent_stats is not None else _BASELINE_HOLD_PCT
    shift = _FIRST_SET_UNDERDOG_HOLD_SHIFT.get((tour or "").upper(), 0.0)
    return first_set_distribution(*shift_underdog_hold(serve_hold(stats), opponent_hold, shift))


def compute_stat_avg(
    stat_type: str,
    stats: "PlayerRollingStats",
    opponent_stats: Optional["PlayerRollingStats"] = None,
    win_prob: Optional[float] = None,
    surface: Optional[str] = None,
    market_total_games: Optional[float] = None,
    best_of: int = 3,
    tour: Optional[str] = None,
) -> Optional[float]:
    """Convert per-game rolling stats to a per-match expected value for the given stat type.

    win_prob: match-specific win probability for this player.
    surface: court surface used to adjust ace and DF projections.
    market_total_games: live bookmaker total-games line — when available, all projections
        scale to this instead of the model's expected total.
    tour: the player's `players.tour`, for the league rates and first-set shift (48a).
    """
    st = normalize_stat_type(stat_type)
    surf_key = (surface or "").title()

    if st == "aces" and stats.aces_per_game is not None:
        ace_rate = _f(stats.aces_per_game)
        if ace_rate is None:
            return None
        surf_factor = _SURFACE_ACE_FACTOR.get(surf_key, 1.0)
        svc_pts = expected_service_points(
            stats, opponent_stats, win_prob, market_total_games, best_of
        )
        matchup = ace_matchup_factor(opponent_stats, tour)
        return ace_rate * svc_pts * surf_factor * matchup

    if st == "double_faults" and stats.df_per_game is not None:
        df_rate = _f(stats.df_per_game)
        if df_rate is None:
            return None
        df_surf_factor = _SURFACE_DF_FACTOR.get(surf_key, 1.0)
        svc_pts = expected_service_points(
            stats, opponent_stats, win_prob, market_total_games, best_of
        )
        matchup = double_fault_matchup_factor(opponent_stats, tour)
        return df_rate * svc_pts * df_surf_factor * matchup

    if st in ("break_points_converted", "break_points_won") and stats.break_pct is not None:
        bp = _f(stats.break_pct)
        if bp is None:
            return None
        bp_chances = expected_break_point_chances(
            stats, opponent_stats, win_prob, market_total_games, best_of
        )
        return bp * bp_chances

    if st in ("total_games_won", "games_won"):
        hold = serve_hold(stats)
        opp_hold = serve_hold(opponent_stats) if opponent_stats is not None else _BASELINE_HOLD_PCT
        # Apply the share to the downstream total so a market total, when we have
        # one, actually reaches this stat — and so the calibration is applied
        # exactly once, on the model total only.
        total_games_ = _downstream_total_games(
            stats, opponent_stats, win_prob, market_total_games, best_of
        )
        return total_games_ * games_won_share_from_matchup(hold, opp_hold, win_prob)

    if st == "total_games":
        return expected_total_games(stats, opponent_stats, win_prob, market_total_games, best_of)

    if st in FIRST_SET_STATS:
        return pmf_mean(stat_pmf(st, first_set_for_matchup(stats, opponent_stats, tour)))

    if st == "total_sets" and stats.win_rate is not None:
        wr = win_prob if win_prob is not None else _f(stats.win_rate)
        return 2 + 2 * wr * (1 - wr)

    if st == "total_tie_breaks" and stats.win_rate is not None:
        hold = serve_hold(stats)
        wr = win_prob if win_prob is not None else _f(stats.win_rate)
        expected_sets = 2 + 2 * wr * (1 - wr)
        tb_per_set = max(0.0, (hold - 0.5) * 0.6)
        return tb_per_set * expected_sets

    if st == "fantasy_score" and stats.win_rate is not None:
        hold = serve_hold(stats)
        opp_hold = serve_hold(opponent_stats) if opponent_stats is not None else _BASELINE_HOLD_PCT
        wr = win_prob if win_prob is not None else _f(stats.win_rate)
        # Both sides come off the same total, so games_won and games_lost stay
        # true complements. Deriving them from differently-calibrated totals left
        # games_lost ~1 game low and inflated the score.
        total_games_ = _downstream_total_games(
            stats, opponent_stats, wr, market_total_games, best_of
        )
        games_won = total_games_ * games_won_share_from_matchup(hold, opp_hold, wr)
        games_lost = max(0.0, total_games_ - games_won)
        sets_won, sets_lost = expected_sets_won_lost_from_win_prob(wr)
        ace_surf = _SURFACE_ACE_FACTOR.get(surf_key, 1.0)
        df_surf = _SURFACE_DF_FACTOR.get(surf_key, 1.0)
        ace_m = ace_matchup_factor(opponent_stats, tour)
        df_m = double_fault_matchup_factor(opponent_stats, tour)
        svc_pts = expected_service_points(
            stats, opponent_stats, wr, market_total_games, best_of
        )
        ace_rate = _f(stats.aces_per_game)
        df_rate = _f(stats.df_per_game)
        aces_per_match = ace_rate * svc_pts * ace_surf * ace_m if ace_rate is not None else 0.0
        dfs_per_match = df_rate * svc_pts * df_surf * df_m if df_rate is not None else 0.0
        return (
            10
            + games_won - games_lost
            + 3 * sets_won - 3 * sets_lost
            + 0.5 * aces_per_match - 0.5 * dfs_per_match
        )

    return None
