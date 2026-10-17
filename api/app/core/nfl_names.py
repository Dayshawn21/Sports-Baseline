"""Normalize NFL player names from NFLverse and prop providers to one key.

NFLverse stores "A.St. Brown"; PrizePicks sends "Amon-Ra St. Brown". Both reduce
to "a.stbrown" so a line can be matched to a player.

The two sources get separate entry points rather than one auto-detecting function
because their shapes overlap: "A.St. Brown" (NFLverse) and "J.K. Dobbins"
(provider) both start with a letter and a period, but the surname is "St. Brown"
in the first and "Dobbins" in the second. The caller always knows which source it
holds, so asking it is safer than guessing.

The key is intentionally lossy: it drops the first name to a single initial,
because that is all NFLverse gives. It therefore cannot distinguish Jameson from
Javonte Williams, and callers must break those ties on other evidence.
"""
from __future__ import annotations

import re

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

# Provider team codes that differ from NFLverse's `sport_teams.team_code`. Only codes
# PrizePicks actually sends are listed; an unknown code is left alone so it fails
# visibly (no game) instead of being guessed into the wrong team.
_TEAM_CODE_ALIASES = {"JAC": "JAX", "LAR": "LA"}


def canonical_team_code(code: str | None) -> str | None:
    """A provider team code in NFLverse form, e.g. "JAC" -> "JAX"."""
    if not code or not code.strip():
        return None
    upper = code.strip().upper()
    return _TEAM_CODE_ALIASES.get(upper, upper)


def _letters(value: str) -> str:
    return re.sub(r"[^a-z]", "", value.lower())


def _key(initial: str, surname: str) -> str | None:
    initial, surname = _letters(initial)[:1], _letters(surname)
    return f"{initial}.{surname}" if initial and surname else None


def _drop_suffixes(tokens: list[str]) -> list[str]:
    while len(tokens) > 2 and _letters(tokens[-1]) in _SUFFIXES:
        tokens = tokens[:-1]
    return tokens


def provider_name_key(name: str) -> str | None:
    """Key a full name such as "Michael Pittman Jr." or "Amon-Ra St. Brown".

    Everything after the first token is the surname, so multi-word surnames like
    "St. Brown" survive; taking only the last token would reduce that to "Brown".
    """
    tokens = _drop_suffixes(name.split())
    if len(tokens) < 2:
        return None
    return _key(tokens[0], "".join(tokens[1:]))


def full_name_key(name: str) -> str | None:
    """Key a whole name, suffixes dropped, to tell apart players sharing an initial.

    `provider_name_key` cannot separate Bijan from Brian Robinson; this can.
    """
    tokens = _drop_suffixes(name.split())
    if len(tokens) < 2:
        return None
    return _letters("".join(tokens)) or None


def nflverse_name_key(name: str) -> str | None:
    """Key an NFLverse name such as "A.St. Brown" or "J.Smith-Njigba"."""
    initial, separator, surname = name.partition(".")
    if not separator:
        # Not the expected "X.Surname" shape; fall back to full-name handling.
        return provider_name_key(name)
    return _key(initial, surname)
