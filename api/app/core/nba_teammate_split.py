"""Which teammates the NBA player page can split by, and each game's side of the split (item 69).

ESPN-listed absences almost never get a box-score row (99.3% of 13,053 checked
2026-11-12), so "without" is the absence of a played row, and games from before
the teammate's first row for the team cannot count as without him.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Sequence
from typing import Literal, Protocol, TypeVar

SplitSide = Literal["with", "without", "before"]

# ESPN's only other stored status is Day-To-Day, which is not a confirmed absence.
NOT_PLAYING = frozenset({"out", "suspension"})


class InjuryEntry(Protocol):
    @property
    def player_id(self) -> int | None: ...
    @property
    def player_name(self) -> str: ...
    @property
    def team(self) -> str: ...
    @property
    def athlete_team(self) -> str | None: ...
    @property
    def status(self) -> str: ...


class DatedGame(Protocol):
    @property
    def game_id(self) -> int: ...
    @property
    def game_date(self) -> dt.date: ...


E = TypeVar("E", bound=InjuryEntry)


def split_teammates(entries: Sequence[E], team: str, player_id: int) -> list[E]:
    """The player's teammates listed as not playing, one per linked player, by name."""
    kept: dict[int, E] = {}
    for entry in entries:
        if entry.player_id is None or entry.player_id == player_id or entry.player_id in kept:
            continue
        if entry.team != team or entry.status.strip().lower() not in NOT_PLAYING:
            continue
        # Filed under one team while ESPN lists the athlete on another: no side to trust.
        if entry.athlete_team is not None and entry.athlete_team != entry.team:
            continue
        kept[entry.player_id] = entry
    return sorted(kept.values(), key=lambda entry: entry.player_name)


def classify_games(
    games: Sequence[DatedGame], first_team_date: dt.date | None, played_game_ids: Collection[int],
) -> list[SplitSide]:
    """One side per game, aligned with `games`; no first date means no game can be judged."""
    return [
        "before" if first_team_date is None or game.game_date < first_team_date
        else "with" if game.game_id in played_game_ids
        else "without"
        for game in games
    ]
