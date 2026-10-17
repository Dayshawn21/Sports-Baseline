"""Probability helpers for prop distributions.

Poisson works for count stats like aces or double faults, but composite stats
like PrizePicks fantasy score need a wider continuous approximation.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from app.core.poisson import over_under_probs, over_under_push_probs
from app.core.tennis_props import clamp

_FANTASY_SCORE_STD_FLOOR = 7.0

# Spread calibration, derived from the market rather than guessed.
#
# PrizePicks shades its goblin line down and its demon line up around the
# standard line, so the goblin-to-demon gap is a read on how wide the market
# thinks a stat's distribution is. Treating that gap as an inter-quartile range
# (IQR = 1.349 sigma) gives, per stat:
#
#     Total Games      IQR 5.00  ->  sigma 3.71   (model 4.69, already wider)
#     Fantasy Score    IQR 16.00 ->  sigma 11.86  (model ~7.3, too narrow)
#     Double Faults    IQR 4.00  ->  sigma 2.97   (model ~1.87, too narrow)
#     Total Games Won  IQR 4.00  ->  sigma 2.97   (model floor 2.2, too narrow)
#     Aces             IQR 3.00  ->  sigma 2.22   (model 2.83, already wider)
#
# Too narrow a sigma makes every projection look more certain than it is, which
# is what packed the top tier: Total Games Won alone was 27.9% LOCK. These widen
# the three understated stats to the market's own spread. Goblin/demon are
# assumed to sit near the quartiles, so these are lower bounds on the true
# spread — deliberately the conservative direction.
_FANTASY_SCORE_SPREAD_CALIBRATION = 1.62
_GAMES_WON_SIGMA_FLOOR = 2.95
_DOUBLE_FAULT_SIGMA_SCALE = 1.55
_DOUBLE_FAULT_SIGMA_FLOOR = 2.0


@dataclass(frozen=True)
class PropProbabilities:
    p_over: float
    p_under: float
    p_push: float = 0.0

    @property
    def decision_probability(self) -> float:
        """Best actionable side after removing push mass from consideration."""
        actionable = max(1e-9, 1.0 - self.p_push)
        return max(self.p_over, self.p_under) / actionable


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _normal_probs_from_sigma(line: float, expected: float, sigma: float, *, push_aware: bool) -> PropProbabilities:
    if push_aware and float(line).is_integer():
        lower = (line - 0.5 - expected) / sigma
        upper = (line + 0.5 - expected) / sigma
        p_under = _normal_cdf(lower)
        p_push = max(0.0, _normal_cdf(upper) - p_under)
        p_over = max(0.0, 1.0 - p_under - p_push)
        return PropProbabilities(p_over, p_under, p_push)

    z = (line - expected) / sigma
    p_under = _normal_cdf(z)
    p_under = max(0.0, min(1.0, p_under))
    return PropProbabilities(1.0 - p_under, p_under, 0.0)


def fantasy_score_probs(line: float, expected: float) -> tuple[float, float]:
    """Approximate fantasy-score over/under probabilities with a normal model.

    Fantasy score is a composite stat, not a simple Poisson count. We estimate a
    wider standard deviation from the contributing components so confidence is
    not overstated when the projected mean sits a few points from the line.
    """
    games_sd = 3.2 * 2.0
    sets_sd = 0.55 * 6.0
    misc_sd = max(1.4, math.sqrt(max(expected, 0.0)) * 0.35)
    sigma = max(
        _FANTASY_SCORE_STD_FLOOR,
        math.sqrt(games_sd**2 + sets_sd**2 + misc_sd**2) * _FANTASY_SCORE_SPREAD_CALIBRATION,
    )
    z = (line - expected) / sigma
    p_under = _normal_cdf(z)
    p_under = max(0.0, min(1.0, p_under))
    return 1.0 - p_under, p_under


def games_won_probs(
    line: float,
    expected: float,
    win_prob: float | None,
    player_hold: float | None,
    opponent_hold: float | None,
) -> tuple[float, float]:
    """Approximate games-won over/under probabilities with a normal model."""
    probs = games_won_probabilities(line, expected, win_prob, player_hold, opponent_hold)
    return probs.p_over, probs.p_under


def games_won_probabilities(
    line: float,
    expected: float,
    win_prob: float | None,
    player_hold: float | None,
    opponent_hold: float | None,
) -> PropProbabilities:
    """Approximate games-won over/under/push probabilities with a normal model."""
    p = 0.5 if win_prob is None else clamp(float(win_prob), 0.01, 0.99)
    closeness = 1.0 - abs(p - 0.5) * 2.0
    hold_gap = abs((player_hold or 0.78) - (opponent_hold or 0.78))
    sigma = max(_GAMES_WON_SIGMA_FLOOR, 1.9 + 1.2 * closeness + 2.2 * hold_gap)
    return _normal_probs_from_sigma(line, expected, sigma, push_aware=True)


def break_points_probs(line: float, expected: float) -> tuple[float, float]:
    """Approximate break-points-won probabilities with mild overdispersion."""
    sigma = max(1.15, math.sqrt(max(expected, 0.0)) * 1.2)
    z = (line - expected) / sigma
    p_under = _normal_cdf(z)
    p_under = max(0.0, min(1.0, p_under))
    return 1.0 - p_under, p_under


def prop_side(p_over: float, p_under: float) -> str:
    """The side to recommend: whichever is likelier.

    Comparing the projected mean with the line is not the same thing. A count
    stat is skewed, so a mean of 5.6 against a 5.5 line is still more likely to
    land under, and the side has to agree with the probability it is graded on.
    """
    return "OVER" if p_over >= p_under else "UNDER"


def prop_over_under_probs(stat_type: str, line: float, expected: float) -> tuple[float, float]:
    """Return over/under probabilities using the right distribution per stat."""
    probs = prop_probabilities(stat_type, line, expected)
    return probs.p_over, probs.p_under


def prop_probabilities(
    stat_type: str,
    line: float,
    expected: float,
    best_of: int = 3,
    p_deciding_set: float | None = None,
) -> PropProbabilities:
    """Return over/under/push probabilities using the right distribution per stat."""
    st = stat_type.strip().lower().replace(" ", "_")
    if st == "fantasy_score":
        p_over, p_under = fantasy_score_probs(line, expected)
        return PropProbabilities(p_over, p_under, 0.0)
    if st in ("break_points_converted", "break_points_won"):
        sigma = max(1.15, math.sqrt(max(expected, 0.0)) * 1.2)
        return _normal_probs_from_sigma(line, expected, sigma, push_aware=True)
    if st == "double_faults":
        # Double faults are overdispersed relative to Poisson — a server has a
        # clean match or a bad one, rather than a steady rate.
        sigma = max(
            _DOUBLE_FAULT_SIGMA_FLOOR,
            math.sqrt(max(expected, 0.0)) * _DOUBLE_FAULT_SIGMA_SCALE,
        )
        return _normal_probs_from_sigma(line, expected, sigma, push_aware=True)
    if st == "total_games":
        return total_games_probs(
            line,
            expected,
            p_deciding_set=p_deciding_set,
            best_of=best_of,
        )
    p_over, p_under, p_push = over_under_push_probs(line, expected)
    return PropProbabilities(p_over, p_under, p_push)


# Total games is a mixture over how many sets get played, not a single count draw.
#
# Measured over 27,439 completed best-of-3 matches:
#
#     2 sets played   mean 18.67   variance  8.97   var/mean 0.48
#     3 sets played   mean 29.11   variance 13.88   var/mean 0.48
#     pooled          mean 22.29   variance 35.41   var/mean 1.59
#
# Within a known set count the total is *under*dispersed relative to Poisson, because
# games per set are bounded. All the apparent overdispersion comes from mixing two modes
# about 10.4 games apart. Best-of-5 shows the same structure across four modes at roughly
# the same spacing.
#
# Treating the pooled distribution as Poisson gets the tails badly wrong: against a 23
# game projection, Poisson puts P(total > 28) at 0.131 where the data says 0.224.
_SET_GAP_GAMES = 10.4
_WITHIN_SET_COUNT_SIGMA = 3.4
# Fallback spread when the deciding-set probability is unknown, from the pooled variance.
_MARGINAL_SIGMA = 5.95

# Best-of-5 has the same structure over more modes. Measured over 3,466 matches:
#
#     3 sets   mean 28.83   variance 14.63    n=1425
#     4 sets   mean 39.07   variance 16.91    n=654
#     5 sets   mean 50.14   variance 20.24    n=395
#     pooled   mean 30.45   variance 109.25
#
# Set-count shares below are the empirical ones. They should really vary with how close
# the match is, as the best-of-3 weight does, but there is no fitted set-level model here
# yet, and using them flat is far closer than the best-of-3 spread was.
_BO5_SET_COUNT_WEIGHTS = ((3, 0.576), (4, 0.264), (5, 0.160))
_BO5_WITHIN_SIGMA = 4.0


def _bo5_set_count_weights(p_deciding_set: float | None) -> tuple[tuple[int, float], ...]:
    if p_deciding_set is None:
        return _BO5_SET_COUNT_WEIGHTS
    closeness = clamp(float(p_deciding_set) / 0.5, 0.0, 1.0)
    p5 = 0.08 + 0.16 * closeness
    p4 = 0.20 + 0.12 * closeness
    p3 = max(0.0, 1.0 - p4 - p5)
    return ((3, p3), (4, p4), (5, p5))


def total_games_probs(
    line: float,
    expected: float,
    p_deciding_set: float | None = None,
    best_of: int = 3,
) -> PropProbabilities:
    """Over/under for total games, modelled as a mixture over set count.

    `p_deciding_set` is the chance the match goes the distance, which callers already
    derive from win probability as 2 * p * (1 - p). Without it the mixture collapses to a
    single normal at the pooled spread, which is still closer than Poisson.
    """
    if best_of and best_of >= 5:
        weights = _bo5_set_count_weights(p_deciding_set)
        # Anchor the components so their weighted mean is the caller's projection.
        base = sum(w * (n - 3) * _SET_GAP_GAMES for n, w in weights)
        p_over = p_under = p_push = 0.0
        for n_sets, weight in weights:
            mean = expected - base + (n_sets - 3) * _SET_GAP_GAMES
            part = _normal_probs_from_sigma(line, mean, _BO5_WITHIN_SIGMA, push_aware=True)
            p_over += weight * part.p_over
            p_under += weight * part.p_under
            p_push += weight * part.p_push
        return PropProbabilities(p_over, p_under, p_push)

    if p_deciding_set is None:
        return _normal_probs_from_sigma(line, expected, _MARGINAL_SIGMA, push_aware=True)

    p3 = min(max(p_deciding_set, 0.0), 1.0)
    p2 = 1.0 - p3
    # Anchor the components so their weighted mean is the caller's projection.
    m2 = expected - p3 * _SET_GAP_GAMES
    m3 = m2 + _SET_GAP_GAMES

    short = _normal_probs_from_sigma(line, m2, _WITHIN_SET_COUNT_SIGMA, push_aware=True)
    long = _normal_probs_from_sigma(line, m3, _WITHIN_SET_COUNT_SIGMA, push_aware=True)
    return PropProbabilities(
        p_over=p2 * short.p_over + p3 * long.p_over,
        p_under=p2 * short.p_under + p3 * long.p_under,
        p_push=p2 * short.p_push + p3 * long.p_push,
    )
