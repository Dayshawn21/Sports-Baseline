"""Each NHL team's W-L-OT record going into a date, as the league's standings write it.

Pure: no DB, no I/O.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class NhlResult:
    season: int
    game_type: str
    game_date: dt.date
    status: str
    end_period: str | None
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None


@dataclass(frozen=True)
class NhlRecord:
    wins: int = 0
    losses: int = 0
    ot_losses: int = 0


def team_records(results: Iterable[NhlResult], season: int, before: dt.date) -> dict[str, NhlRecord]:
    """W-L-OT from completed regular-season games of `season` dated before `before`.

    A win in any period is a W. A loss in overtime or a shootout is the third number, as in the NHL
    standings; a completed game with no stored end period counts its loser as a regulation loss.
    Playoff games are left out. A team missing from the result has played no such game: read it as 0-0-0.
    """
    wins: dict[str, int] = {}
    losses: dict[str, int] = {}
    ot_losses: dict[str, int] = {}
    for result in results:
        if (result.season != season or result.game_type != "REG" or result.status != "completed"
                or result.game_date >= before or result.home_score is None or result.away_score is None
                or result.home_score == result.away_score):
            continue
        winner, loser = ((result.home_team, result.away_team) if result.home_score > result.away_score
                         else (result.away_team, result.home_team))
        wins[winner] = wins.get(winner, 0) + 1
        loser_column = ot_losses if result.end_period in ("OT", "SO") else losses
        loser_column[loser] = loser_column.get(loser, 0) + 1
    teams = wins.keys() | losses.keys() | ot_losses.keys()
    return {team: NhlRecord(wins.get(team, 0), losses.get(team, 0), ot_losses.get(team, 0)) for team in teams}
