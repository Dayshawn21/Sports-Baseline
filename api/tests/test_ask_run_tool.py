import asyncio
import datetime as dt

import pytest

from app.schemas.ask import TOOL_INPUTS, tool_definitions
from app.services.ask import tools
from app.services.ask.prompt import SYSTEM_PROMPT

NOW = dt.datetime(2026, 10, 27, 22, 0, tzinfo=dt.UTC)
CTX = tools.ToolContext(db=None, registry=None, now=NOW, production=True)


def _run(name, raw):
    return asyncio.run(tools.run_tool(name, raw, CTX))


def test_every_defined_tool_has_an_executor_and_an_input_model():
    names = [definition["name"] for definition in tools.TOOLS]
    assert names == list(tools.EXECUTORS) == list(TOOL_INPUTS)
    assert tools.TOOLS == tool_definitions()


def test_run_tool_validates_then_dispatches(monkeypatch):
    seen = {}

    async def fake(inp, ctx):
        seen["inp"], seen["ctx"] = inp, ctx
        return "result"

    monkeypatch.setitem(tools.EXECUTORS, "get_slate", fake)
    assert _run("get_slate", {"sport": "nfl", "week": "8"}) == "result"
    assert seen["inp"].week == 8 and seen["ctx"] is CTX


def test_unknown_tool_lists_the_real_ones():
    with pytest.raises(tools.UnknownToolError, match="available: get_slate, get_top_props"):
        _run("get_weather", {})


@pytest.mark.parametrize(
    ("name", "raw", "message"),
    [
        ("get_slate", {"sport": "nba", "week": 3}, "get_slate: week applies to nfl only; use date for nba and tennis"),
        ("get_slate", {"sport": "hockey"}, "get_slate: sport: Input should be 'nba', 'nfl' or 'tennis'"),
        ("get_player", {"sport": "nfl"}, "get_player: player_id: Field required"),
    ],
)
def test_bad_input_becomes_one_readable_line(name, raw, message):
    with pytest.raises(tools.ToolInputError) as error:
        _run(name, raw)
    text = str(error.value)
    assert text == message
    assert "pydantic.dev" not in text and "input_value" not in text


def test_the_system_prompt_is_static_and_states_the_signal_rules():
    for rule in ('signal "pick"', '"reference_only" is never a pick', "insufficient", "Never invent a url", "find first"):
        assert rule in SYSTEM_PROMPT
    # The date arrives in the user turn; a timestamp here would break prompt caching.
    assert "2026" not in SYSTEM_PROMPT and "{" not in SYSTEM_PROMPT
