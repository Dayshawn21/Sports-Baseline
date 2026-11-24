"""Conservative full-name/team and event matching for stored NHL context."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from app.core.nhl_context import ESPN_NHL_TEAMS, NhlGoalieObservation, NhlInjuryEntry, espn_nhl_team_code
from app.core.nhl_names import fold_name

PlayerLinkReason = Literal[
    "matched", "no_candidate", "ambiguous", "team_mismatch", "missing_team",
    "position_mismatch", "not_reported",
]
EventLinkReason = Literal["matched", "no_game", "ambiguous", "missing_start", "start_mismatch"]


@dataclass(frozen=True)
class ContextPlayerCandidate:
    player_id: int
    sport: str
    name: str
    team: str | None
    position: str | None


@dataclass(frozen=True)
class ContextGameCandidate:
    game_id: int
    sport: str
    game_type: str
    away_team: str
    home_team: str
    start_utc: datetime | None


@dataclass(frozen=True)
class PlayerLink:
    player_id: int | None
    reason: PlayerLinkReason


@dataclass(frozen=True)
class EventLink:
    game_id: int | None
    reason: EventLinkReason


def _name_key(name: str) -> str | None:
    tokens = re.sub(r"[^a-z\s]", "", fold_name(name).casefold()).split()
    if len(tokens) < 2 or len(tokens[0]) < 2:
        return None
    return " ".join(tokens)


def index_context_players(
    candidates: Sequence[ContextPlayerCandidate],
) -> dict[str, list[ContextPlayerCandidate]]:
    result: dict[str, list[ContextPlayerCandidate]] = {}
    for candidate in candidates:
        key = _name_key(candidate.name)
        if candidate.sport == "nhl" and key is not None:
            result.setdefault(key, []).append(candidate)
    return result


def resolve_context_player(
    name: str | None, team: str | None,
    candidates: Mapping[str, Sequence[ContextPlayerCandidate]], *, goalie: bool = False,
    team_mismatch: bool = False, source_position: str | None = None,
) -> PlayerLink:
    if name is None:
        return PlayerLink(None, "not_reported")
    code = espn_nhl_team_code(team)
    if code is None:
        return PlayerLink(None, "missing_team")
    if team_mismatch:
        return PlayerLink(None, "team_mismatch")
    key = _name_key(name)
    matching = [row for row in candidates.get(key, ()) if row.sport == "nhl"] if key else []
    if not matching:
        return PlayerLink(None, "no_candidate")
    if code not in ESPN_NHL_TEAMS.values():
        return PlayerLink(None, "team_mismatch")
    same_team = [row for row in matching if espn_nhl_team_code(row.team) == code]
    if not same_team:
        return PlayerLink(None, "team_mismatch")
    if len(same_team) != 1:
        return PlayerLink(None, "ambiguous")
    player = same_team[0]
    if goalie and (player.position != "G" or source_position not in (None, "G")):
        return PlayerLink(None, "position_mismatch")
    return PlayerLink(player.player_id, "matched")


def resolve_context_injury(
    injury: NhlInjuryEntry, candidates: Mapping[str, Sequence[ContextPlayerCandidate]],
) -> PlayerLink:
    return resolve_context_player(
        injury.player_name, injury.team_code, candidates, team_mismatch=injury.team_mismatch,
    )


def resolve_context_goalie(
    observation: NhlGoalieObservation, candidates: Mapping[str, Sequence[ContextPlayerCandidate]],
) -> PlayerLink:
    return resolve_context_player(
        observation.player_name, observation.team_code, candidates, goalie=True,
        team_mismatch=observation.team_mismatch, source_position=observation.source_position,
    )


def resolve_context_event(
    away_team: str, home_team: str, start_utc: datetime | None,
    candidates: Sequence[ContextGameCandidate], *, time_valid: bool = True,
) -> EventLink:
    if start_utc is None or not time_valid:
        return EventLink(None, "missing_start")
    if start_utc.utcoffset() is None:
        raise ValueError("context event start must be timezone-aware")
    away, home = espn_nhl_team_code(away_team), espn_nhl_team_code(home_team)
    if away == home or away not in ESPN_NHL_TEAMS.values() or home not in ESPN_NHL_TEAMS.values():
        return EventLink(None, "no_game")
    matching = [
        row for row in candidates if row.sport == "nhl" and row.game_type in ("REG", "PST")
        and espn_nhl_team_code(row.away_team) == away and espn_nhl_team_code(row.home_team) == home
    ]
    if not matching:
        return EventLink(None, "no_game")
    eligible = []
    for row in matching:
        if row.start_utc is None:
            continue
        if row.start_utc.utcoffset() is None:
            raise ValueError("stored game start must be timezone-aware")
        if abs(row.start_utc - start_utc) <= timedelta(minutes=60):
            eligible.append(row)
    if len(eligible) > 1:
        return EventLink(None, "ambiguous")
    if eligible:
        return EventLink(eligible[0].game_id, "matched")
    return EventLink(None, "missing_start" if all(row.start_utc is None for row in matching) else "start_mismatch")
