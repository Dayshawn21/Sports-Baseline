import json

import pytest

from app.services.ask.loop import AskOutcome, TextDelta, ToolFinished, ToolStarted
from app.services.ask.stream import (
    ERROR_MESSAGES, SSE_PING, done_frame, error_frame, event_frame, sse_frame,
)


def _data(frame):
    [event_line, data_line, *_] = frame.split("\n")
    return event_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: "))


def test_sse_frame_is_event_then_one_compact_data_line():
    assert sse_frame("text", {"delta": "hi"}) == 'event: text\ndata: {"delta":"hi"}\n\n'


def test_multi_line_text_stays_on_one_data_line():
    frame = event_frame(TextDelta("line one\nline two"))
    assert frame == 'event: text\ndata: {"delta":"line one\\nline two"}\n\n'
    assert frame.count("\n") == 3


def test_ping_is_a_comment():
    assert SSE_PING == ": ping\n\n"


def test_tool_start_sends_only_name_and_sport():
    frame = event_frame(ToolStarted("get_slate", {"sport": "nba", "date": "2026-10-28", "limit": 5}))
    assert frame == 'event: tool_start\ndata: {"name":"get_slate","sport":"nba"}\n\n'


@pytest.mark.parametrize("tool_input", [{}, {"sport": 3}, {"query": "Jrue"}])
def test_tool_start_without_a_string_sport_sends_null(tool_input):
    assert _data(event_frame(ToolStarted("find", tool_input))) == ("tool_start", {"name": "find", "sport": None})


@pytest.mark.parametrize("ok", [True, False])
def test_tool_end_sends_name_and_ok_never_the_note(ok):
    frame = event_frame(ToolFinished("get_player", ok=ok, note="No player found"))
    assert _data(frame) == ("tool_end", {"name": "get_player", "ok": ok})


def test_done_sends_only_stop_and_text():
    outcome = AskOutcome(text="Two games tonight.", stop="answered")
    outcome.usage.input_tokens = 900
    assert done_frame(outcome) == 'event: done\ndata: {"stop":"answered","text":"Two games tonight."}\n\n'


@pytest.mark.parametrize("kind", ["busy", "unavailable", "failed"])
def test_error_frame_uses_fixed_copy(kind):
    assert _data(error_frame(kind)) == ("error", {"message": ERROR_MESSAGES[kind]})
