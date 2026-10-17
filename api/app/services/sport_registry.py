"""Which prop pipeline source serves each sport (17d).

Imports every sport's source, so the shared prop modules must never import this
one: `tests/test_sport_props_pipeline.py` keeps them free of NFL code.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping

from app.services.nba.prop_source import NbaPropSource
from app.services.nfl.prop_source import NflPropSource
from app.services.sport_props import SportPropSource

PROP_SOURCES: Mapping[str, Callable[[], SportPropSource]] = {
    "nfl": NflPropSource,
    "nba": NbaPropSource,
}


def prop_source(code: str) -> SportPropSource:
    try:
        factory = PROP_SOURCES[code]
    except KeyError:
        raise KeyError(f"No prop source for sport {code!r}; known: {sorted(PROP_SOURCES)}") from None
    return factory()
