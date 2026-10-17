"""Decide which NFL player a provider prop line refers to.

Pure: takes a provider name plus whatever the provider said about team and
position, and a pre-indexed candidate list. No DB, no I/O.

The guiding rule is that a wrong link is worse than no link. A mismatched player
produces a confident, plausible, wrong edge, which is harder to notice than a
blank row. So every path that cannot decide returns a reason instead of a guess.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.core.nfl_names import canonical_team_code, full_name_key, provider_name_key


class Resolution(StrEnum):
    ALIAS = "alias"
    UNIQUE_NAME = "unique_name"
    FULL_NAME = "full_name"
    POSITION_TIEBREAK = "position_tiebreak"
    TEAM_TIEBREAK = "team_tiebreak"
    UNKEYABLE_NAME = "unkeyable_name"
    NO_CANDIDATE = "no_candidate"
    AMBIGUOUS = "ambiguous"
    # Position disagreed with every candidate. Only position earns this: it is
    # stable across seasons, whereas a stale team is not evidence of anything.
    CONTRADICTED = "contradicted"
    # The only candidate differs in both full name and team: a different,
    # unstored player who shares the initial and surname.
    NAME_TEAM_CONFLICT = "name_team_conflict"


MATCHED_REASONS = frozenset({
    Resolution.ALIAS, Resolution.UNIQUE_NAME, Resolution.FULL_NAME,
    Resolution.POSITION_TIEBREAK, Resolution.TEAM_TIEBREAK,
})


@dataclass(frozen=True)
class PlayerCandidate:
    player_id: int
    name: str
    team: str | None = None
    position: str | None = None


@dataclass(frozen=True)
class ResolutionResult:
    player_id: int | None
    reason: Resolution

    @property
    def matched(self) -> bool:
        return self.player_id is not None


def index_candidates(candidates: Sequence[PlayerCandidate]) -> dict[str, list[PlayerCandidate]]:
    """Group candidates by name key so resolution does not rescan the roster.

    Roster names are keyed as full names: stats ingest stores
    `player_display_name`, so "A.J. Brown" is a first name, not "A." plus "J. Brown".
    """
    index: dict[str, list[PlayerCandidate]] = {}
    for candidate in candidates:
        key = provider_name_key(candidate.name)
        if key:
            index.setdefault(key, []).append(candidate)
    return index


def _narrow(
    candidates: Sequence[PlayerCandidate],
    value: str | None,
    attribute: str,
) -> Sequence[PlayerCandidate] | None:
    """Filter by one attribute, or None when the filter cannot be trusted.

    An empty result means the provider's value contradicts every candidate, which
    is evidence of a different player rather than grounds to ignore the filter.
    """
    if not value:
        return candidates
    matches = [c for c in candidates if (getattr(c, attribute) or "").upper() == value.upper()]
    return matches or None


def _name_and_team_conflict(provider_name: str, provider_team: str | None, candidate: PlayerCandidate) -> bool:
    """A lone initial-plus-surname match that disagrees on both first name and team.

    Either disagreement alone is common and harmless (nicknames such as "Joshua"
    for "Josh"; a stale or traded team), so neither vetoes by itself. Together they
    describe a different player who shares a surname and initial and is simply not
    stored, e.g. "Camden Brown" (DAL) matching the only C. Brown, Chase (CIN).
    """
    provider_full, candidate_full = full_name_key(provider_name), full_name_key(candidate.name)
    provider_code, candidate_code = canonical_team_code(provider_team), canonical_team_code(candidate.team)
    if not (provider_full and candidate_full and provider_code and candidate_code):
        return False
    return provider_full != candidate_full and provider_code != candidate_code


def resolve_player(
    provider_name: str,
    provider_team: str | None,
    provider_position: str | None,
    candidate_index: Mapping[str, Sequence[PlayerCandidate]],
    aliases: Mapping[str, int] | None = None,
) -> ResolutionResult:
    key = provider_name_key(provider_name)
    if key is None:
        return ResolutionResult(None, Resolution.UNKEYABLE_NAME)

    if aliases and key in aliases:
        return ResolutionResult(aliases[key], Resolution.ALIAS)

    candidates = candidate_index.get(key) or []
    if not candidates:
        return ResolutionResult(None, Resolution.NO_CANDIDATE)
    if len(candidates) == 1:
        if _name_and_team_conflict(provider_name, provider_team, candidates[0]):
            return ResolutionResult(None, Resolution.NAME_TEAM_CONFLICT)
        return ResolutionResult(candidates[0].player_id, Resolution.UNIQUE_NAME)

    # An exact full name narrows a shared initial-plus-surname key. No exact match
    # keeps every candidate, so a nickname ("Chig" for "Chigoziem") still resolves.
    provider_full = full_name_key(provider_name)
    exact = [c for c in candidates if provider_full and full_name_key(c.name) == provider_full]
    if len(exact) == 1:
        return ResolutionResult(exact[0].player_id, Resolution.FULL_NAME)
    if exact:
        candidates = exact

    # Position before team: a receiver stays a receiver, but sport_players.team_id is
    # last-write-wins from the loaded season and goes stale as players move.
    by_position = _narrow(candidates, provider_position, "position")
    if by_position is None:
        return ResolutionResult(None, Resolution.CONTRADICTED)
    if len(by_position) == 1:
        return ResolutionResult(by_position[0].player_id, Resolution.POSITION_TIEBREAK)

    # Team can narrow a tie but never veto one. sport_players.team_id reflects the
    # loaded season, so a player who has since moved legitimately mismatches the
    # provider's current team; that is stale data, not a different player.
    by_team = _narrow(by_position, canonical_team_code(provider_team), "team")
    if by_team is None:
        return ResolutionResult(None, Resolution.AMBIGUOUS)
    if len(by_team) == 1:
        return ResolutionResult(by_team[0].player_id, Resolution.TEAM_TIEBREAK)

    return ResolutionResult(None, Resolution.AMBIGUOUS)


def find_game_id(
    team: str | None,
    start_time: dt.datetime | None,
    game_index: Mapping[tuple[str, dt.date], int],
) -> int | None:
    """Locate the game a prop line belongs to, from its team and kickoff.

    Checks the UTC date and the day before, because a US evening kickoff falls on
    the next UTC day: a Sunday 20:15 ET game is stored as the Monday 00:15 UTC.
    `sport_games.game_date` is the local game day, so the earlier date is the match.

    Deliberately not matched on `sport_games.start_utc`: team and game date remain
    more stable across provider schedule updates than an exact kickoff timestamp.
    """
    code = canonical_team_code(team)
    if not code or start_time is None:
        return None
    utc_date = start_time.astimezone(dt.timezone.utc).date()
    for candidate_date in (utc_date, utc_date - dt.timedelta(days=1)):
        game_id = game_index.get((code, candidate_date))
        if game_id is not None:
            return game_id
    return None
