"""Exact whole-match distribution from two hold probabilities (48c).

Extends the first-set chain across sets. Each set uses the same scoring (a
single tiebreak game at 6-6), the first server of the match is averaged, and
each later set's first server follows from the previous set's game count: the
player who served the set's first game serves the next set's first game only
when the set had an even number of games.

Pure: no DB, no I/O.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from numpy.polynomial.hermite_e import hermegauss

from app.core.tennis_first_set import _HOLD_MAX, _HOLD_MIN, _final_scores

# (sets won by A, sets won by B, A serves the set's first game, games so far)
_State = tuple[int, int, bool, int]

# Constant holds play sets independently and gave up to 0.107 too many
# best-of-3 deciders against the held-out tennis_sets fit. This sd, fitted
# 2026-10-28 by tennis_match_sim --fit-set-effect, leaves at most 0.023.
SET_EFFECT_SD = 0.140

_NODES, _WEIGHTS = hermegauss(9)
# (node, weight) pairs for a standard normal, weights summing to 1.
_GAUSS_HERMITE = tuple(zip(_NODES.tolist(), (_WEIGHTS / math.sqrt(2.0 * math.pi)).tolist()))


@dataclass(frozen=True)
class MatchDistribution:
    """Player A's match outcome: final set score and total games, both exact."""

    set_scores: dict[tuple[int, int], float]
    total_games: dict[int, float]

    @property
    def win_prob(self) -> float:
        return sum(p for (a_sets, b_sets), p in self.set_scores.items() if a_sets > b_sets)

    @property
    def set_count(self) -> dict[int, float]:
        counts: dict[int, float] = {}
        for (a_sets, b_sets), p in self.set_scores.items():
            counts[a_sets + b_sets] = counts.get(a_sets + b_sets, 0.0) + p
        return dict(sorted(counts.items()))


def _set_outcomes(hold_a: float, hold_b: float) -> dict[bool, dict[tuple[int, int], float]]:
    return {a_first: _final_scores(hold_a, hold_b, a_first) for a_first in (True, False)}


def mixed_match_distribution(
    hold_a: float, hold_b: float, best_of: int = 3, effect_sd: float = 0.0,
) -> MatchDistribution:
    """The chain averaged over a match-level shift in the hold gap.

    Each match draws one normal shift of sd `effect_sd`, split evenly between
    the two holds and kept for every set, so a player who wins one set is more
    likely to win the next (48c step 2). A fixed Gauss-Hermite rule keeps it exact.
    """
    if effect_sd <= 0.0:
        return match_distribution(hold_a, hold_b, best_of)
    set_scores: dict[tuple[int, int], float] = {}
    total_games: dict[int, float] = {}
    for node, weight in _GAUSS_HERMITE:
        half = effect_sd * node / 2.0
        part = match_distribution(hold_a + half, hold_b - half, best_of)
        for score, p in part.set_scores.items():
            set_scores[score] = set_scores.get(score, 0.0) + weight * p
        for games, p in part.total_games.items():
            total_games[games] = total_games.get(games, 0.0) + weight * p
    return MatchDistribution(dict(sorted(set_scores.items())), dict(sorted(total_games.items())))


def match_distribution(hold_a: float, hold_b: float, best_of: int = 3) -> MatchDistribution:
    """Exact set score and total-games pmf for a best-of-`best_of` match."""
    hold_a = min(_HOLD_MAX, max(_HOLD_MIN, hold_a))
    hold_b = min(_HOLD_MAX, max(_HOLD_MIN, hold_b))
    sets_to_win = best_of // 2 + 1
    outcomes = _set_outcomes(hold_a, hold_b)

    live: dict[_State, float] = {(0, 0, True, 0): 0.5, (0, 0, False, 0): 0.5}
    set_scores: dict[tuple[int, int], float] = {}
    total_games: dict[int, float] = {}
    while live:
        following: dict[_State, float] = {}
        for (a_sets, b_sets, a_first, games), probability in live.items():
            for (a_games, b_games), chance in outcomes[a_first].items():
                next_a = a_sets + (a_games > b_games)
                next_b = b_sets + (b_games > a_games)
                set_games = a_games + b_games
                total = games + set_games
                mass = probability * chance
                if sets_to_win in (next_a, next_b):
                    set_scores[(next_a, next_b)] = set_scores.get((next_a, next_b), 0.0) + mass
                    total_games[total] = total_games.get(total, 0.0) + mass
                else:
                    state = (next_a, next_b, a_first == (set_games % 2 == 0), total)
                    following[state] = following.get(state, 0.0) + mass
        live = following
    return MatchDistribution(dict(sorted(set_scores.items())), dict(sorted(total_games.items())))


