"""Stored NHL market and line-only display contracts."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.nhl.markets import NhlLineOnlyMarket


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class NhlMoneylineSchema(_CamelModel):
    book: Literal["draftkings", "bet365"]
    home_odds: int
    away_odds: int
    home_win_probability: float = Field(ge=0, le=1)
    fetched_at: AwareDatetime


class NhlSpreadSchema(_CamelModel):
    book: Literal["draftkings", "bet365"]
    home_line: float
    home_odds: int
    away_odds: int
    fetched_at: AwareDatetime


class NhlTotalSchema(_CamelModel):
    book: Literal["draftkings", "bet365"]
    line: float
    over_odds: int
    under_odds: int
    fetched_at: AwareDatetime


class NhlLineMoveSchema(_CamelModel):
    market: Literal["spread", "total"]
    book: Literal["draftkings", "bet365"]
    open_line: float
    current_line: float
    open_fetched_at: AwareDatetime
    current_fetched_at: AwareDatetime


class NhlLineStepSchema(_CamelModel):
    fetched_at: AwareDatetime
    line: float


class NhlLineHistorySchema(_CamelModel):
    market: Literal["spread", "total"]
    book: Literal["draftkings", "bet365"]
    steps: list[NhlLineStepSchema]


class NhlSlateGameSchema(_CamelModel):
    game_id: int
    season: int
    week: int | None
    game_type: Literal["REG", "PST"]
    game_date: dt.date
    start_utc: AwareDatetime | None
    status: str
    away_team: str
    home_team: str
    away_team_name: str
    home_team_name: str
    away_score: int | None
    home_score: int | None
    end_period: Literal["REG", "OT", "SO"] | None
    prop_line_count: int
    moneyline: NhlMoneylineSchema | None
    spread: NhlSpreadSchema | None
    total: NhlTotalSchema | None
    line_movement: list[NhlLineMoveSchema] = Field(default_factory=list)


class NhlSlateResponse(_CamelModel):
    date: dt.date
    previous_date: dt.date | None
    next_date: dt.date | None
    games: list[NhlSlateGameSchema]


class NhlGameDetailResponse(NhlSlateGameSchema):
    line_history: list[NhlLineHistorySchema] = Field(default_factory=list)


class NhlLineOnlyLineSchema(_CamelModel):
    provider: Literal["prizepicks"]
    provider_prop_id: str
    player_id: int
    player_name: str
    position: str | None
    team: str | None
    market: NhlLineOnlyMarket
    odds_type: Literal["standard", "demon", "goblin"]
    line: float
    fetched_at: AwareDatetime


class NhlLineOnlyPropsResponse(_CamelModel):
    game_id: int
    lines: list[NhlLineOnlyLineSchema]
