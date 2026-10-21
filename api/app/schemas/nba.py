from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.schemas.prop_ranking import PropRankingResponse


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class NbaRecordSchema(_CamelModel):
    wins: int
    losses: int


class NbaMoneylineSchema(_CamelModel):
    book: str
    home_odds: int
    away_odds: int
    # The stored de-vigged probability of the home side (item 20d).
    home_win_probability: float
    fetched_at: dt.datetime


class NbaSpreadSchema(_CamelModel):
    book: str
    # Book sign: negative means the home team is favored.
    home_line: float
    home_odds: int
    away_odds: int
    fetched_at: dt.datetime


class NbaTotalSchema(_CamelModel):
    book: str
    line: float
    over_odds: int
    under_odds: int
    fetched_at: dt.datetime


class NbaLineMoveSchema(_CamelModel):
    market: Literal["spread", "total"]
    book: str
    open_line: float
    current_line: float
    open_fetched_at: dt.datetime
    current_fetched_at: dt.datetime


class NbaSlateGameSchema(_CamelModel):
    """One NBA game as the slate shows it; the game page extends this shape (item 20e1)."""
    game_id: int
    season: int
    week: int | None
    game_type: Literal["REG", "PIN", "PST"]
    game_date: dt.date
    start_utc: dt.datetime | None
    status: str
    away_team: str
    home_team: str
    away_team_name: str
    home_team_name: str
    away_score: int | None
    home_score: int | None
    away_record: NbaRecordSchema
    home_record: NbaRecordSchema
    prop_line_count: int
    # Each market takes its own latest row, DraftKings first, so books can differ.
    moneyline: NbaMoneylineSchema | None
    spread: NbaSpreadSchema | None
    total: NbaTotalSchema | None
    line_movement: list[NbaLineMoveSchema]


class NbaLineStepSchema(_CamelModel):
    fetched_at: dt.datetime
    line: float


class NbaLineHistorySchema(_CamelModel):
    market: Literal["spread", "total"]
    book: str
    # A spread line is the home spread in book sign, as `NbaSpreadSchema.home_line`.
    steps: list[NbaLineStepSchema]


class NbaGameDetailResponse(NbaSlateGameSchema):
    """The game page's anchor; later game-level display context extends it."""
    line_history: list[NbaLineHistorySchema]


class NbaLineOnlyRecentSchema(_CamelModel):
    game_date: dt.date
    opponent: str | None
    # NULL when a stat the market needs was not loaded for that game, never zero.
    value: float | None


class NbaLineOnlyLineSchema(_CamelModel):
    player_id: int
    player_name: str
    position: str | None
    # ESPN code, as the game's teams; null when PrizePicks sent none.
    team: str | None
    market: str
    odds_type: str | None
    line: float
    fetched_at: dt.datetime
    # Last played games before this one, newest first.
    recent: list[NbaLineOnlyRecentSchema]


class NbaLineOnlyPropsResponse(_CamelModel):
    """Every NBA market is line-only until 20g: never a projection, edge or rank."""
    game_id: int
    lines: list[NbaLineOnlyLineSchema]


class NbaPropLineSchema(NbaLineOnlyLineSchema):
    # Null means not served (the flags say why), never zero.
    projection: float | None
    games_in_sample: int
    prior_minutes: float | None
    # Projection minus line, gray: "gap", not "edge", until 20g4 adopts a slice.
    gap: float | None
    p_over: float | None
    p_under: float | None
    over_probability_version: str | None
    flags: list[Literal["few_prior_games", "low_minutes", "no_over_probability", "integer_line"]]


class NbaPropsResponse(_CamelModel):
    """Modelled NBA lines with the reference projection: never a pick, rank or signal color (20g2)."""
    game_id: int
    model_version: str
    lines: list[NbaPropLineSchema]


class NbaPropBoardGameSchema(_CamelModel):
    game_id: int
    away_team: str
    home_team: str
    start_utc: dt.datetime | None
    status: str
    lines: list[NbaPropLineSchema]
    line_only_lines: list[NbaLineOnlyLineSchema]


class NbaPropBoardResponse(_CamelModel):
    date: dt.date
    previous_date: dt.date | None
    next_date: dt.date | None
    model_version: str
    games: list[NbaPropBoardGameSchema]


class NbaSlateResponse(_CamelModel):
    date: dt.date
    previous_date: dt.date | None
    next_date: dt.date | None
    games: list[NbaSlateGameSchema]


class NbaSlateGapSchema(_CamelModel):
    game_id: int
    away_team: str
    home_team: str
    player_id: int
    player_name: str
    market: str
    line: float
    projection: float
    gap: float
    gap_share: float


class NbaSlateGapsResponse(_CamelModel):
    """The slate digest's largest gaps (38c2): gray reference, never a pick; the one sorted NBA gap."""
    date: dt.date
    model_version: str
    items: list[NbaSlateGapSchema]


class NbaModelRankingResponse(PropRankingResponse):
    """27i's rule on NBA's frozen pre-tip rows (20g4), in NFL's 27j shape; a later NBA adoption item reads it."""
