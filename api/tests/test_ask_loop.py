import asyncio
import datetime as dt

import pytest
from anthropic import AsyncAnthropic, Omit
from anthropic.types import Message, TextBlock, ThinkingBlock, ToolUseBlock, Usage

from app.config import Settings
from app.core.ask_messages import AskUsage, tool_result_block, user_turn
from app.schemas.ask import ToolResult
from app.services.ask import tools
from app.services.ask.client import AskNotConfigured, make_client
from app.services.ask.loop import REFUSAL_TEXT, TextDelta, ToolFinished, ToolStarted, run_ask
from app.services.ask.prompt import SYSTEM_PROMPT
from app.services.ask.tools import TOOLS, ToolContext

NOW = dt.datetime(2026, 10, 27, 22, 0, tzinfo=dt.UTC)
CTX = ToolContext(db=None, registry=None, now=NOW, production=True)
SETTINGS = Settings(database_url="postgresql://localhost/ci", _env_file=None)
QUESTION = "Who plays tonight?"


def _message(*content, stop="end_turn", input_tokens=900, output_tokens=60):
    return Message(
        id="msg_test", type="message", role="assistant", model=SETTINGS.ask_model,
        content=list(content), stop_reason=stop, stop_sequence=None,
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def _thinking():
    return ThinkingBlock(type="thinking", thinking="", signature="sig")


def _text(text):
    return TextBlock(type="text", text=text)


class FakeStream:
    """The slice of the SDK's AsyncMessageStream the loop uses: one text delta
    per text block, then the scripted Message as the final message."""

    def __init__(self, response):
        self.response = response
        self.exited = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.exited = True

    @property
    async def text_stream(self):
        for block in self.response.content:
            if block.type == "text":
                yield block.text

    async def get_final_message(self):
        return self.response


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.streams = []

    def stream(self, **kwargs):
        # Like the SDK, an `omit` argument is not sent. Copy the list: the loop
        # appends to it after this call returns.
        sent = {key: value for key, value in kwargs.items() if not isinstance(value, Omit)}
        self.calls.append({**sent, "messages": list(kwargs["messages"])})
        stream = FakeStream(self.responses.pop(0))
        self.streams.append(stream)
        return stream


class FakeClient:
    def __init__(self, *responses):
        self.messages = FakeMessages(responses)
        self.closed = False

    async def close(self):
        self.closed = True


def _ask(client):
    return asyncio.run(run_ask(client, QUESTION, CTX, SETTINGS))


def test_request_sends_the_cached_prefix_and_the_dated_question():
    client = FakeClient(_message(_text("No games tonight.")))
    _ask(client)

    [request] = client.messages.calls
    assert request["model"] == SETTINGS.ask_model
    assert request["max_tokens"] == SETTINGS.ask_max_tokens
    assert request["output_config"] == {"effort": "low"}
    assert request["system"] == [
        {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
    ]
    assert request["tools"] is TOOLS
    assert request["messages"] == [{"role": "user", "content": user_turn(QUESTION, NOW)}]


def test_request_sends_no_sampling_or_thinking_parameters():
    client = FakeClient(_message(_text("ok")))
    _ask(client)
    assert set(client.messages.calls[0]) == {
        "model", "max_tokens", "output_config", "system", "tools", "messages",
    }


def test_answer_skips_thinking_blocks():
    outcome = _ask(FakeClient(_message(_thinking(), _text("Two NBA games tonight."))))
    assert outcome.text == "Two NBA games tonight."
    assert outcome.stop == "answered"
    assert outcome.tool_calls == []


def test_answer_joins_every_text_block():
    outcome = _ask(FakeClient(_message(_text("Lakers at "), _text("Suns."))))
    assert outcome.text == "Lakers at Suns."


def test_usage_counts_the_request():
    outcome = _ask(FakeClient(_message(_text("ok"), input_tokens=1500, output_tokens=40)))
    assert outcome.usage == AskUsage(requests=1, input_tokens=1500, output_tokens=40)


def test_max_tokens_returns_the_partial_text_as_truncated():
    outcome = _ask(FakeClient(_message(_thinking(), _text("The top gaps are"), stop="max_tokens")))
    assert outcome.stop == "truncated"
    assert outcome.text == "The top gaps are"


def test_refusal_returns_the_fixed_sentence():
    outcome = _ask(FakeClient(_message(stop="refusal")))
    assert outcome.stop == "refused"
    assert outcome.text == REFUSAL_TEXT


@pytest.mark.parametrize("reason", ["pause_turn", "stop_sequence", "model_context_window_exceeded"])
def test_unexpected_stops_are_errors_with_no_text(reason):
    outcome = _ask(FakeClient(_message(_text("partial"), stop=reason)))
    assert outcome.stop == "error"
    assert outcome.text == ""


def test_effort_defaults_to_low():
    assert SETTINGS.ask_effort == "low"


def test_make_client_refuses_an_empty_key():
    with pytest.raises(AskNotConfigured):
        make_client(SETTINGS)


def test_make_client_passes_the_key_and_limits():
    client = make_client(SETTINGS.model_copy(update={"anthropic_api_key": "sk-test"}))
    assert isinstance(client, AsyncAnthropic)
    assert client.api_key == "sk-test"
    assert client.max_retries == 2
    assert client.timeout == 60


def _tool_use(tool_id, name, tool_input):
    return ToolUseBlock(type="tool_use", id=tool_id, name=name, input=tool_input)


def _tool_result(name, sport):
    return ToolResult(tool=name, sport=sport, url=f"/{sport}", as_of=NOW, data=[{"url": f"/{sport}", "signal": "none"}])


@pytest.fixture
def ran(monkeypatch):
    """Stub the executors, not run_tool, so the real validation still runs.
    Returns the (tool, input) calls in the order they executed."""
    calls = []

    def executor(name):
        async def run(inp, ctx):
            calls.append((name, inp.model_dump(exclude_none=True)))
            return _tool_result(name, inp.sport)
        return run

    for name in ("get_slate", "find"):
        monkeypatch.setitem(tools.EXECUTORS, name, executor(name))
    return calls


def test_one_tool_round_then_the_answer(ran):
    asks = _message(
        _thinking(), _text("Let me check."), _tool_use("toolu_1", "get_slate", {"sport": "nba"}),
        stop="tool_use",
    )
    client = FakeClient(asks, _message(_text("Two NBA games tonight.")))
    outcome = _ask(client)

    assert ran == [("get_slate", {"sport": "nba"})]
    assert outcome.stop == "answered"
    assert outcome.text == "Two NBA games tonight."  # the final turn only, not "Let me check."
    assert outcome.usage.requests == 2

    first, second = client.messages.calls
    assert second["messages"] == [
        first["messages"][0],
        {"role": "assistant", "content": asks.content},  # thinking block kept, unmodified
        {"role": "user", "content": [
            tool_result_block("toolu_1", _tool_result("get_slate", "nba").model_dump_json()),
        ]},
    ]


def test_parallel_calls_run_in_order_and_answer_in_one_message(ran):
    asks = _message(
        _tool_use("toolu_a", "find", {"sport": "nba", "query": "Lakers"}),
        _tool_use("toolu_b", "get_slate", {"sport": "nfl"}),
        stop="tool_use",
    )
    client = FakeClient(asks, _message(_text("done")))
    _ask(client)

    assert [name for name, _ in ran] == ["find", "get_slate"]
    results = client.messages.calls[1]["messages"][2]
    assert results["role"] == "user"
    assert [block["tool_use_id"] for block in results["content"]] == ["toolu_a", "toolu_b"]
    assert all("is_error" not in block for block in results["content"])


def test_rounds_repeat_until_the_model_answers(ran):
    client = FakeClient(
        _message(_tool_use("toolu_1", "find", {"sport": "nfl", "query": "Chiefs"}), stop="tool_use"),
        _message(_tool_use("toolu_2", "get_slate", {"sport": "nfl"}), stop="tool_use"),
        _message(_text("Chiefs play Sunday.")),
    )
    outcome = _ask(client)

    assert outcome.text == "Chiefs play Sunday."
    assert outcome.usage.requests == 3
    roles = [message["role"] for message in client.messages.calls[2]["messages"]]
    assert roles == ["user", "assistant", "user", "assistant", "user"]


def test_tool_calls_are_recorded(ran):
    client = FakeClient(
        _message(
            _tool_use("toolu_a", "find", {"sport": "nba", "query": "Lakers"}),
            _tool_use("toolu_b", "get_slate", {"sport": "nba"}),
            stop="tool_use",
        ),
        _message(_text("done")),
    )
    outcome = _ask(client)

    assert [(c.name, c.input, c.is_error) for c in outcome.tool_calls] == [
        ("find", {"sport": "nba", "query": "Lakers"}, False),
        ("get_slate", {"sport": "nba"}, False),
    ]
    assert all(isinstance(c.ms, int) and c.ms >= 0 for c in outcome.tool_calls)


class FakeDb:
    def __init__(self):
        self.rollbacks = 0

    async def rollback(self):
        self.rollbacks += 1


def _results_sent(client, request=1):
    """The tool_result blocks in the last message of a later request."""
    return client.messages.calls[request]["messages"][-1]["content"]


def test_unknown_tool_goes_back_as_an_error_and_the_loop_continues():
    client = FakeClient(
        _message(_tool_use("toolu_1", "get_weather", {"city": "Dallas"}), stop="tool_use"),
        _message(_text("I can only answer Lineform questions.")),
    )
    outcome = _ask(client)

    [block] = _results_sent(client)
    assert block["is_error"] is True
    assert block["content"].startswith("unknown tool 'get_weather'; available: get_slate")
    assert outcome.stop == "answered"
    assert [(c.name, c.is_error) for c in outcome.tool_calls] == [("get_weather", True)]


def test_bad_input_goes_back_with_the_validation_message():
    client = FakeClient(
        _message(_tool_use("toolu_1", "find", {"sport": "nba", "query": "x"}), stop="tool_use"),
        _message(_text("done")),
    )
    outcome = _ask(client)

    [block] = _results_sent(client)
    assert block["is_error"] is True
    assert block["content"].startswith("find: query:")
    assert outcome.tool_calls[0].is_error is True


def test_one_failed_call_does_not_drop_the_other_result(ran):
    client = FakeClient(
        _message(
            _tool_use("toolu_a", "get_weather", {}),
            _tool_use("toolu_b", "get_slate", {"sport": "nba"}),
            stop="tool_use",
        ),
        _message(_text("done")),
    )
    _ask(client)

    first, second = _results_sent(client)
    assert (first["tool_use_id"], first.get("is_error")) == ("toolu_a", True)
    assert (second["tool_use_id"], second.get("is_error")) == ("toolu_b", None)


def test_a_crashing_tool_rolls_back_and_hides_the_exception(monkeypatch, caplog):
    async def broken(inp, ctx):
        raise RuntimeError("password authentication failed for user sportapp")

    monkeypatch.setitem(tools.EXECUTORS, "get_slate", broken)
    db = FakeDb()
    ctx = ToolContext(db=db, registry=None, now=NOW, production=True)
    client = FakeClient(
        _message(_tool_use("toolu_1", "get_slate", {"sport": "nba"}), stop="tool_use"),
        _message(_text("I could not check tonight's slate.")),
    )
    outcome = asyncio.run(run_ask(client, QUESTION, ctx, SETTINGS))

    [block] = _results_sent(client)
    assert block == {
        "type": "tool_result",
        "tool_use_id": "toolu_1",
        "content": "get_slate failed on the server; tell the user this data could not be checked.",
        "is_error": True,
    }
    assert db.rollbacks == 1
    assert "password" not in str(client.messages.calls)
    assert outcome.stop == "answered"
    assert "get_slate" in caplog.text and "RuntimeError" in caplog.text  # logged with its traceback


def test_a_truncated_tool_call_runs_nothing(ran):
    client = FakeClient(_message(
        _text("Checking"), _tool_use("toolu_1", "get_slate", {"sport": "nba"}), stop="max_tokens",
    ))
    outcome = _ask(client)

    assert ran == []
    assert outcome.stop == "truncated"
    assert len(client.messages.calls) == 1


def _always_asks(rounds):
    return [
        _message(_tool_use(f"toolu_{n}", "get_slate", {"sport": "nba"}), stop="tool_use")
        for n in range(rounds)
    ]


def test_the_limit_forces_a_final_answer_without_tools(ran):
    client = FakeClient(*_always_asks(5), _message(_text("Here is what I found so far.")))
    outcome = _ask(client)

    calls = client.messages.calls
    assert len(calls) == 6
    assert len(ran) == 5
    assert all("tool_choice" not in call for call in calls[:5])
    assert calls[5]["tool_choice"] == {"type": "none"}
    assert calls[5]["tools"] is TOOLS  # earlier turns hold tool_use blocks, so tools are still sent
    assert outcome.stop == "iteration_limit"
    assert outcome.text == "Here is what I found so far."
    assert outcome.usage.requests == 6


def test_a_limit_of_one_makes_two_requests(ran):
    client = FakeClient(*_always_asks(1), _message(_text("partial")))
    settings = SETTINGS.model_copy(update={"ask_max_tool_iterations": 1})
    outcome = asyncio.run(run_ask(client, QUESTION, CTX, settings))

    assert len(client.messages.calls) == 2
    assert client.messages.calls[1]["tool_choice"] == {"type": "none"}
    assert outcome.stop == "iteration_limit"


def test_a_truncated_final_answer_stays_truncated(ran):
    client = FakeClient(*_always_asks(5), _message(_text("Partial"), stop="max_tokens"))
    assert _ask(client).stop == "truncated"


def test_a_tool_request_on_the_final_turn_runs_nothing(ran):
    client = FakeClient(*_always_asks(6))
    outcome = _ask(client)

    assert len(ran) == 5
    assert len(client.messages.calls) == 6
    assert outcome.stop == "error"


def test_answering_inside_the_limit_never_sends_tool_choice(ran):
    client = FakeClient(*_always_asks(4), _message(_text("done")))
    outcome = _ask(client)

    assert all("tool_choice" not in call for call in client.messages.calls)
    assert outcome.stop == "answered"


class Recorder:
    def __init__(self):
        self.events = []

    async def __call__(self, event):
        self.events.append(event)


def _ask_recording(client):
    recorder = Recorder()
    outcome = asyncio.run(run_ask(client, QUESTION, CTX, SETTINGS, on_event=recorder))
    return outcome, recorder.events


def test_events_bracket_each_tool_in_order(ran):
    client = FakeClient(
        _message(
            _tool_use("toolu_a", "find", {"sport": "nba", "query": "Lakers"}),
            _tool_use("toolu_b", "get_slate", {"sport": "nba"}),
            stop="tool_use",
        ),
        _message(_text("done")),
    )
    _, events = _ask_recording(client)

    assert events == [
        ToolStarted(name="find", input={"sport": "nba", "query": "Lakers"}),
        ToolFinished(name="find", ok=True, note=None),
        ToolStarted(name="get_slate", input={"sport": "nba"}),
        ToolFinished(name="get_slate", ok=True, note=None),
        TextDelta("done"),
    ]


def test_a_failed_tool_finishes_not_ok():
    client = FakeClient(
        _message(_tool_use("toolu_1", "get_weather", {}), stop="tool_use"),
        _message(_text("done")),
    )
    _, events = _ask_recording(client)
    assert events[-2] == ToolFinished(name="get_weather", ok=False, note=None)


def test_finished_carries_the_result_note_not_its_rows(monkeypatch):
    async def empty(inp, ctx):
        return ToolResult(tool="get_slate", sport="nba", url="/nba", as_of=NOW, note="No NBA games on this date.")

    monkeypatch.setitem(tools.EXECUTORS, "get_slate", empty)
    client = FakeClient(
        _message(_tool_use("toolu_1", "get_slate", {"sport": "nba"}), stop="tool_use"),
        _message(_text("No games tonight.")),
    )
    _, events = _ask_recording(client)
    assert events[-2] == ToolFinished(name="get_slate", ok=True, note="No NBA games on this date.")


def test_no_tool_means_only_text_events():
    _, events = _ask_recording(FakeClient(_message(_thinking(), _text("hi"))))
    assert events == [TextDelta("hi")]


def test_text_deltas_arrive_in_order_across_rounds(ran):
    client = FakeClient(
        _message(_text("Let me check."), _tool_use("toolu_1", "get_slate", {"sport": "nba"}), stop="tool_use"),
        _message(_text("Lakers at "), _text("Suns.")),
    )
    outcome, events = _ask_recording(client)
    assert events == [
        TextDelta("Let me check."),
        ToolStarted(name="get_slate", input={"sport": "nba"}),
        ToolFinished(name="get_slate", ok=True, note=None),
        TextDelta("Lakers at "),
        TextDelta("Suns."),
    ]
    assert outcome.text == "Lakers at Suns."  # deltas are display; the outcome is the final turn


def test_a_tool_only_round_emits_no_text(ran):
    client = FakeClient(
        _message(_thinking(), _tool_use("toolu_1", "get_slate", {"sport": "nba"}), stop="tool_use"),
        _message(_text("ok")),
    )
    _, events = _ask_recording(client)
    assert [e for e in events if isinstance(e, TextDelta)] == [TextDelta("ok")]
    assert isinstance(events[0], ToolStarted)


def test_every_stream_is_closed(ran):
    client = FakeClient(
        _message(_tool_use("toolu_1", "get_slate", {"sport": "nba"}), stop="tool_use"),
        _message(_text("ok")),
    )
    _ask(client)
    assert [s.exited for s in client.messages.streams] == [True, True]


def test_a_refusal_streams_its_text_but_answers_with_the_fixed_sentence():
    outcome, events = _ask_recording(FakeClient(_message(_text("I won't"), stop="refusal")))
    assert events == [TextDelta("I won't")]
    assert outcome.text == REFUSAL_TEXT


def test_the_callback_does_not_change_the_outcome(ran):
    def script():
        return FakeClient(
            _message(_tool_use("toolu_1", "get_slate", {"sport": "nba"}), stop="tool_use"),
            _message(_text("Two games.")),
        )

    plain = _ask(script())
    recorded, _ = _ask_recording(script())
    assert (recorded.text, recorded.stop, recorded.usage) == (plain.text, plain.stop, plain.usage)
    assert [c.name for c in recorded.tool_calls] == [c.name for c in plain.tool_calls]


def test_a_callback_error_propagates(ran):
    async def disconnected(event):
        raise ConnectionResetError("client went away")

    client = FakeClient(
        _message(_tool_use("toolu_1", "get_slate", {"sport": "nba"}), stop="tool_use"),
        _message(_text("never sent")),
    )
    with pytest.raises(ConnectionResetError):
        asyncio.run(run_ask(client, QUESTION, CTX, SETTINGS, on_event=disconnected))
    assert ran == []  # it fails on ToolStarted, before the tool runs


class FailingMessages(FakeMessages):
    """Scripted rounds; an exception in the script is raised when its round opens."""

    def stream(self, **kwargs):
        if isinstance(self.responses[0], Exception):
            raise self.responses.pop(0)
        return super().stream(**kwargs)


def _failing_client(*rounds):
    client = FakeClient()
    client.messages = FailingMessages(rounds)
    return client


def _slate_round(input_tokens=900, output_tokens=60):
    return _message(
        _tool_use("toolu_1", "get_slate", {"sport": "nba"}), stop="tool_use",
        input_tokens=input_tokens, output_tokens=output_tokens,
    )


def test_a_caller_owned_usage_collects_every_round(ran):
    client = FakeClient(_slate_round(900, 30), _message(_text("ok"), input_tokens=1200, output_tokens=50))
    usage = AskUsage()
    outcome = asyncio.run(run_ask(client, QUESTION, CTX, SETTINGS, usage=usage))
    assert outcome.usage is usage
    assert usage == AskUsage(requests=2, input_tokens=2100, output_tokens=80)


def test_a_caller_owned_usage_keeps_the_rounds_before_a_failure(ran):
    client = _failing_client(_slate_round(), RuntimeError("provider down"))
    usage = AskUsage()
    with pytest.raises(RuntimeError):
        asyncio.run(run_ask(client, QUESTION, CTX, SETTINGS, usage=usage))
    assert usage == AskUsage(requests=1, input_tokens=900, output_tokens=60)
