"""Game-level Monte Carlo for the 48c match simulation.

Each service game is drawn whole from an exact table of how it can end (held
or broken, serve points won and lost), so the simulation steps game by game
while aces and double faults still have serve points to land on.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.prop_projection import markov_hold
from app.core.tennis_first_set import _HOLD_MAX, _HOLD_MIN
from app.core.tennis_match_chain import _GAUSS_HERMITE, SET_EFFECT_SD

# (held, serve points won, serve points lost)
GameOutcome = tuple[bool, int, int]

DEFAULT_DRAWS = 4_000
# Gamma shapes of the per-match ace and DF rate multiplier, fitted 2026-10-29 by
# `tennis_match_sim --dispersion` on 9,020 2026 ATP and WTA player-matches.
ACE_RATE_SHAPE = 5.78
DF_RATE_SHAPE = 12.89
_MAX_SET_GAMES = 13
# An ace or a double fault is never certain on a single point.
_POINT_RATE_CAP = 0.95

_SPW_SEARCH_STEPS = 60
# Deuce cycles kept as separate rows. A cycle returns to deuce with 2pq <= 0.5,
# so the mass folded onto the last rows is under 0.5 ** 29 (about 2e-9).
_DEUCE_CYCLES = 30


def serve_point_prob(hold: float) -> float:
    """The serve-point win probability whose game chain holds with `hold`.

    `markov_hold` rises with the serve-point probability on [0, 1], so a
    bounded bisection is exact enough and cannot loop.
    """
    target = min(1.0, max(0.0, float(hold)))
    low, high = 0.0, 1.0
    for _ in range(_SPW_SEARCH_STEPS):
        mid = (low + high) / 2.0
        if markov_hold(mid) < target:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def service_game_table(spw: float) -> dict[GameOutcome, float]:
    """Exact distribution of how one service game ends.

    Games settled before deuce are enumerated point by point. From deuce each
    cycle either ends the game two points apart or returns to deuce; after the
    last kept cycle the remaining mass is split by the closed-form deuce win
    probability onto that cycle's rows, so the held mass equals `markov_hold`.
    """
    p, q = float(spw), 1.0 - float(spw)
    table: dict[GameOutcome, float] = {}

    def add(outcome: GameOutcome, mass: float) -> None:
        table[outcome] = table.get(outcome, 0.0) + mass

    live = {(0, 0): 1.0}
    deuce = 0.0
    while live:
        following: dict[tuple[int, int], float] = {}
        for (won, lost), mass in live.items():
            for score, chance in (((won + 1, lost), p), ((won, lost + 1), q)):
                next_won, next_lost = score
                if (next_won, next_lost) == (3, 3):
                    deuce += mass * chance
                elif next_won == 4:
                    add((True, next_won, next_lost), mass * chance)
                elif next_lost == 4:
                    add((False, next_won, next_lost), mass * chance)
                else:
                    following[score] = following.get(score, 0.0) + mass * chance
        live = following

    deuce_win = p * p / max(1e-12, p * p + q * q)
    for cycle in range(_DEUCE_CYCLES):
        level = 3 + cycle
        if cycle == _DEUCE_CYCLES - 1:
            add((True, level + 2, level), deuce * deuce_win)
            add((False, level, level + 2), deuce * (1.0 - deuce_win))
            break
        add((True, level + 2, level), deuce * p * p)
        add((False, level, level + 2), deuce * q * q)
        deuce *= 2.0 * p * q
    return table


@dataclass(frozen=True)
class ServerTables:
    """One player's service games at each carry-over node, ready to sample."""

    spw: np.ndarray
    held: np.ndarray
    won: np.ndarray
    lost: np.ndarray
    cumulative: np.ndarray
    """(node, row) running total of each row's probability."""


@dataclass(frozen=True)
class MatchDraws:
    """Per-draw results. Player arrays have shape (2, draws): row 0 is A, row 1 is B."""

    games_won: np.ndarray
    sets_won: np.ndarray
    first_set_games: np.ndarray
    serve_points_won: np.ndarray
    serve_points_lost: np.ndarray
    aces: np.ndarray
    double_faults: np.ndarray
    breaks: np.ndarray
    tie_breaks: np.ndarray

    @property
    def total_games(self) -> np.ndarray:
        return self.games_won.sum(axis=0)

    @property
    def a_wins(self) -> np.ndarray:
        return self.sets_won[0] > self.sets_won[1]


def _server_tables(holds: list[float]) -> ServerTables:
    spws = [serve_point_prob(hold) for hold in holds]
    tables = [service_game_table(spw) for spw in spws]
    rows = list(tables[0])
    return ServerTables(
        spw=np.array(spws),
        held=np.array([row[0] for row in rows]),
        won=np.array([row[1] for row in rows]),
        lost=np.array([row[2] for row in rows]),
        cumulative=np.array([np.cumsum([table[row] for row in rows]) for table in tables]),
    )


def _carry_over_holds(hold_a: float, hold_b: float, effect_sd: float) -> tuple[list[float], list[float], np.ndarray]:
    """Each node's two holds and its weight, the same mixture `mixed_match_distribution` averages."""
    def clamp(hold: float) -> float:
        return min(_HOLD_MAX, max(_HOLD_MIN, hold))

    if effect_sd <= 0.0:
        return [clamp(hold_a)], [clamp(hold_b)], np.array([1.0])
    holds_a = [clamp(hold_a + effect_sd * node / 2.0) for node, _ in _GAUSS_HERMITE]
    holds_b = [clamp(hold_b - effect_sd * node / 2.0) for node, _ in _GAUSS_HERMITE]
    return holds_a, holds_b, np.array([weight for _, weight in _GAUSS_HERMITE])


