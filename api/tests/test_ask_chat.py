import pytest

from app.core.ask_messages import AskUsage
from app.services.ask.chat import format_event, format_outcome, question_from
from app.services.ask.loop import AskOutcome, ToolCallRecord, ToolFinished, ToolStarted


def test_unquoted_words_become_one_question():
    assert question_from(["who", "plays", "tonight?"]) == "who plays tonight?"


def test_a_quoted_question_passes_through():
    assert question_from(["Top NBA props tonight?"]) == "Top NBA props tonight?"


@pytest.mark.parametrize("args", [[], ["  "], ["", " "]])
def test_a_blank_question_is_rejected(args):
    with pytest.raises(ValueError):
        question_from(args)


def test_outcome_shows_answer_stop_tools_and_usage():
    outcome = AskOutcome(
        text="Two NBA games tonight: [Lakers at Suns](/nba/game/401).",
        stop="answered",
        tool_calls=[
            ToolCallRecord(name="get_slate", input={"sport": "nba"}, is_error=False, ms=412, content="{}"),
            ToolCallRecord(name="get_weather", input={}, is_error=True, ms=0, content="unknown tool 'get_weather'"),
        ],
        usage=AskUsage(
            requests=2, input_tokens=5210, output_tokens=312,
            cache_read_input_tokens=4100, cache_creation_input_tokens=0,
        ),
    )
    assert format_outcome(outcome) == "\n".join([
        "Two NBA games tonight: [Lakers at Suns](/nba/game/401).",
        "",
        "stop: answered",
        "tools: 2",
        '  get_slate {"sport": "nba"}  ok  412 ms',
        "  get_weather {}  error  0 ms",
        "usage: 2 requests, 5,210 input, 312 output, 4,100 cache read, 0 cache write",
    ])


def test_an_outcome_without_tools_or_text_says_so():
    lines = format_outcome(AskOutcome(text="", stop="error", usage=AskUsage(requests=1))).splitlines()
    assert lines[:4] == ["(no answer)", "", "stop: error", "tools: 0"]


def test_events_read_as_one_line_each():
    assert format_event(ToolStarted(name="find", input={"sport": "nfl", "query": "Chiefs"})) == (
        '-> find {"sport": "nfl", "query": "Chiefs"}'
    )
    assert format_event(ToolFinished(name="find", ok=True, note=None)) == "<- find ok"
    assert format_event(ToolFinished(name="get_slate", ok=True, note="No NBA games on this date.")) == (
        "<- get_slate ok: No NBA games on this date."
    )
    assert format_event(ToolFinished(name="get_weather", ok=False, note=None)) == "<- get_weather error"
