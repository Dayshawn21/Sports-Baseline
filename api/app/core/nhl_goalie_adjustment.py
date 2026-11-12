"""Opposing-goalie adjustment for NHL skater projections (item 67a).

The constants here are pre-registered: they are fixed in their own commit before any
opposing-goalie arm is scored, and only the per-market exponent is chosen afterwards,
on 2024-25 alone. A change to any of them ships as a new version, never as `-v1`.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.nhl.markets import NhlLineOnlyMarket

NHL_OPP_GOALIE_VERSION = "nhl-opp-goalie-v1"

ADJUSTED_MARKETS = frozenset({
    NhlLineOnlyMarket.SHOTS_ON_GOAL,
    NhlLineOnlyMarket.POINTS,
    NhlLineOnlyMarket.GOALS,
    NhlLineOnlyMarket.ASSISTS,
    NhlLineOnlyMarket.POWER_PLAY_POINTS,
})

GOALIE_QUALITY_STARTS = 20
# Save percentage stabilises slowly: about 35 starts of shots before a goalie's own number
# outweighs the league's. Fixed before scoring, not tuned.
SHRINK_SHOTS = 1000
MIN_MULTIPLIER = 0.80
MAX_MULTIPLIER = 1.25

# beta = 0 is the reference arm itself, so the development arms are the other two.
DEVELOPMENT_BETAS: tuple[float, ...] = (0.5, 1.0)
SELECTION_BETAS: tuple[float, ...] = (0.0, *DEVELOPMENT_BETAS)


@dataclass(frozen=True)
class GoalieRecord:
    """Saves and shots against summed over a goalie's prior starts."""

    saves: int
    shots: int


def _check_league(league_save_pct: float) -> None:
    if not 0.0 < league_save_pct < 1.0:
        raise ValueError(f"league save percentage must be strictly between 0 and 1, got {league_save_pct}")


def shrunk_save_pct(record: GoalieRecord, league_save_pct: float) -> float:
    """The goalie's save percentage pulled toward the league's by `SHRINK_SHOTS` league-average shots."""
    _check_league(league_save_pct)
    return (record.saves + SHRINK_SHOTS * league_save_pct) / (record.shots + SHRINK_SHOTS)


def goalie_multiplier(record: GoalieRecord | None, league_save_pct: float) -> float:
    """Goals this goalie allows per shot relative to an average one, clipped; 1.0 with no record.

    A better goalie gives a value below 1, which lowers the skater's projection.
    """
    _check_league(league_save_pct)
    if record is None:
        return 1.0
    ratio = (1.0 - shrunk_save_pct(record, league_save_pct)) / (1.0 - league_save_pct)
    return min(MAX_MULTIPLIER, max(MIN_MULTIPLIER, ratio))


def adjusted_value(value: float, market: NhlLineOnlyMarket, multiplier: float, beta: float) -> float:
    """The reference projection scaled by `multiplier ** beta`; markets outside the adjusted set are unchanged."""
    if market not in ADJUSTED_MARKETS or beta == 0:
        return value
    return value * multiplier ** beta


@dataclass(frozen=True)
class Matchup:
    """What is known about the opposing starter before a skater's game: his prior starts and the league's."""

    # None when no opposing starter is known; GoalieRecord(0, 0) when he is known but has no prior starts.
    opposing_goalie: GoalieRecord | None
    # None when no start precedes the game in the read window.
    league_save_pct: float | None

    def multiplier(self) -> float:
        if self.league_save_pct is None:
            return 1.0
        return goalie_multiplier(self.opposing_goalie, self.league_save_pct)


def goalie_record(starts: Sequence[Mapping[str, int | None]]) -> GoalieRecord:
    """Saves and shots against over the last `GOALIE_QUALITY_STARTS` starts, skipping starts missing either."""
    recent = [
        (saves, shots) for stats in starts[-GOALIE_QUALITY_STARTS:]
        if (saves := stats.get("saves")) is not None and (shots := stats.get("shots_against")) is not None
    ]
    return GoalieRecord(sum(saves for saves, _ in recent), sum(shots for _, shots in recent))


def select_beta(mae_by_beta: Mapping[float, float]) -> float:
    """The pre-registered pick: the exponent with the lowest development MAE, ties to the smaller.

    `0.0` (the reference arm) must be among the candidates, so a market that no adjustment helps picks it.
    """
    if 0.0 not in mae_by_beta:
        raise ValueError("the reference arm (beta 0) must be a candidate")
    return min(sorted(mae_by_beta), key=lambda beta: mae_by_beta[beta])
