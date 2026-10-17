"""Bring PrizePicks NBA names and team codes into the form ESPN's rows use (item 20c).

Pure: no DB, no I/O.
"""
from __future__ import annotations

import unicodedata

# PrizePicks team codes that differ from ESPN's `sport_teams.team_code`. WAS has not
# been seen on a board yet; any other unknown code passes through, so it fails
# visibly (no game) instead of being guessed into the wrong team.
_TEAM_CODE_ALIASES = {"NYK": "NY", "SAS": "SA", "GSW": "GS", "NOP": "NO", "UTA": "UTAH", "WAS": "WSH"}


def espn_team_code(code: str | None) -> str | None:
    """A PrizePicks team code in ESPN form, e.g. "NYK" -> "NY"."""
    if not code or not code.strip():
        return None
    upper = code.strip().upper()
    return _TEAM_CODE_ALIASES.get(upper, upper)


def fold_name(name: str) -> str:
    """Strip diacritics: PrizePicks sends "Egor Dëmin", ESPN stores "Egor Demin".

    The name keys keep only a-z, so an unfolded "ë" would drop out and leave "dmin".
    """
    decomposed = unicodedata.normalize("NFKD", name)
    return "".join(char for char in decomposed if not unicodedata.combining(char))
