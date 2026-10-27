"""Name lookup for Ask Lineform's `find` tool (47a): fold accents and case,
then rank candidates by how closely the query matches."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

Kind = Literal["player", "team", "game", "tournament"]

MAX_MATCHES = 10


@dataclass(frozen=True)
class Candidate:
    kind: Kind
    name: str
    url: str
    entity_id: int | None = None
    game_id: int | None = None


def fold(text: str) -> str:
    """'Egor Dëmin' and 'egor demin' fold to the same key."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", plain.lower()).split())


def _score(query: str, name: str) -> int:
    if name == query:
        return 3
    words = name.split()
    if all(any(word.startswith(part) for word in words) for part in query.split()):
        return 2
    return 1 if query in name else 0


def match_candidates(query: str, candidates: Iterable[Candidate]) -> list[Candidate]:
    """Best matches first; one entry per entity, ties by name."""
    needle = fold(query)
    if not needle:
        return []
    scored: dict[tuple[Kind, str, int | None], tuple[int, Candidate]] = {}
    for candidate in candidates:
        score = _score(needle, fold(candidate.name))
        key = (candidate.kind, fold(candidate.name), candidate.entity_id)
        if score and (key not in scored or scored[key][0] < score):
            scored[key] = (score, candidate)
    ranked = sorted(scored.values(), key=lambda pair: (-pair[0], pair[1].name))
    return [candidate for _, candidate in ranked[:MAX_MATCHES]]
