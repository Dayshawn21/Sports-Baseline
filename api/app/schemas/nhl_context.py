from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.nhl_context_resolution import PlayerLinkReason
from app.core.nhl_context_snapshots import Freshness


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class NhlInjurySchema(_CamelModel):
    espn_athlete_id: str
    player_id: int | None
    player_name: str
    team: str
    status: str
    detail: str | None
    source_updated_at: AwareDatetime | None
    return_date: str | None
    link_reason: PlayerLinkReason
    team_mismatch: bool


class _SourceContext(_CamelModel):
    source: Literal["ESPN"] = "ESPN"
    fetched_at: AwareDatetime | None = None
    source_timestamp: AwareDatetime | None = None
    freshness: Freshness = "unavailable"


class NhlInjuryContext(_SourceContext):
    away: list[NhlInjurySchema] = Field(default_factory=list)
    home: list[NhlInjurySchema] = Field(default_factory=list)


class NhlGoalieSide(_CamelModel):
    team: str
    espn_athlete_id: str | None = None
    player_id: int | None = None
    player_name: str | None = None
    status: Literal["expected", "confirmed", "unknown", "not_reported", "unavailable"] = "unavailable"
    raw_status: str | None = None
    link_reason: PlayerLinkReason | None = None


class NhlGoalieContext(_SourceContext):
    away: NhlGoalieSide
    home: NhlGoalieSide


class NhlGameContextSchema(_CamelModel):
    injuries: NhlInjuryContext
    goalies: NhlGoalieContext
