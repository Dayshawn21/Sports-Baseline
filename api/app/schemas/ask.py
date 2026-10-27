"""Ask Lineform tool contracts (47a): one input model per tool, and the result
envelope every tool returns.

Each input model's JSON schema is the tool's `input_schema`, the only thing the
model knows about a tool besides its description. Inputs are validated here, in
our code, rather than with `strict: true`: strict schemas drop the `ge`/`le` and
length limits below, and a validation error goes back to the model as a message
it can correct.
"""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from app.core.ask_links import AskSport, BoardSport, PlayerSport
from app.nba.markets import NbaPropMarket

DESCRIPTION_LIMIT = 1200

_DATE = "Calendar date, YYYY-MM-DD. NBA dates are US Eastern. Omit for today."
_WEEK = "NFL regular-season week, 1-18. Omit for the current week."


class _ToolInput(BaseModel):
    # Unknown fields are rejected, so a misspelled argument is an error the
    # model sees, not a silently ignored value.
    model_config = ConfigDict(extra="forbid")


class _DatedInput(_ToolInput):
    date: dt.date | None = Field(default=None, description=_DATE)
    week: int | None = Field(default=None, ge=1, le=18, description=_WEEK)

    @model_validator(mode="after")
    def _period_fits_sport(self) -> _DatedInput:
        sport = getattr(self, "sport")
        if self.week is not None and sport != "nfl":
            raise ValueError("week applies to nfl only; use date for nba and tennis")
        if self.date is not None and sport == "nfl":
            raise ValueError("nfl slates are by week, not date; use week")
        return self


class GetSlateInput(_DatedInput):
    sport: AskSport
    tour: Literal["ATP", "WTA", "CHALLENGER"] | None = Field(
        default=None, description="Tennis only: limit to one tour."
    )

    @model_validator(mode="after")
    def _tour_is_tennis(self) -> GetSlateInput:
        if self.tour is not None and self.sport != "tennis":
            raise ValueError("tour applies to tennis only")
        return self


class GetTopPropsInput(_ToolInput):
    sport: BoardSport
    date: dt.date | None = Field(default=None, description=_DATE)
    market: str | None = Field(
        default=None,
        max_length=40,
        description=(
            "NBA: one of " + ", ".join(m.value for m in NbaPropMarket)
            + ". Tennis: text matched against the pick label, e.g. 'aces' or 'total games'."
        ),
    )
    limit: int = Field(default=5, ge=1, le=10, description="How many rows to return.")

    @model_validator(mode="after")
    def _known_nba_market(self) -> GetTopPropsInput:
        if self.sport == "nba" and self.market is not None and self.market not in set(NbaPropMarket):
            raise ValueError(f"unknown nba market {self.market!r}")
        return self


class GetGameDetailInput(_ToolInput):
    sport: AskSport
    game_id: int = Field(ge=1, description="The game id (tennis: match id) from get_slate, get_top_props or find.")
    player_id: int | None = Field(
        default=None, ge=1, description="NBA or NFL: return only this player's prop lines, every payout type."
    )

    @model_validator(mode="after")
    def _player_filter_has_props(self) -> GetGameDetailInput:
        if self.player_id is not None and self.sport == "tennis":
            raise ValueError("player_id applies to nba and nfl; use get_player for a tennis player")
        return self


class GetPlayerInput(_ToolInput):
    sport: PlayerSport
    player_id: int = Field(ge=1, description="The player id from find, get_game_detail or get_top_props.")


class GetModelTrackRecordInput(_ToolInput):
    sport: AskSport
    season: int | None = Field(
        default=None, ge=2023, le=2030, description="Season start year. Omit for the current season."
    )


class FindInput(_DatedInput):
    sport: AskSport
    query: str = Field(min_length=2, max_length=60, description="A player, team or tournament name, or part of one.")


class ToolResult(BaseModel):
    """What every tool returns to the model. Every row in `data` carries a
    `url` (the page it came from) and a `signal` (pick, reference_only or none)."""

    tool: str
    sport: str
    url: str | None
    as_of: dt.datetime
    note: str | None = None
    truncated: bool = False
    data: JsonValue = None


TOOL_INPUTS: dict[str, type[_ToolInput]] = {
    "get_slate": GetSlateInput,
    "get_top_props": GetTopPropsInput,
    "get_game_detail": GetGameDetailInput,
    "get_player": GetPlayerInput,
    "get_model_track_record": GetModelTrackRecordInput,
    "find": FindInput,
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    "get_slate": (
        "List the games or matches on one day (NBA, tennis) or one week (NFL): teams or players, start time, "
        "status and score, market lines, and the model's win probability where it has one. Call this when the "
        "user asks what is on, who is playing, or about the lines for a day or week. Each row has a game_id for "
        "get_game_detail."
    ),
    "get_top_props": (
        "The model's largest prop gaps for one day, ranked the way the Lineform page ranks them. NBA rows are "
        "reference projections only (signal reference_only), never picks. Tennis rows are upcoming best picks "
        "with a confidence tier: priced best bets have signal pick, unpriced angles have signal reference_only. "
        "Call this when the user asks which props the model likes, the biggest edges, or best plays. NFL is not "
        "supported: say so and offer get_slate instead."
    ),
    "get_game_detail": (
        "One game or tennis match in depth: market lines and movement, injuries, team or player context, the "
        "model's view, and that game's prop lines (standard lines by player, or every line for one player_id). "
        "Call this after get_slate, get_top_props or find, when the user asks about a specific game, matchup or "
        "a player's props tonight."
    ),
    "get_player": (
        "One NFL or tennis player's page: recent games or matches, current lines, and record splits. Call this "
        "when the user asks how a player has been doing. Needs a player_id from find or another tool. NBA has "
        "no player page; use get_game_detail for NBA players."
    ),
    "get_model_track_record": (
        "How the model has actually performed: each graded slice's verdict (adopt, reject, or insufficient = "
        "still accruing), sample size, hit rate with its standard error, and break-even. Call this whenever the "
        "user asks whether the model is any good, how it has done historically, or whether to trust a pick. "
        "Results are per slice, never per player or per prop."
    ),
    "find": (
        "Look up a player, team or tennis tournament by name on one day's or week's slate and return its ids. "
        "Call this first when the user names someone and you need a game_id or player_id for another tool."
    ),
}


def _without_titles(schema: JsonValue) -> JsonValue:
    """Drop pydantic's `title` keys: they repeat the field name and cost tokens on every request."""
    if isinstance(schema, dict):
        return {key: _without_titles(value) for key, value in schema.items() if key != "title"}
    if isinstance(schema, list):
        return [_without_titles(item) for item in schema]
    return schema


def tool_definitions() -> list[dict[str, JsonValue]]:
    """The Messages API `tools` list. Deterministic, so the prefix stays cacheable."""
    return [
        {
            "name": name,
            "description": TOOL_DESCRIPTIONS[name],
            "input_schema": _without_titles(model.model_json_schema()),
        }
        for name, model in TOOL_INPUTS.items()
    ]
