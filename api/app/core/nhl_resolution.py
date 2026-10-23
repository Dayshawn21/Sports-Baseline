"""Resolve NHL prop players and games without using provider position labels."""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import replace

from app.core.nfl_resolution import (
    PlayerCandidate, ResolutionResult, find_game_id, index_candidates, resolve_player,
)
from app.core.nhl_names import fold_name, nhl_team_code


def index_nhl_candidates(candidates: Sequence[PlayerCandidate]) -> dict[str, list[PlayerCandidate]]:
    return index_candidates([replace(candidate, name=fold_name(candidate.name)) for candidate in candidates])


def resolve_nhl_line(
    player_name: str,
    team: str | None,
    start_time: dt.datetime | None,
    candidate_index: Mapping[str, Sequence[PlayerCandidate]],
    game_index: Mapping[tuple[str, dt.date], int],
    aliases: Mapping[str, int] | None = None,
) -> tuple[ResolutionResult, int | None]:
    """Resolve player and game independently, allowing either link to be missing."""
    code = nhl_team_code(team)
    # PrizePicks F covers NHL C/L/R, so position cannot identify a different player.
    result = resolve_player(fold_name(player_name), code, None, candidate_index, aliases)
    return result, find_game_id(code, start_time, game_index)
