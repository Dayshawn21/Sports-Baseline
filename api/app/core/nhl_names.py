"""Normalize PrizePicks names and team codes to NHL source values."""
from __future__ import annotations

import unicodedata


def nhl_team_code(code: str | None) -> str | None:
    if not code or not code.strip():
        return None
    upper = code.strip().upper()
    return "TBL" if upper == "TB" else upper


def fold_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    return "".join(char for char in decomposed if not unicodedata.combining(char))
