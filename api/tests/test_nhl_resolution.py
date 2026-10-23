from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.core.nfl_names import provider_name_key
from app.core.nfl_resolution import PlayerCandidate, Resolution, resolve_player
from app.core.nhl_names import fold_name, nhl_team_code
from app.core.nhl_resolution import index_nhl_candidates, resolve_nhl_line

GAME_DAY = date(2026, 10, 23)
START = datetime(2026, 10, 24, 1, tzinfo=timezone.utc)
GAMES = {("TBL", GAME_DAY): 100, ("COL", GAME_DAY): 100, ("CHI", GAME_DAY): 200}
CANDIDATES = index_nhl_candidates([
    PlayerCandidate(1, "Brandon Hagel", "TBL", "L"),
    PlayerCandidate(2, "Nathan MacKinnon", "COL", "C"),
    PlayerCandidate(3, "Andrei Vasilevskiy", "TBL", "G"),
    PlayerCandidate(4, "Artturi Lehkonen", "COL", "L"),
    PlayerCandidate(5, "Seth Jones", "FLA", "D"),
    PlayerCandidate(6, "Sam Jones", "CHI", "C"),
    PlayerCandidate(7, "Martin Nečas", "COL", "C"),
])


@pytest.mark.parametrize(("provider", "expected"), [
    ("TB", "TBL"), (" tb ", "TBL"), ("TBL", "TBL"),
    *[(code, code) for code in ("ANA", "BUF", "CHI", "COL", "MTL", "NSH", "PHI", "PIT", "WSH")],
    ("ARI", "ARI"), ("UTA", "UTA"), ("UNKNOWN", "UNKNOWN"),
    ("COL/TB", "COL/TB"), ("", None), ("  ", None), (None, None),
])
def test_team_codes_only_map_observed_variants(provider: str | None, expected: str | None) -> None:
    assert nhl_team_code(provider) == expected


def test_team_alias_links_to_nhl_player_and_game() -> None:
    result, game = resolve_nhl_line("Brandon Hagel", "TB", START, CANDIDATES, GAMES)
    assert (result.player_id, game) == (1, 100)


def test_accented_provider_name_matches_ascii_candidate() -> None:
    result, _ = resolve_nhl_line("Artturi Lehkönen", "COL", START, CANDIDATES, GAMES)
    assert result.player_id == 4


def test_ascii_provider_name_matches_accented_candidate() -> None:
    result, _ = resolve_nhl_line("Martin Necas", "COL", START, CANDIDATES, GAMES)
    assert result.player_id == 7


def test_folded_alias_key_overrides_missing_candidate() -> None:
    alias_key = provider_name_key(fold_name("Alternate Nämé"))
    assert alias_key is not None
    result, game = resolve_nhl_line(
        "Alternate Nämé", "TB", START, CANDIDATES, GAMES, {alias_key: 3},
    )
    assert (result.player_id, result.reason, game) == (3, Resolution.ALIAS, 100)


def test_full_name_separates_shared_initial_and_surname() -> None:
    result, _ = resolve_nhl_line("Seth Jones", "FLA", START, CANDIDATES, GAMES)
    assert (result.player_id, result.reason) == (5, Resolution.FULL_NAME)


def test_provider_forward_label_cannot_reject_nhl_center_or_wing() -> None:
    assert resolve_player("S. Jones", "CHI", "F", CANDIDATES).reason is Resolution.CONTRADICTED
    result, game = resolve_nhl_line("S. Jones", "CHI", START, CANDIDATES, GAMES)
    assert (result.player_id, result.reason, game) == (6, Resolution.TEAM_TIEBREAK, 200)


def test_ambiguous_initial_without_team_stays_unlinked() -> None:
    result, game = resolve_nhl_line("S. Jones", None, START, CANDIDATES, GAMES)
    assert (result.player_id, result.reason, game) == (None, Resolution.AMBIGUOUS, None)


def test_ambiguity_is_not_resolved_by_guessing_an_unknown_team() -> None:
    result, game = resolve_nhl_line("S. Jones", "UNKNOWN", START, CANDIDATES, GAMES)
    assert (result.player_id, result.reason, game) == (None, Resolution.AMBIGUOUS, None)


def test_conflicting_first_name_and_team_stays_unlinked() -> None:
    result, game = resolve_nhl_line("Brian Hagel", "CHI", START, CANDIDATES, GAMES)
    assert (result.player_id, result.reason, game) == (None, Resolution.NAME_TEAM_CONFLICT, 200)


def test_missing_roster_player_does_not_prevent_game_linkage() -> None:
    result, game = resolve_nhl_line("Unknown Rookie", "TB", START, CANDIDATES, GAMES)
    assert (result.player_id, result.reason, game) == (None, Resolution.NO_CANDIDATE, 100)


@pytest.mark.parametrize("name", ["", " ", "Bedard"])
def test_unkeyable_name_retains_game_linkage(name: str) -> None:
    result, game = resolve_nhl_line(name, "CHI", START, CANDIDATES, GAMES)
    assert (result.player_id, result.reason, game) == (None, Resolution.UNKEYABLE_NAME, 200)


@pytest.mark.parametrize(("team", "start"), [
    (None, START), ("", START), ("UNKNOWN", START), ("TB", None),
    ("TB", datetime(2026, 11, 1, tzinfo=timezone.utc)),
])
def test_missing_game_inputs_do_not_prevent_player_linkage(team: str | None, start: datetime | None) -> None:
    result, game = resolve_nhl_line("Andrei Vasilevskiy", team, start, CANDIDATES, GAMES)
    assert (result.player_id, game) == (3, None)


@pytest.mark.parametrize("start", [
    START,
    datetime(2026, 10, 23, 21, tzinfo=ZoneInfo("America/New_York")),
    datetime(2026, 10, 23, 17, tzinfo=timezone.utc),
])
def test_utc_and_eastern_start_times_find_the_local_game_day(start: datetime) -> None:
    _, game = resolve_nhl_line("Brandon Hagel", "TB", start, CANDIDATES, GAMES)
    assert game == 100


def test_arizona_and_utah_remain_separate_teams() -> None:
    games = {("ARI", GAME_DAY): 300, ("UTA", GAME_DAY): 400}
    for team, expected in (("ARI", 300), ("UTA", 400)):
        _, game = resolve_nhl_line("Unknown Rookie", team, START, {}, games)
        assert game == expected


def test_indexing_folds_names_without_mutating_candidates() -> None:
    candidate = PlayerCandidate(7, "Martin Nečas", "COL", "C")
    index = index_nhl_candidates([candidate])
    assert index["m.necas"][0].name == "Martin Necas"
    assert candidate.name == "Martin Nečas"
