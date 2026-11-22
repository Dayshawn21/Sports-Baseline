"""How much of a season's depth chart and Out reports a usage-shift replay can use (70b1).

A season is fit for the 70b usage-shift backtest when most team-weeks name a
starter at each position and most Out players have a chart row that week, so
the teammate who moves up can be found. Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

POSITIONS = ("QB", "RB", "WR", "TE")


@dataclass(frozen=True)
class DepthRow:
    team: str
    week: int
    player_id: int
    position: str
    depth_rank: int


@dataclass(frozen=True)
class OutRow:
    team: str
    week: int
    player_id: int
    position: str


@dataclass(frozen=True)
class DepthCoverage:
    team_weeks: int
    starter_team_weeks: dict[str, int]
    out_players: int
    out_with_depth: int
    # Out rank-1 starters with a same-position teammate charted at rank 2 that week.
    actionable_out_starters: int


def depth_coverage(depth: Iterable[DepthRow], out: Iterable[OutRow]) -> DepthCoverage:
    ranks: dict[tuple[str, int, int], DepthRow] = {}
    charted: dict[tuple[str, int, str], set[int]] = defaultdict(set)
    for row in depth:
        ranks[(row.team, row.week, row.player_id)] = row
        charted[(row.team, row.week, row.position)].add(row.depth_rank)

    team_weeks = {(team, week) for team, week, _ in charted}
    starters = {
        position: sum(1 in charted.get((team, week, position), set()) for team, week in team_weeks)
        for position in POSITIONS
    }
    out_rows = [row for row in out if row.position in POSITIONS]
    with_depth = [ranks[key] for key in ((row.team, row.week, row.player_id) for row in out_rows) if key in ranks]
    actionable = sum(
        row.depth_rank == 1 and 2 in charted[(row.team, row.week, row.position)]
        for row in with_depth
    )
    return DepthCoverage(len(team_weeks), starters, len(out_rows), len(with_depth), actionable)
