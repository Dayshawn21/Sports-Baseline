"""Pre-registered rule and row types for the NHL projection backtest (item 56b).

Everything here was fixed in its own commit before any NHL variant was scored,
so a later reader can show the rule preceded the data. NHL keeps its own
constants: a change to NBA's or NFL's rule must never move this one.

Pure: no DB, no I/O.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from app.core.nfl_projection_backtest import PairedDiff
from app.nhl.markets import NhlLineOnlyMarket

# Every priced NHL market, goalie markets included. The two combos and Fantasy Score are not stored (45a).
BACKTEST_MARKETS: tuple[NhlLineOnlyMarket, ...] = tuple(NhlLineOnlyMarket)
# PrizePicks posts Faceoffs Won only for centers.
CENTER_ONLY_MARKETS = frozenset({NhlLineOnlyMarket.FACEOFFS_WON})
CENTER_POSITION = "C"

# The slate's served game types.
SERVED_GAME_TYPES: tuple[str, ...] = ("REG", "PST")

# `sport_games.season` is the start year: 2024 is 2024-25.
PRIOR_SEASON = 2023
DEVELOPMENT_SEASON = 2024
# 45b's designated holdout: scored once per candidate, never fitted on.
HOLDOUT_SEASON = 2025

REFERENCE_ARM = "reference"
REFERENCE_GAMES = 20
LAST_10_ARM = "last_10"
LAST_10_GAMES = 10
# What 56c serves and freezes while the reference arm is the projection.
NHL_PROJECTION_REFERENCE_VERSION = "nhl-reference-v1"

# Eligibility is the harness's, so every arm scores the same cases. The floors are
# pre-game stand-ins for the players PrizePicks posts, set before any scoring and not tuned.
MIN_PRIOR_GAMES = 10
TOI_WINDOW = 10
MIN_PRIOR_TOI_MINUTES = 12.0
MIN_PRIOR_GOALIE_STARTS = 5

# Adoption rule, copied from NBA's and held as NHL's own.
MIN_PAIRED_CASES = 300
MIN_RELATIVE_MAE_IMPROVEMENT = 0.01
STANDARD_ERRORS_REQUIRED = 2.0

NhlVerdict = Literal["adopt", "reject", "insufficient"]


@dataclass(frozen=True)
class NhlHistoryRow:
    """One stored skater or goalie box-score row, with its game's Eastern date and type.

    A row exists only if the player dressed (skater) or played (goalie), so no row means
    did not play. `stats` holds the stored columns, `time_on_ice_seconds` included;
    NULL means not loaded, never zero.
    """

    player_id: int
    game_id: int
    season: int
    game_date: dt.date
    game_type: str
    position: str | None
    is_goalie: bool
    started: bool
    stats: Mapping[str, int | None]


@dataclass(frozen=True)
class NhlReplayCase:
    player_id: int
    game_id: int
    game_date: dt.date
    game_type: str
    market: str
    # Mean TOI minutes over the last 10 prior games for a skater; None for a goalie.
    prior_toi_minutes: float | None
    projection: float
    actual: float

    @property
    def key(self) -> tuple[int, int, str]:
        return (self.player_id, self.game_id, self.market)

    @property
    def error(self) -> float:
        return self.projection - self.actual


def nhl_adoption_verdict(diff: PairedDiff) -> NhlVerdict:
    """A candidate arm against its comparison arm in one market, on the holdout."""
    if diff.n < MIN_PAIRED_CASES:
        return "insufficient"
    improves_enough = diff.relative_mae_change <= -MIN_RELATIVE_MAE_IMPROVEMENT
    beyond_noise = diff.mean_diff < -STANDARD_ERRORS_REQUIRED * diff.standard_error
    return "adopt" if improves_enough and beyond_noise else "reject"
