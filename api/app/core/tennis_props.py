"""Tennis-specific projection helpers for match-length-sensitive props."""

from __future__ import annotations

# Total match games used to run ~9% above the market, and the per-player stats
# built on top of it (games won, service points, and the ace / double-fault /
# break-point figures derived from those) had their own coefficients fitted while
# that inflation was in place — so they measured well against market lines
# *because* two errors cancelled. Correcting the match total alone therefore
# dragged all of them ~7% low.
#
# This factor restores the level those downstream stats were previously
# calibrated at, without reintroducing the bias into the match total itself.
# It is a seam, not a result: the underlying formulas mix per-game and per-point
# rates (see `compute_stat_avg`), so they need a proper rework against settled
# prop outcomes rather than more coefficient fitting.
_DOWNSTREAM_GAMES_CALIBRATION = 1.09


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def expected_sets_from_win_prob(win_prob: float | None) -> float:
    p = 0.5 if win_prob is None else clamp(float(win_prob), 0.01, 0.99)
    return 2.0 + 2.0 * p * (1.0 - p)


def expected_sets_won_lost_from_win_prob(win_prob: float | None) -> tuple[float, float]:
    """Estimate expected sets won/lost in a best-of-3 match.

    This is intentionally tied to the expected match length, so a favorite gets
    credit for more set wins without pretending every win is a straight-set win.
    """
    p = 0.5 if win_prob is None else clamp(float(win_prob), 0.01, 0.99)
    expected_sets = expected_sets_from_win_prob(p)
    set_share = clamp(0.5 + 0.65 * (p - 0.5), 0.18, 0.82)
    sets_won = expected_sets * set_share
    return sets_won, expected_sets - sets_won


# Best-of-5 runs longer, and none of the coefficients below know that. Measured over
# completed matches: best-of-3 averages 22.29 total games, best-of-5 averages 30.45.
# Scaling by the ratio keeps all the matchup sensitivity and fixes the level.
_BEST_OF_5_TOTAL_SCALE = 30.45 / 22.29


def expected_total_games_from_matchup(
    player_hold: float,
    opponent_hold: float,
    win_prob: float | None,
    best_of: int = 3,
) -> float:
    """Estimate total match games from service strength and matchup closeness."""
    p = 0.5 if win_prob is None else clamp(float(win_prob), 0.01, 0.99)
    expected_sets = expected_sets_from_win_prob(p)
    avg_hold = clamp((player_hold + opponent_hold) / 2.0, 0.55, 0.95)
    closeness = 1.0 - abs(p - 0.5) * 2.0
    hold_factor = clamp((avg_hold - 0.68) / 0.18, 0.0, 1.0)
    # Keep set length in a realistic best-of-3 band.
    #
    # These coefficients were 8.8 / 0.9 / 0.7, which produced ~10.0 games per set
    # and a median match total of 23.8 against a market median of 21.5 — every
    # single Total Games projection (117/117) landed above the market line, so
    # every prop recommended OVER. All three were scaled by 0.917 to match the
    # market median; the ratios between them are unchanged, so the model responds
    # to hold strength and closeness exactly as before, just at a sane level.
    #
    # Fitted to PrizePicks standard lines, not to settled results — the market is
    # the best anchor available until prop outcomes are recorded.
    games_per_set = 8.07 + 0.83 * hold_factor + 0.64 * closeness
    total = expected_sets * games_per_set
    return total * _BEST_OF_5_TOTAL_SCALE if (best_of or 3) >= 5 else total


def games_won_share_from_matchup(
    player_hold: float,
    opponent_hold: float,
    win_prob: float | None,
) -> float:
    """This player's share of the match's total games, in [0.32, 0.68].

    Split out from `expected_games_won_from_matchup` so callers can apply the
    share to whichever match total is right for them — the market total when one
    exists, the model total otherwise. Folding the total in here forced every
    caller to take the model total and hid that choice.
    """
    p = 0.5 if win_prob is None else clamp(float(win_prob), 0.01, 0.99)
    hold_edge = clamp(player_hold - opponent_hold, -0.18, 0.18)
    return clamp(0.5 + 0.60 * (p - 0.5) + 0.35 * hold_edge, 0.32, 0.68)


def expected_games_won_from_matchup(
    player_hold: float,
    opponent_hold: float,
    win_prob: float | None,
) -> float:
    """Estimate one player's expected games won from the *model* match total.

    Deliberately uncalibrated: `_DOWNSTREAM_GAMES_CALIBRATION` belongs at the
    per-player stat call sites (see prop_projection._downstream_total_games), not
    in this primitive, which also feeds paths that must not be scaled.
    """
    p = 0.5 if win_prob is None else clamp(float(win_prob), 0.01, 0.99)
    total_games = expected_total_games_from_matchup(player_hold, opponent_hold, p)
    return total_games * games_won_share_from_matchup(player_hold, opponent_hold, p)
