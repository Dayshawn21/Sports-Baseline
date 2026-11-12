"""Injury-aware expected minutes for the NBA prop projection (item 65).

Pure: no DB, no I/O, no clock; the caller passes the roster history.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Sequence
from itertools import groupby
from dataclasses import dataclass, field
from statistics import fmean
from typing import Literal

from app.core.nba_line_only import line_only_value
from app.core.nba_projection_backtest import (
    ARMS, MIN_PRIOR_GAMES, MIN_PRIOR_MINUTES, MINUTES_WINDOW, REFERENCE_ARM, REFERENCE_GAMES, NbaHistoryRow,
    eligible_minutes, prior_minutes,
)
from app.nba.markets import NbaPropMarket

# 2023-24 is the first stored season; reading earlier would let a later backfill
# change `nba-minutes-v1` under the same version.
NBA_MINUTES_FIRST_HISTORY_SEASON = 2023
NBA_MINUTES_MODEL_VERSION = "nba-minutes-v1"
ROTATION_MINUTES = 15.0
MAX_MINUTE_SHIFT = 10.0
MAX_MINUTES = 42.0
MIN_FIT_CASES = 2000
# A k outside this range means the formula is not describing rotations, so 65 stops.
FIT_K_RANGE = (0.0, 2.0)

NbaMinutesFlag = Literal["few_prior_games", "low_minutes", "team_changed", "no_rate"]


@dataclass(frozen=True)
class NbaRosterRow:
    """One stored box-score row with the team the player played for in that game."""

    player_id: int
    game_id: int
    team_id: int
    season: int
    game_date: dt.date
    did_not_play: bool
    # NULL means not loaded, never zero minutes.
    minutes: float | None


@dataclass(frozen=True)
class TeammateAvailability:
    player_id: int
    # Mean minutes over the teammate's last 10 played games, NULL minutes skipped.
    minutes: float
    # Share of the projected player's reference window in which this teammate played.
    window_share: float
    available: bool


@dataclass(frozen=True)
class Availability:
    teammates: tuple[TeammateAvailability, ...]
    # The projected player's window includes games for another team, so the window
    # says nothing about this team's rotation.
    team_changed: bool

    @property
    def team_delta(self) -> float:
        """Teammate minutes expected now minus those in the window: negative when minutes are vacated."""
        return sum(mate.minutes * ((1.0 if mate.available else 0.0) - mate.window_share) for mate in self.teammates)

    @property
    def available_minutes(self) -> float:
        return sum(mate.minutes for mate in self.teammates if mate.available)

    @property
    def out_player_ids(self) -> tuple[int, ...]:
        return tuple(mate.player_id for mate in self.teammates if not mate.available)


@dataclass
class RosterIndex:
    """Roster history as of a date: built from rows dated strictly before it, then advanced a date at a time."""

    # Each player's played games oldest first: (game_id, team_id, minutes).
    played: dict[int, list[tuple[int, int, float | None]]] = field(default_factory=dict)
    latest_team: dict[int, int] = field(default_factory=dict)
    team_games: dict[int, list[int]] = field(default_factory=dict)
    played_in: dict[int, set[int]] = field(default_factory=dict)
    # Players whose latest row is for each team, so a lookup never scans the league.
    members: dict[int, set[int]] = field(default_factory=dict)

    def advance(self, rows: Sequence[NbaRosterRow]) -> None:
        """Add one date's rows, after every game on that date has been projected."""
        for row in rows:
            previous = self.latest_team.get(row.player_id)
            if previous is not None and previous != row.team_id:
                self.members[previous].discard(row.player_id)
            self.latest_team[row.player_id] = row.team_id
            self.members.setdefault(row.team_id, set()).add(row.player_id)
            games = self.team_games.setdefault(row.team_id, [])
            if not games or games[-1] != row.game_id:
                games.append(row.game_id)
            if not row.did_not_play:
                self.played.setdefault(row.player_id, []).append((row.game_id, row.team_id, row.minutes))
                self.played_in.setdefault(row.game_id, set()).add(row.player_id)

    def recent_minutes(self, player_id: int) -> float | None:
        minutes = [m for _, _, m in self.played.get(player_id, [])[-MINUTES_WINDOW:] if m is not None]
        return fmean(minutes) if minutes else None

    def previous_game_players(self, team_id: int) -> frozenset[int]:
        """Who played in the team's latest game before the date: the leakage-free availability source."""
        games = self.team_games.get(team_id)
        return frozenset(self.played_in.get(games[-1], set())) if games else frozenset()


def availability(index: RosterIndex, player_id: int, team_id: int, available_ids: frozenset[int]) -> Availability:
    """Each rotation teammate's minutes, share of the player's window and whether he is available now.

    `team_id` is the player's own team in the game; `available_ids` comes from a named
    source (`previous_game_players`, the game's own box score for the oracle diagnostic,
    or the forward injury report).
    """
    window = index.played.get(player_id, [])[-REFERENCE_GAMES:]
    if any(team != team_id for _, team, _ in window):
        return Availability(teammates=(), team_changed=True)
    window_games = [game for game, _, _ in window]
    teammates = []
    for mate in index.members.get(team_id, ()):
        if mate == player_id:
            continue
        minutes = index.recent_minutes(mate)
        if minutes is None or minutes < ROTATION_MINUTES:
            continue
        shared = sum(1 for game in window_games if mate in index.played_in.get(game, ()))
        share = shared / len(window_games) if window_games else 0.0
        teammates.append(TeammateAvailability(mate, minutes, share, mate in available_ids))
    return Availability(teammates=tuple(sorted(teammates, key=lambda t: t.player_id)), team_changed=False)


