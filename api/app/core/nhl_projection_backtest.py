"""Pre-registered rule and row types for the NHL projection backtest (item 56b).

Everything here was fixed in its own commit before any NHL variant was scored,
so a later reader can show the rule preceded the data. NHL keeps its own
constants: a change to NBA's or NFL's rule must never move this one.

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

from app.core.nfl_projection_backtest import PairedDiff
from app.core.nhl_goalie_adjustment import (
    ADJUSTED_MARKETS, GoalieRecord, Matchup, adjusted_value, goalie_record,
)
from app.core.nhl_player_values import GOALIE_MARKETS, nhl_stat_value
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
    # The opposing-goalie arm (67a) needs the matchup; every other arm ignores both.
    team_id: int | None = None
    opponent_team_id: int | None = None


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
    # Set only by an opposing-goalie arm on a skater case; None everywhere else.
    opposing_starter_found: bool | None = None

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


# An arm projects one market from a player's prior played games, oldest first.
Arm = Callable[[Sequence[NhlHistoryRow], NhlLineOnlyMarket], float | None]


def window_mean(games: int) -> Arm:
    """The mean settled value over the last `games` prior games, skipping games where the stat is NULL."""
    def arm(prior: Sequence[NhlHistoryRow], market: NhlLineOnlyMarket) -> float | None:
        values = [value for row in prior[-games:] if (value := nhl_stat_value(market, row.stats)) is not None]
        return fmean(values) if values else None
    return arm


# An opposing-goalie arm also reads what is known about the starter the skater faces.
MatchupArm = Callable[[Sequence[NhlHistoryRow], NhlLineOnlyMarket, Matchup], float | None]


def opp_goalie_arm(beta_by_market: Mapping[NhlLineOnlyMarket, float]) -> MatchupArm:
    """The reference projection scaled by the opposing starter's multiplier to each market's exponent."""
    def arm(prior: Sequence[NhlHistoryRow], market: NhlLineOnlyMarket, matchup: Matchup) -> float | None:
        value = window_mean(REFERENCE_GAMES)(prior, market)
        if value is None:
            return None
        return adjusted_value(value, market, matchup.multiplier(), beta_by_market.get(market, 0.0))
    return arm


ARMS: dict[str, Arm] = {
    REFERENCE_ARM: window_mean(REFERENCE_GAMES),
    LAST_10_ARM: window_mean(LAST_10_GAMES),
}

# 67a's development arms: every adjusted market at one exponent, for the per-market pick on 2024-25.
OPP_GOALIE_B05_ARM = "opp_goalie_b05"
OPP_GOALIE_B10_ARM = "opp_goalie_b10"
MATCHUP_ARM_BETAS: dict[str, float] = {OPP_GOALIE_B05_ARM: 0.5, OPP_GOALIE_B10_ARM: 1.0}
MATCHUP_ARMS: dict[str, MatchupArm] = {
    name: opp_goalie_arm({market: beta for market in ADJUSTED_MARKETS}) for name, beta in MATCHUP_ARM_BETAS.items()
}


def prior_toi_minutes(prior: Sequence[NhlHistoryRow]) -> float | None:
    """Mean time on ice over the last 10 prior games with TOI stored; NULL games are ignored."""
    seconds = [row.stats["time_on_ice_seconds"] for row in prior[-TOI_WINDOW:] if row.stats.get("time_on_ice_seconds") is not None]
    return fmean(seconds) / 60 if seconds else None


def eligible_case(row: NhlHistoryRow, prior: Sequence[NhlHistoryRow]) -> bool:
    """Whether the game is scored. Eligibility belongs to the harness, so every arm scores the same cases."""
    if row.is_goalie:
        return row.started and len(prior) >= MIN_PRIOR_GOALIE_STARTS
    if len(prior) < MIN_PRIOR_GAMES:
        return False
    minutes = prior_toi_minutes(prior)
    return minutes is not None and minutes >= MIN_PRIOR_TOI_MINUTES


def _markets_for(row: NhlHistoryRow) -> list[NhlLineOnlyMarket]:
    if row.is_goalie:
        return [market for market in BACKTEST_MARKETS if market in GOALIE_MARKETS]
    return [
        market for market in BACKTEST_MARKETS
        if market not in GOALIE_MARKETS and (market not in CENTER_ONLY_MARKETS or row.position == CENTER_POSITION)
    ]


def _cases_for(
    row: NhlHistoryRow, prior: Sequence[NhlHistoryRow], arm: Arm, starter_found: bool | None = None,
) -> list[NhlReplayCase]:
    minutes = None if row.is_goalie else prior_toi_minutes(prior)
    cases = []
    for market in _markets_for(row):
        actual = nhl_stat_value(market, row.stats)
        projection = arm(prior, market) if actual is not None else None
        if actual is None or projection is None:
            continue
        cases.append(NhlReplayCase(
            player_id=row.player_id, game_id=row.game_id, game_date=row.game_date, game_type=row.game_type,
            market=market.value, prior_toi_minutes=minutes, projection=projection, actual=actual,
            opposing_starter_found=starter_found,
        ))
    return cases


@dataclass
class _LeagueTotals:
    saves: int = 0
    shots: int = 0

    def save_pct(self) -> float | None:
        return self.saves / self.shots if self.shots else None

    def add(self, record: GoalieRecord) -> None:
        self.saves += record.saves
        self.shots += record.shots


def _starters(rows: Sequence[NhlHistoryRow]) -> dict[tuple[int, int], int]:
    """(game, team) to the goalie who started for that team; a relief goalie never counts."""
    starters: dict[tuple[int, int], int] = {}
    for row in rows:
        if row.is_goalie and row.started and row.team_id is not None:
            starters.setdefault((row.game_id, row.team_id), row.player_id)
    return starters


def _matchup(
    row: NhlHistoryRow, starters: Mapping[tuple[int, int], int],
    played: Mapping[int, Sequence[NhlHistoryRow]], league: float | None,
) -> Matchup:
    starter = None if row.opponent_team_id is None else starters.get((row.game_id, row.opponent_team_id))
    if starter is None:
        return Matchup(None, league)
    return Matchup(goalie_record([start.stats for start in played.get(starter, [])]), league)


def _matchup_bound(arm: MatchupArm, matchup: Matchup) -> Arm:
    return lambda prior, market: arm(prior, market, matchup)


def replay_cases(history: Iterable[NhlHistoryRow], season: int, arm: Arm) -> list[NhlReplayCase]:
    """Score every eligible player-game of `season`, each from games dated strictly before it.

    Box scores load the morning after a game, so even an earlier game on the same Eastern
    date is not an input. A goalie's inputs are his starts only, matching how the market
    settles. `history` must be in date order.
    """
    return _replay(history, season, lambda row, starters, played, league: (arm, None))


def replay_matchup_cases(history: Iterable[NhlHistoryRow], season: int, arm: MatchupArm) -> list[NhlReplayCase]:
    """`replay_cases` for an opposing-goalie arm: the same cases, each skater's projection given its matchup.

    The opposing starter is the opponent's goalie who started the game, which is known only after
    it (the backtest's hindsight caveat). His record and the league's save percentage come from
    starts dated strictly before the game, under the same same-day rule as every prior game.
    """
    def arm_for(
        row: NhlHistoryRow, starters: Mapping[tuple[int, int], int],
        played: Mapping[int, Sequence[NhlHistoryRow]], league: float | None,
    ) -> tuple[Arm, bool | None]:
        if row.is_goalie:
            return _matchup_bound(arm, Matchup(None, None)), None
        matchup = _matchup(row, starters, played, league)
        return _matchup_bound(arm, matchup), matchup.opposing_goalie is not None

    return _replay(history, season, arm_for)


# Picks the arm for one case from the day's starters, prior starts and league save percentage.
_ArmFor = Callable[
    [NhlHistoryRow, Mapping[tuple[int, int], int], Mapping[int, Sequence[NhlHistoryRow]], float | None],
    tuple[Arm, bool | None],
]


def _replay(history: Iterable[NhlHistoryRow], season: int, arm_for: _ArmFor) -> list[NhlReplayCase]:
    played: dict[int, list[NhlHistoryRow]] = defaultdict(list)
    league = _LeagueTotals()
    cases: list[NhlReplayCase] = []
    for _, same_day in groupby(history, key=lambda row: row.game_date):
        rows = list(same_day)
        starters = _starters(rows)
        for row in rows:
            prior = played[row.player_id]
            if row.season == season and eligible_case(row, prior):
                arm, found = arm_for(row, starters, played, league.save_pct())
                cases.extend(_cases_for(row, prior, arm, found))
        for row in rows:
            if row.started:
                played[row.player_id].append(row)
            if row.is_goalie and row.started:
                league.add(goalie_record([row.stats]))
    return cases
