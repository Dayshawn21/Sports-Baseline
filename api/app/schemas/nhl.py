"""Stored NHL market and line-only display contracts."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.nhl_context_snapshots import Freshness
from app.core.nhl_odds import NhlBook
from app.nhl.markets import NhlLineOnlyMarket
from app.schemas.nhl_context import NhlGameContextSchema, NhlGoalieContext, NhlInjurySchema


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class NhlMoneylineSchema(_CamelModel):
    book: NhlBook
    home_odds: int
    away_odds: int
    home_win_probability: float = Field(ge=0, le=1)
    fetched_at: AwareDatetime


class NhlSpreadSchema(_CamelModel):
    book: NhlBook
    home_line: float
    home_odds: int
    away_odds: int
    fetched_at: AwareDatetime


class NhlTotalSchema(_CamelModel):
    book: NhlBook
    line: float
    over_odds: int
    under_odds: int
    fetched_at: AwareDatetime


class NhlLineMoveSchema(_CamelModel):
    market: Literal["spread", "total"]
    book: NhlBook
    open_line: float
    current_line: float
    open_fetched_at: AwareDatetime
    current_fetched_at: AwareDatetime


class NhlLineStepSchema(_CamelModel):
    fetched_at: AwareDatetime
    line: float


class NhlLineHistorySchema(_CamelModel):
    market: Literal["spread", "total"]
    book: NhlBook
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
    context: NhlGameContextSchema


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


class NhlPropBoardGameSchema(_CamelModel):
    game_id: int
    away_team: str
    home_team: str
    start_utc: AwareDatetime | None
    status: str
    lines: list[NhlLineOnlyLineSchema]


class NhlPropBoardResponse(_CamelModel):
    date: dt.date
    previous_date: dt.date | None
    next_date: dt.date | None
    games: list[NhlPropBoardGameSchema]


class NhlPlayerLineSchema(_CamelModel):
    line: float
    odds_type: Literal["standard", "demon", "goblin"]
    fetched_at: AwareDatetime


class NhlPlayerGameSchema(_CamelModel):
    """One played game's value; null when the box score left the stat unloaded, never zero."""
    game_date: dt.date
    opponent: str | None
    value: float | None


class NhlPlayerMarketSchema(_CamelModel):
    """Stored lines with recent results. Goalie markets count started games only."""
    market: NhlLineOnlyMarket
    lines: list[NhlPlayerLineSchema]
    recent: list[NhlPlayerGameSchema]
    opponent_games: list[NhlPlayerGameSchema]


class NhlPlayerGameRefSchema(_CamelModel):
    game_id: int
    game_type: Literal["REG", "PST"]
    away_team: str
    home_team: str
    start_utc: AwareDatetime | None
    status: str


class NhlPlayerInjurySchema(_CamelModel):
    fetched_at: AwareDatetime | None = None
    source_timestamp: AwareDatetime | None = None
    freshness: Freshness = "unavailable"
    entry: NhlInjurySchema | None = None


class NhlPlayerPropsResponse(_CamelModel):
    player_id: int
    name: str
    position: str | None
    team: str | None
    date: dt.date
    game: NhlPlayerGameRefSchema | None
    opponent: str | None
    injury: NhlPlayerInjurySchema
    goalies: NhlGoalieContext | None
    markets: list[NhlPlayerMarketSchema]
