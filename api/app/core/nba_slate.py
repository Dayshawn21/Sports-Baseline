"""Which date the NBA slate shows, and each team's record going into it (item 20e1).

Pure: no DB, no I/O.
"""
from __future__ import annotations

import bisect
import datetime as dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class NbaResult:
    season: int
    game_type: str
    game_date: dt.date
    status: str
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None


@dataclass(frozen=True)
class Record:
    wins: int = 0
    losses: int = 0


def slate_date(requested: dt.date | None, today: dt.date, game_dates: Sequence[dt.date]) -> dt.date:
    """The requested date, else today or the next date with games, else the latest one.

    `game_dates` must be sorted ascending.
    """
    if requested is not None:
        return requested
    index = bisect.bisect_left(game_dates, today)
    if index < len(game_dates):
        return game_dates[index]
    return game_dates[-1] if game_dates else today


def adjacent_dates(date: dt.date, game_dates: Sequence[dt.date]) -> tuple[dt.date | None, dt.date | None]:
    """The nearest earlier and later dates with games; `game_dates` sorted ascending."""
    before = bisect.bisect_left(game_dates, date)
    after = bisect.bisect_right(game_dates, date)
    return (game_dates[before - 1] if before else None, game_dates[after] if after < len(game_dates) else None)


def team_records(results: Iterable[NbaResult], season: int, before: dt.date) -> dict[str, Record]:
    """W-L from completed regular-season games of `season` dated before `before`.

    Play-in and playoff games are left out, so a record reads like the standings.
    A team missing from the result has played no such game: read it as 0-0.
    """
    wins: dict[str, int] = {}
    losses: dict[str, int] = {}
    for result in results:
        if (result.season != season or result.game_type != "REG" or result.status != "completed"
                or result.game_date >= before or result.home_score is None or result.away_score is None
                or result.home_score == result.away_score):
            continue
        winner, loser = ((result.home_team, result.away_team) if result.home_score > result.away_score
                         else (result.away_team, result.home_team))
        wins[winner] = wins.get(winner, 0) + 1
        losses[loser] = losses.get(loser, 0) + 1
    return {team: Record(wins.get(team, 0), losses.get(team, 0)) for team in wins.keys() | losses.keys()}