_SOLVER_HOLD_MIN = 0.25
_SOLVER_HOLD_MAX = 0.99
# Below about 0.55 the total stops rising with the level (both players break
# so often that sets run long again), so the level search stays above it.
_SOLVER_LEVEL_MIN = 0.55
_SOLVER_LEVEL_MAX = 0.95
_SOLVER_TOLERANCE = 1e-6
_SOLVER_MAX_STEPS = 40


@dataclass(frozen=True)
class HoldSolution:
    hold_a: float
    hold_b: float
    clamped: bool
    """A target could not be met inside the hold range, so the nearest edge was used."""
    distribution: MatchDistribution


def p_over_line(total_games: dict[int, float], line: float) -> float:
    """P(total over the line) with pushes left out, as a book prices it."""
    over = sum(p for games, p in total_games.items() if games > line)
    under = sum(p for games, p in total_games.items() if games < line)
    return over / max(1e-12, over + under)


def _solve_increasing(
    f: Callable[[float], float], target: float, low: float, high: float,
) -> tuple[float, bool]:
    """x in [low, high] with f(x) = target for an increasing f; clamped to an edge when out of reach.

    Illinois false position: bracketed like bisection, so it cannot leave the
    range or loop, but it converges in a handful of chain evaluations.
    """
    f_low, f_high = f(low) - target, f(high) - target
    if f_low >= 0.0:
        return low, f_low > _SOLVER_TOLERANCE
    if f_high <= 0.0:
        return high, f_high < -_SOLVER_TOLERANCE
    side = 0
    x = low
    for _ in range(_SOLVER_MAX_STEPS):
        x = (low * f_high - high * f_low) / (f_high - f_low)
        f_x = f(x) - target
        if abs(f_x) < _SOLVER_TOLERANCE:
            break
        if f_x < 0.0:
            low, f_low = x, f_x
            if side == -1:
                f_high /= 2.0
            side = -1
        else:
            high, f_high = x, f_x
            if side == 1:
                f_low /= 2.0
            side = 1
    return x, False


def _holds_at_level(
    level: float, win_prob: float, best_of: int, effect_sd: float,
) -> tuple[float, float, bool]:
    reach = min(level - _SOLVER_HOLD_MIN, _SOLVER_HOLD_MAX - level)
    gap, clamped = _solve_increasing(
        lambda d: mixed_match_distribution(level + d, level - d, best_of, effect_sd).win_prob,
        win_prob, -reach, reach,
    )
    return level + gap, level - gap, clamped


def solve_holds(
    win_prob: float,
    best_of: int = 3,
    total_line: float | None = None,
    p_over: float = 0.5,
    stats_level: float | None = None,
    effect_sd: float = SET_EFFECT_SD,
) -> HoldSolution:
    """The two holds whose chain gives A's `win_prob` and, with a book total,
    the line's push-excluded over price.

    Without a total the holds average `stats_level` (the players' own serving)
    and only the moneyline is matched. The level stays within 0.55 to 0.95
    and each hold within 0.25 to 0.99.
    """
    if total_line is None:
        if stats_level is None:
            raise ValueError("solve_holds needs a total line or a stats level")
        level = min(_SOLVER_LEVEL_MAX, max(_SOLVER_LEVEL_MIN, stats_level))
        hold_a, hold_b, clamped = _holds_at_level(level, win_prob, best_of, effect_sd)
        return HoldSolution(hold_a, hold_b, clamped, mixed_match_distribution(hold_a, hold_b, best_of, effect_sd))

    def over_at(level: float) -> float:
        hold_a, hold_b, _ = _holds_at_level(level, win_prob, best_of, effect_sd)
        return p_over_line(mixed_match_distribution(hold_a, hold_b, best_of, effect_sd).total_games, total_line)

    level, level_clamped = _solve_increasing(over_at, p_over, _SOLVER_LEVEL_MIN, _SOLVER_LEVEL_MAX)
    hold_a, hold_b, gap_clamped = _holds_at_level(level, win_prob, best_of, effect_sd)
    return HoldSolution(
        hold_a, hold_b, level_clamped or gap_clamped,
        mixed_match_distribution(hold_a, hold_b, best_of, effect_sd),
    )
