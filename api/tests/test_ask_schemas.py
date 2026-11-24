import datetime as dt
import json

import pytest
from pydantic import ValidationError

from app.schemas.ask import (
    DESCRIPTION_LIMIT,
    TOOL_DESCRIPTIONS,
    TOOL_INPUTS,
    FindInput,
    GetGameDetailInput,
    GetPlayerInput,
    GetSlateInput,
    GetTopPropsInput,
    ToolResult,
    tool_definitions,
)


def test_every_tool_has_a_definition_in_the_messages_api_shape():
    definitions = tool_definitions()
    assert [d["name"] for d in definitions] == list(TOOL_INPUTS)
    for definition in definitions:
        assert set(definition) == {"name", "description", "input_schema"}
        assert definition["input_schema"]["type"] == "object"
        assert definition["input_schema"]["additionalProperties"] is False


def test_definitions_are_deterministic_and_carry_no_titles():
    first, second = json.dumps(tool_definitions()), json.dumps(tool_definitions())
    assert first == second
    assert '"title"' not in first


@pytest.mark.parametrize("name", list(TOOL_DESCRIPTIONS))
def test_descriptions_stay_within_the_limit(name):
    assert 0 < len(TOOL_DESCRIPTIONS[name]) <= DESCRIPTION_LIMIT


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (GetSlateInput, {"sport": "nhl"}),
        (GetTopPropsInput, {"sport": "nfl"}),
        (GetPlayerInput, {"sport": "nba", "player_id": 1}),
        (GetGameDetailInput, {"sport": "soccer", "game_id": 1}),
    ],
)
def test_unsupported_sports_are_rejected(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_limits_are_bounded():
    with pytest.raises(ValidationError):
        GetTopPropsInput.model_validate({"sport": "nba", "limit": 50})
    assert GetTopPropsInput.model_validate({"sport": "nba"}).limit == 5


def test_periods_must_fit_the_sport():
    with pytest.raises(ValidationError, match="week applies to nfl only"):
        GetSlateInput.model_validate({"sport": "nba", "week": 3})
    with pytest.raises(ValidationError, match="by week, not date"):
        FindInput.model_validate({"sport": "nfl", "query": "Kelce", "date": "2026-10-27"})
    assert GetSlateInput.model_validate({"sport": "nfl", "week": 8}).week == 8


def test_tour_is_tennis_only():
    with pytest.raises(ValidationError, match="tennis only"):
        GetSlateInput.model_validate({"sport": "nba", "tour": "WTA"})


def test_nba_market_must_be_a_modelled_market():
    with pytest.raises(ValidationError, match="unknown nba market"):
        GetTopPropsInput.model_validate({"sport": "nba", "market": "steals"})
    assert GetTopPropsInput.model_validate({"sport": "tennis", "market": "aces"}).market == "aces"


def test_misspelled_arguments_are_errors_not_ignored():
    with pytest.raises(ValidationError):
        GetSlateInput.model_validate({"sport": "nba", "dat": "2026-10-27"})


def test_result_envelope_serializes_to_json():
    result = ToolResult(
        tool="get_slate", sport="nba", url="/nba", as_of=dt.datetime(2026, 10, 27, tzinfo=dt.UTC),
        data=[{"url": "/nba/game/1", "signal": "none"}],
    )
    assert json.loads(result.model_dump_json())["data"][0]["signal"] == "none"
