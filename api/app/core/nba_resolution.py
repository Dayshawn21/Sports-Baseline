"""Decide which NBA player and game a PrizePicks line refers to (item 20c).

Reuses NFL's resolver unchanged, with two NBA adjustments made before it runs:
names are accent-folded and team codes mapped to ESPN's. Position is never
passed, because PrizePicks sends "F-C" or "G-F" where ESPN stores "F" or "G",
and the resolver treats a position mismatch as a different player.

Pure: no DB, no I/O.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import replace

from app.core.nba_names import espn_team_code, fold_name
from app.core.nfl_resolution import (
    PlayerCandidate, ResolutionResult, find_game_id, index_candidates, resolve_player,
)


def index_nba_candidates(candidates: Sequence[PlayerCandidate]) -> dict[str, list[PlayerCandidate]]:
    return index_candidates([replace(candidate, name=fold_name(candidate.name)) for candidate in candidates])


def resolve_nba_line(
    player_name: str,
    team: str | None,
    start_time: dt.datetime | None,
    candidate_index: Mapping[str, Sequence[PlayerCandidate]],
    game_index: Mapping[tuple[str, dt.date], int],
    aliases: Mapping[str, int] | None = None,
) -> tuple[ResolutionResult, int | None]:
    """The player resolution and the game id, each decided independently."""
    code = espn_team_code(team)
    result = resolve_player(fold_name(player_name), code, None, candidate_index, aliases)
    return result, find_game_id(code, start_time, game_index)
