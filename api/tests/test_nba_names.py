import pytest

from app.core.nba_names import _TEAM_CODE_ALIASES, espn_team_code, fold_name

# `sport_teams.team_code` for NBA after the 20b load.
ESPN_CODES = {
    "ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GS", "HOU", "IND", "LAC", "LAL", "MEM",
    "MIA", "MIL", "MIN", "NO", "NY", "OKC", "ORL", "PHI", "PHX", "POR", "SA", "SAC", "TOR", "UTAH", "WSH",
}


@pytest.mark.parametrize(("code", "expected"), [
    ("NYK", "NY"), ("SAS", "SA"), ("GSW", "GS"), ("NOP", "NO"), ("UTA", "UTAH"), ("WAS", "WSH"),
    ("BOS", "BOS"), (" okc ", "OKC"), ("", None), ("  ", None), (None, None),
])
def test_espn_team_code(code: str | None, expected: str | None) -> None:
    assert espn_team_code(code) == expected


def test_every_alias_targets_a_stored_espn_code() -> None:
    assert set(_TEAM_CODE_ALIASES.values()) <= ESPN_CODES


@pytest.mark.parametrize(("name", "expected"), [
    ("Egor Dëmin", "Egor Demin"),
    ("Nikola Jokić", "Nikola Jokic"),
    ("Kristaps Porziņģis", "Kristaps Porzingis"),
    ("Jonas Valančiūnas", "Jonas Valanciunas"),
    ("Cade Cunningham", "Cade Cunningham"),
])
def test_fold_name(name: str, expected: str) -> None:
    assert fold_name(name) == expected
