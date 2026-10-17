"""Replay NBA prop projections game by game and score them against results (item 20f).

Pure: no DB, no I/O.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import groupby
from statistics import fmean
from typing import Literal

from app.core.nba_line_only import line_only_value
from app.core.nfl_projection_backtest import PairedDiff
from app.nba.markets import NbaPropMarket

# Double-double is binary and line-only: it needs a probability scored by Brier or log loss, not MAE.
BACKTEST_MARKETS: tuple[NbaPropMarket, ...] = tuple(NbaPropMarket)

# A pre-tip stand-in for the players PrizePicks posts: a real sample and a rotation role.
MIN_PRIOR_GAMES = 10
MIN_PRIOR_MINUTES = 20.0
MINUTES_WINDOW = 10

REFERENCE_ARM = "reference"
REFERENCE_GAMES = 20
# What 20g serves while the reference arm is the projection; frozen rows and the P(over) fit carry it.
NBA_PROJECTION_MODEL_VERSION = "nba-reference-v1"
HOLDOUT_SEASON = 2025
DEVELOPMENT_SEASON = 2024

# Pre-registered 2026-10-06 with this spec, before any variant was scored on the
# 2025-26 holdout. NBA keeps its own constants so a change to NFL's rule cannot move it.
MIN_PAIRED_CASES = 300
MIN_RELATIVE_MAE_IMPROVEMENT = 0.01
STANDARD_ERRORS_REQUIRED = 2.0

NbaVerdict = Literal["adopt", "reject", "insufficient"]


@dataclass(frozen=True)
class NbaHistoryRow:
    """One stored box-score row, with its game's Eastern date and type."""

    player_id: int
    game_id: int
    season: int
    game_date: dt.date
    game_type: str
    did_not_play: bool
    # NULL means not loaded, never zero minutes.
    minutes: float | None
    # The `LINE_ONLY_COLUMNS` stats plus `did_not_play`, so `line_only_value` reads it as a row.
    stats: Mapping[str, int | bool | None]


@dataclass(frozen=True)
class NbaReplayCase:
    player_id: int
    game_id: int
    game_date: dt.date
    game_type: str
    market: str
    # Mean minutes over the last 10 prior played games with minutes stored.
    prior_minutes: float
    projection: float
    actual: float

    @property
    def key(self) -> tuple[int, int, str]:
        return (self.player_id, self.game_id, self.market)

    @property
    def error(self) -> float:
        return self.projection - self.actual


# An arm projects one market from a player's prior played games, oldest first.
Arm = Callable[[Sequence[NbaHistoryRow], NbaPropMarket], float | None]


def window_mean(games: int) -> Arm:
    """The mean settled value over the last `games` prior played games, skipping games where it is NULL.

    A combo market averages its per-game sum, which equals the sum of its components'
    means whenever no component is NULL.
    """
    def arm(prior: Sequence[NbaHistoryRow], market: NbaPropMarket) -> float | None:
        values = [value for row in prior[-games:] if (value := line_only_value(market, row.stats)) is not None]
        return fmean(values) if values else None
    return arm


ARMS: dict[str, Arm] = {
    REFERENCE_ARM: window_mean(REFERENCE_GAMES),
    "last_10": window_mean(10),
}


def prior_minutes(prior: Sequence[NbaHistoryRow]) -> float | None:
    minutes = [row.minutes for row in prior[-MINUTES_WINDOW:] if row.minutes is not None]
    return fmean(minutes) if minutes else None


def eligible_minutes(row: NbaHistoryRow, prior: Sequence[NbaHistoryRow]) -> float | None:
    """The player's prior minutes when the game is scored, else None.

    Eligibility belongs to the harness, not an arm, so every arm is scored on the same cases.
    """
    if row.did_not_play or len(prior) < MIN_PRIOR_GAMES:
        return None
    minutes = prior_minutes(prior)
    return minutes if minutes is not None and minutes >= MIN_PRIOR_MINUTES else None


def _cases_for(row: NbaHistoryRow, prior: Sequence[NbaHistoryRow], minutes: float, arm: Arm) -> list[NbaReplayCase]:
    cases = []
    for market in BACKTEST_MARKETS:
        actual = line_only_value(market, row.stats)
        projection = arm(prior, market) if actual is not None else None
        if actual is None or projection is None:
            continue
        cases.append(NbaReplayCase(
            player_id=row.player_id, game_id=row.game_id, game_date=row.game_date, game_type=row.game_type,
            market=market.value, prior_minutes=minutes, projection=projection, actual=actual,
        ))
    return cases


def replay_cases(history: Iterable[NbaHistoryRow], season: int, arm: Arm) -> list[NbaReplayCase]:
    """Score every eligible player-game of `season`, each from games dated strictly before it.

    Box scores load the morning after a game, so even an earlier game on the same
    Eastern date is not an input. `history` must be in date order.
    """
    played: dict[int, list[NbaHistoryRow]] = defaultdict(list)
    cases: list[NbaReplayCase] = []
    for _, same_day in groupby(history, key=lambda row: row.game_date):
        rows = list(same_day)
        for row in rows:
            prior = played[row.player_id]
            minutes = eligible_minutes(row, prior) if row.season == season else None
            if minutes is not None:
                cases.extend(_cases_for(row, prior, minutes, arm))
        for row in rows:
            if not row.did_not_play:
                played[row.player_id].append(row)
    return cases


def nba_adoption_verdict(diff: PairedDiff) -> NbaVerdict:
    """A candidate arm against its comparison arm in one market, on the holdout."""
    if diff.n < MIN_PAIRED_CASES:
        return "insufficient"
    improves_enough = diff.relative_mae_change <= -MIN_RELATIVE_MAE_IMPROVEMENT
    beyond_noise = diff.mean_diff < -STANDARD_ERRORS_REQUIRED * diff.standard_error
    return "adopt" if improves_enough and beyond_noise else "reject"