@dataclass(frozen=True)
class NbaMinutesProjection:
    model_version: str
    # None when the player is not eligible, exactly as `nba-reference-v1` serves it.
    projection: float | None
    reference: float | None
    minutes_change: float
    prior_minutes: float | None
    # Settled value per minute over the reference window.
    rate: float | None
    out_player_ids: tuple[int, ...]
    flags: tuple[NbaMinutesFlag, ...]


def minutes_change(player_minutes: float, team_delta: float, available_minutes: float, k: float) -> float:
    """The player's share of the teammate-minutes change, scaled by `k`, clamped and capped."""
    total = player_minutes + available_minutes
    change = -k * team_delta * player_minutes / total if total > 0 else 0.0
    change = max(-MAX_MINUTE_SHIFT, min(MAX_MINUTE_SHIFT, change))
    return min(change, MAX_MINUTES - player_minutes)


def _rate(window: Sequence[NbaHistoryRow], market: NbaPropMarket) -> float | None:
    pairs = [
        (value, row.minutes) for row in window
        if row.minutes is not None and (value := line_only_value(market, row.stats)) is not None
    ]
    total_minutes = sum(minutes for _, minutes in pairs)
    return sum(value for value, _ in pairs) / total_minutes if total_minutes > 0 else None


def project_minutes_line(
    prior: Sequence[NbaHistoryRow], available: Availability, market: NbaPropMarket, k: float,
) -> NbaMinutesProjection:
    """The reference projection moved by the player's per-minute rate times his minutes change.

    Eligibility is the reference's, so both versions are scored on the same cases.
    """
    reference = ARMS[REFERENCE_ARM](prior, market)
    minutes = prior_minutes(prior)

    def served(projection: float | None, change: float, rate: float | None,
               flags: tuple[NbaMinutesFlag, ...]) -> NbaMinutesProjection:
        return NbaMinutesProjection(
            model_version=NBA_MINUTES_MODEL_VERSION, projection=projection, reference=reference,
            minutes_change=change, prior_minutes=minutes, rate=rate,
            out_player_ids=available.out_player_ids, flags=flags,
        )

    if len(prior) < MIN_PRIOR_GAMES or reference is None:
        return served(None, 0.0, None, ("few_prior_games",))
    if minutes is None or minutes < MIN_PRIOR_MINUTES:
        return served(None, 0.0, None, ("low_minutes",))
    if available.team_changed:
        return served(reference, 0.0, None, ("team_changed",))
    rate = _rate(prior[-REFERENCE_GAMES:], market)
    if rate is None:
        return served(reference, 0.0, None, ("no_rate",))
    change = minutes_change(minutes, available.team_delta, available.available_minutes, k)
    return served(reference + rate * change, change, rate, ())


@dataclass(frozen=True)
class FitCase:
    """One eligible played player-game of the fit season, availability from `previous_game_players`."""

    actual_minutes: float
    player_minutes: float
    team_delta: float
    available_minutes: float

    @property
    def x(self) -> float:
        total = self.player_minutes + self.available_minutes
        return -self.team_delta * self.player_minutes / total if total > 0 else 0.0

    @property
    def y(self) -> float:
        return self.actual_minutes - self.player_minutes


def fit_rotation_coefficient(cases: Sequence[FitCase]) -> float:
    """Least squares through the origin of minutes above the player's mean on his share of the change.

    Only cases with a nonzero change carry information about k.
    """
    informative = [case for case in cases if case.x != 0.0]
    if len(informative) < MIN_FIT_CASES:
        raise ValueError(f"{len(informative)} cases with a teammate change; the fit needs {MIN_FIT_CASES}")
    return sum(case.x * case.y for case in informative) / sum(case.x * case.x for case in informative)


def k_in_range(k: float) -> bool:
    return FIT_K_RANGE[0] <= k <= FIT_K_RANGE[1]


@dataclass(frozen=True)
class Situation:
    """One eligible player-game with both availability sources, computed before its date's rows are added."""

    row: NbaHistoryRow
    prior: tuple[NbaHistoryRow, ...]
    prior_minutes: float
    previous_game: Availability
    # Leaks the game's own box score: a diagnostic ceiling, never a verdict input.
    oracle: Availability


def situations(
    history: Sequence[NbaHistoryRow], roster: Sequence[NbaRosterRow], seasons: frozenset[int],
) -> list[Situation]:
    """Walk both histories a date at a time; inputs are only rows dated strictly before each game.

    `history` and `roster` are the same box-score rows in date order (20f's projection rows
    and this item's roster rows).
    """
    index = RosterIndex()
    played: dict[int, list[NbaHistoryRow]] = defaultdict(list)
    roster_by_date = {day: list(rows) for day, rows in groupby(roster, key=lambda r: r.game_date)}
    found: list[Situation] = []
    for day, same_day in groupby(history, key=lambda r: r.game_date):
        rows = list(same_day)
        day_roster = roster_by_date.get(day, [])
        team_of = {(r.player_id, r.game_id): r.team_id for r in day_roster}
        in_game: dict[int, set[int]] = defaultdict(set)
        for r in day_roster:
            if not r.did_not_play:
                in_game[r.game_id].add(r.player_id)
        for row in rows:
            prior = played[row.player_id]
            minutes = eligible_minutes(row, prior) if row.season in seasons else None
            team = team_of.get((row.player_id, row.game_id))
            if minutes is None or team is None:
                continue
            found.append(Situation(
                row=row, prior=tuple(prior[-REFERENCE_GAMES:]), prior_minutes=minutes,
                previous_game=availability(index, row.player_id, team, index.previous_game_players(team)),
                oracle=availability(index, row.player_id, team, frozenset(in_game[row.game_id])),
            ))
        for row in rows:
            if not row.did_not_play:
                played[row.player_id].append(row)
        index.advance(day_roster)
    return found
