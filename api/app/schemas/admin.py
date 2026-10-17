from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AdminSessionResponse(_CamelModel):
    key_required: bool


class FlaggedPlayer(_CamelModel):
    player_id: int
    player_name: str
    tour: str
    flags: list[str]
    has_elo: bool
    has_stats: bool
    ta_slug: Optional[str]   # current DB value (None if not set)
    auto_slug: str            # computed _slug(player_name) — used for prefill in UI


class FlaggedPlayersResponse(_CamelModel):
    count: int
    players: list[FlaggedPlayer]


class FetchStatsRequest(_CamelModel):
    ta_slug: Optional[str] = None  # if provided, saves to DB then uses for fetch


class FetchStatsResponse(_CamelModel):
    success: bool
    player_name: str
    matches_found: int
    error: Optional[str]


class FetchEloRequest(_CamelModel):
    ta_name: Optional[str] = None  # TennisAbstract name override (if spelling differs)


class FetchEloResponse(_CamelModel):
    success: bool
    player_name: str
    elo: Optional[float]           # the ELO value found (None on failure)
    error: Optional[str]


class SetEloRequest(_CamelModel):
    elo: float
    elo_hard: Optional[float] = None
    elo_clay: Optional[float] = None
    elo_grass: Optional[float] = None


class SetEloResponse(_CamelModel):
    success: bool
    player_id: int
    player_name: str
