from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.core.nhl_context_resolution import (
    ContextGameCandidate, ContextPlayerCandidate, index_context_players,
    resolve_context_event, resolve_context_goalie, resolve_context_injury, resolve_context_player,
)
from app.core.nhl_context import NhlGoalieObservation, NhlInjuryEntry

START = datetime(2026, 10, 24, 23, tzinfo=timezone.utc)
PLAYER = ContextPlayerCandidate(1, "nhl", "Andrei Vasilevskiy", "TBL", "G")
GAME = ContextGameCandidate(10, "nhl", "REG", "TBL", "UTA", START)


@pytest.mark.parametrize("name,stored", [
    ("Andrei Vasilevskiy", "Andrei Vasilevskiy"),
    ("Martin Ne\u010das", "Martin Necas"), ("Ryan O'Reilly", "Ryan OReilly"),
    (" PIERRE-LUC   DUBOIS ", "Pierre-Luc Dubois"),
])
def test_full_name_accent_punctuation_and_team_alias_match(name: str, stored: str) -> None:
    index = index_context_players([replace(PLAYER, name=stored)])
    result = resolve_context_player(name, "TB", index)
    assert (result.player_id, result.reason) == (1, "matched")


@pytest.mark.parametrize("name", ["A. Vasilevskiy", "Andrey Vasilevskiy", "Vasilevskiy", "", "  "])
def test_no_initial_fuzzy_or_missing_name_guess(name: str) -> None:
    result = resolve_context_player(name, "TB", index_context_players([PLAYER]))
    assert (result.player_id, result.reason) == (None, "no_candidate")


@pytest.mark.parametrize("team,reason", [(None, "missing_team"), ("", "missing_team"), ("CHI", "team_mismatch")])
def test_unique_full_name_cannot_override_team(team: str | None, reason: str) -> None:
    result = resolve_context_player(PLAYER.name, team, index_context_players([PLAYER]))
    assert result.player_id is None and result.reason == reason


def test_absent_announcement_and_nested_team_mismatch_are_distinct() -> None:
    index = index_context_players([PLAYER])
    assert resolve_context_player(None, "TB", index).reason == "not_reported"
    assert resolve_context_player(PLAYER.name, "TB", index, team_mismatch=True).reason == "team_mismatch"


def test_same_name_and_team_ambiguity_is_not_broken_by_position() -> None:
    index = index_context_players([PLAYER, replace(PLAYER, player_id=2, position="C")])
    result = resolve_context_player(PLAYER.name, "TB", index, goalie=True)
    assert (result.player_id, result.reason) == (None, "ambiguous")


def test_team_can_separate_exact_full_name_candidates() -> None:
    index = index_context_players([PLAYER, replace(PLAYER, player_id=2, team="CHI")])
    assert resolve_context_player(PLAYER.name, "TB", index).player_id == 1


@pytest.mark.parametrize("position,source_position", [("C", "G"), (None, "G"), ("G", "C")])
def test_goalie_requires_stored_goalie_position_without_source_contradiction(
    position: str | None, source_position: str | None,
) -> None:
    index = index_context_players([replace(PLAYER, position=position)])
    result = resolve_context_player(PLAYER.name, "TB", index, goalie=True, source_position=source_position)
    assert (result.player_id, result.reason) == (None, "position_mismatch")


def test_source_goalie_position_can_be_absent_but_candidate_must_be_goalie() -> None:
    result = resolve_context_player(PLAYER.name, "TB", index_context_players([PLAYER]), goalie=True)
    assert result.player_id == 1


def test_wrong_sport_candidates_are_excluded_even_from_prebuilt_index() -> None:
    wrong = replace(PLAYER, sport="nba")
    assert index_context_players([wrong]) == {}
    result = resolve_context_player(PLAYER.name, "TB", {"andrei vasilevskiy": [wrong]})
    assert result.reason == "no_candidate"


def test_unknown_team_cannot_be_accepted_from_a_matching_candidate() -> None:
    index = index_context_players([replace(PLAYER, team="UNKNOWN")])
    assert resolve_context_player(PLAYER.name, "UNKNOWN", index).reason == "team_mismatch"


def test_observation_wrappers_preserve_mismatch_and_position_vetoes() -> None:
    injury = NhlInjuryEntry("20", "TBL", "123", PLAYER.name, "Out", None, None, None, "4")
    goalie = NhlGoalieObservation(
        "456", START.date(), START, True, "UTA", "TBL", "20", "TBL",
        "123", PLAYER.name, "confirmed", "Confirmed", "4", "G",
    )
    index = index_context_players([PLAYER])
    assert resolve_context_injury(injury, index).reason == "team_mismatch"
    assert resolve_context_goalie(goalie, index).reason == "team_mismatch"
    assert resolve_context_goalie(replace(goalie, athlete_team_id="20", source_position="C"), index).reason == "position_mismatch"
    assert resolve_context_goalie(replace(goalie, athlete_team_id="20"), index).player_id == 1


@pytest.mark.parametrize("offset", [-60, 0, 60])
@pytest.mark.parametrize("kind", ["REG", "PST"])
def test_event_matching_uses_ordered_teams_aware_start_and_inclusive_boundary(offset: int, kind: str) -> None:
    result = resolve_context_event(
        "TB", "UTAH", START, [replace(GAME, start_utc=START + timedelta(minutes=offset), game_type=kind)],
    )
    assert (result.game_id, result.reason) == (10, "matched")


@pytest.mark.parametrize("offset", [-3601, 3601])
def test_outside_time_boundary_is_unresolved(offset: int) -> None:
    result = resolve_context_event("TB", "UTA", START, [replace(GAME, start_utc=START + timedelta(seconds=offset))])
    assert (result.game_id, result.reason) == (None, "start_mismatch")


@pytest.mark.parametrize("candidate", [
    replace(GAME, sport="nba"), replace(GAME, game_type="PRE"),
    replace(GAME, away_team="UTA", home_team="TBL"), replace(GAME, home_team="CHI"),
])
def test_wrong_sport_type_or_team_orientation_never_matches(candidate: ContextGameCandidate) -> None:
    assert resolve_context_event("TB", "UTA", START, [candidate]).reason == "no_game"


def test_ambiguous_events_are_not_resolved_to_nearest_start() -> None:
    candidates = [GAME, replace(GAME, game_id=11, start_utc=START + timedelta(minutes=30))]
    result = resolve_context_event("TB", "UTA", START, candidates)
    assert (result.game_id, result.reason) == (None, "ambiguous")


def test_unknown_or_repeated_event_teams_never_match() -> None:
    assert resolve_context_event("UNKNOWN", "UTA", START, [replace(GAME, away_team="UNKNOWN")]).reason == "no_game"
    assert resolve_context_event("UTA", "UTA", START, [replace(GAME, away_team="UTA")]).reason == "no_game"


def test_missing_or_invalid_starts_stay_unresolved() -> None:
    assert resolve_context_event("TB", "UTA", None, [GAME]).reason == "missing_start"
    assert resolve_context_event("TB", "UTA", START, [GAME], time_valid=False).reason == "missing_start"
    assert resolve_context_event("TB", "UTA", START, [replace(GAME, start_utc=None)]).reason == "missing_start"
    for source, candidate in [(START.replace(tzinfo=None), GAME), (START, replace(GAME, start_utc=START.replace(tzinfo=None)))]:
        with pytest.raises(ValueError, match="timezone-aware"):
            resolve_context_event("TB", "UTA", source, [candidate])
