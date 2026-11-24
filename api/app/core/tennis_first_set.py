"""First-set games for tennis props (build-plan item 16e).

An exact game-by-game chain over one set from the two servers' hold
probabilities. The first server is unknown before the match, so both serve
orders are averaged. At 6-6 a single tiebreak game decides the set. The rules
are pre-registered in the 16e spec; change them only through a new check.

Pure: no DB, no I/O.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.core.prop_probs import PropProbabilities

FIRST_SET_STATS = frozenset({"1st_set_total_games", "1st_set_total_games_won"})
_HOLD_MIN = 0.01
_HOLD_MAX = 0.99


@dataclass(frozen=True)
class FirstSetDistribution:
    total_games: dict[int, float]
    player_games: dict[int, float]

    @property
    def mean_total_games(self) -> float:
        return pmf_mean(self.total_games)

    @property
    def mean_player_games(self) -> float:
        return pmf_mean(self.player_games)


def pmf_mean(pmf: dict[int, float]) -> float:
    return sum(value * probability for value, probability in pmf.items())


def _is_over(player: int, opponent: int) -> bool:
    high, low = max(player, opponent), min(player, opponent)
    return high == 7 or (high == 6 and low <= 4)


def _final_scores(player_hold: float, opponent_hold: float, player_serves_first: bool) -> dict[tuple[int, int], float]:
    tiebreak_win = player_hold / (player_hold + opponent_hold)
    live = {(0, 0): 1.0}
    final: dict[tuple[int, int], float] = {}
    while live:
        following: dict[tuple[int, int], float] = {}
        for (player, opponent), probability in live.items():
            if (player, opponent) == (6, 6):
                outcomes = [((7, 6), tiebreak_win), ((6, 7), 1 - tiebreak_win)]
            else:
                player_serving = ((player + opponent) % 2 == 0) == player_serves_first
                player_wins = player_hold if player_serving else 1 - opponent_hold
                outcomes = [((player + 1, opponent), player_wins), ((player, opponent + 1), 1 - player_wins)]
            for score, chance in outcomes:
                target = final if _is_over(*score) else following
                target[score] = target.get(score, 0.0) + probability * chance
        live = following
    return final


def first_set_distribution(player_hold: float, opponent_hold: float) -> FirstSetDistribution:
    """Total games and the player's games in the first set, serve order averaged."""
    player_hold = min(_HOLD_MAX, max(_HOLD_MIN, player_hold))
    opponent_hold = min(_HOLD_MAX, max(_HOLD_MIN, opponent_hold))
    total: dict[int, float] = {}
    games: dict[int, float] = {}
    for player_serves_first in (True, False):
        for (player, opponent), probability in _final_scores(player_hold, opponent_hold, player_serves_first).items():
            total[player + opponent] = total.get(player + opponent, 0.0) + probability / 2
            games[player] = games.get(player, 0.0) + probability / 2
    return FirstSetDistribution(dict(sorted(total.items())), dict(sorted(games.items())))


def shift_underdog_hold(player_hold: float, opponent_hold: float, shift: float) -> tuple[float, float]:
    """Lower only the weaker server's hold by `shift` (48a); equal holds have no underdog."""
    if player_hold < opponent_hold:
        return player_hold - shift, opponent_hold
    if opponent_hold < player_hold:
        return player_hold, opponent_hold - shift
    return player_hold, opponent_hold


def stat_pmf(stat: str, dist: FirstSetDistribution) -> dict[int, float]:
    """The distribution a first-set stat settles on: the whole set, or the player's games."""
    return dist.total_games if stat == "1st_set_total_games" else dist.player_games


def pmf_probabilities(pmf: dict[int, float], line: float) -> PropProbabilities:
    """Exact over, under and push for a line; a push only on an integer line."""
    p_over = sum(probability for value, probability in pmf.items() if value > line)
    p_under = sum(probability for value, probability in pmf.items() if value < line)
    p_push = pmf.get(int(line), 0.0) if math.isclose(line, round(line)) else 0.0
    return PropProbabilities(p_over, p_under, p_push)