def _sample_rows(tables: ServerTables, nodes: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    picks = (tables.cumulative[nodes] < rng.random(len(nodes))[:, None]).sum(axis=1)
    return np.minimum(picks, tables.cumulative.shape[1] - 1)


@dataclass
class _Tally:
    games: np.ndarray
    points_won: np.ndarray
    points_lost: np.ndarray
    breaks: np.ndarray
    tie_breaks: np.ndarray


def _play_service_games(
    serving: np.ndarray, server: int, tables: ServerTables, nodes: np.ndarray,
    set_games: np.ndarray, tally: _Tally, rng: np.random.Generator,
) -> None:
    draws = np.flatnonzero(serving)
    if draws.size == 0:
        return
    rows = _sample_rows(tables, nodes[draws], rng)
    held = tables.held[rows]
    tally.points_won[server, draws] += tables.won[rows]
    tally.points_lost[server, draws] += tables.lost[rows]
    winner = np.where(held, server, 1 - server)
    set_games[winner, draws] += 1
    tally.breaks[1 - server, draws[~held]] += 1


def _play_set(
    live: np.ndarray, a_serves: np.ndarray, tables: tuple[ServerTables, ServerTables],
    tiebreak_win: np.ndarray, nodes: np.ndarray, tally: _Tally, rng: np.random.Generator,
) -> np.ndarray:
    """Play one set for the `live` draws; returns the set's games, shape (2, draws)."""
    set_games = np.zeros_like(tally.games)
    playing = live.copy()
    for _ in range(_MAX_SET_GAMES):
        at_tiebreak = playing & (set_games[0] == 6) & (set_games[1] == 6)
        regular = playing & ~at_tiebreak
        _play_service_games(regular & a_serves, 0, tables[0], nodes, set_games, tally, rng)
        _play_service_games(regular & ~a_serves, 1, tables[1], nodes, set_games, tally, rng)
        tiebreak_draws = np.flatnonzero(at_tiebreak)
        a_takes = rng.random(tiebreak_draws.size) < tiebreak_win[nodes[tiebreak_draws]]
        set_games[np.where(a_takes, 0, 1), tiebreak_draws] += 1
        tally.tie_breaks[tiebreak_draws] += 1
        # A tiebreak counts as a game, so serve keeps alternating into the next set.
        a_serves[playing] = ~a_serves[playing]
        high, low = set_games.max(axis=0), set_games.min(axis=0)
        playing &= ~((high == 7) | ((high == 6) & (low <= 4)))
    return set_games


def simulate_match(
    hold_a: float,
    hold_b: float,
    best_of: int,
    ace_rate_a: float,
    ace_rate_b: float,
    df_rate_a: float,
    df_rate_b: float,
    draws: int = DEFAULT_DRAWS,
    seed: int = 0,
    effect_sd: float = SET_EFFECT_SD,
    ace_shape: float | None = None,
    df_shape: float | None = None,
) -> MatchDraws:
    """Seeded game-by-game draws of one match from the two solved holds.

    Rates are per serve point. `ace_shape` and `df_shape` are step 4's gamma
    shapes for a per-draw rate multiplier (mean 1); None leaves the rate fixed.
    """
    rng = np.random.default_rng(seed)
    holds_a, holds_b, weights = _carry_over_holds(hold_a, hold_b, effect_sd)
    tables = (_server_tables(holds_a), _server_tables(holds_b))
    tiebreak_win = np.array(holds_a) / (np.array(holds_a) + np.array(holds_b))
    nodes = rng.choice(len(weights), size=draws, p=weights / weights.sum())
    tally = _Tally(*(np.zeros((2, draws), dtype=np.int64) for _ in range(4)), np.zeros(draws, dtype=np.int64))
    sets_won = np.zeros((2, draws), dtype=np.int64)
    first_set = np.zeros((2, draws), dtype=np.int64)
    a_serves = rng.random(draws) < 0.5
    live = np.ones(draws, dtype=bool)
    for set_number in range(best_of):
        set_games = _play_set(live, a_serves, tables, tiebreak_win, nodes, tally, rng)
        tally.games += set_games
        if set_number == 0:
            first_set = set_games
        sets_won[0, live] += set_games[0, live] > set_games[1, live]
        sets_won[1, live] += set_games[1, live] > set_games[0, live]
        live &= sets_won.max(axis=0) < best_of // 2 + 1
    aces = _serve_counts(tally.points_won, tables, nodes, (ace_rate_a, ace_rate_b), ace_shape, rng, won=True)
    faults = _serve_counts(tally.points_lost, tables, nodes, (df_rate_a, df_rate_b), df_shape, rng, won=False)
    return MatchDraws(
        tally.games, sets_won, first_set, tally.points_won, tally.points_lost, aces, faults,
        tally.breaks, tally.tie_breaks,
    )


def _serve_counts(
    points: np.ndarray, tables: tuple[ServerTables, ServerTables], nodes: np.ndarray,
    rates: tuple[float, float], shape: float | None, rng: np.random.Generator, *, won: bool,
) -> np.ndarray:
    """Aces land on won serve points, double faults on lost ones, at the per-serve-point rate."""
    counts = np.zeros_like(points)
    for player in (0, 1):
        spw = tables[player].spw[nodes]
        share = spw if won else 1.0 - spw
        multiplier = rng.gamma(shape, 1.0 / shape, size=nodes.size) if shape else 1.0
        chance = np.minimum(_POINT_RATE_CAP, rates[player] * multiplier / np.maximum(share, 1e-9))
        counts[player] = rng.binomial(points[player], chance)
    return counts
