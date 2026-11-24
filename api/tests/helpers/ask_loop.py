"""Shared fixtures and builders, first written for `test_ask_loop.py`."""
import datetime as dt

import pytest
from anthropic import Omit
from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from app.config import Settings
from app.schemas.ask import ToolResult
from app.services.ask import tools


NOW = dt.datetime(2026, 10, 27, 22, 0, tzinfo=dt.UTC)
SETTINGS = Settings(database_url="postgresql://localhost/ci", _env_file=None)


def _message(*content, stop="end_turn", input_tokens=900, output_tokens=60):
    return Message(
        id="msg_test", type="message", role="assistant", model=SETTINGS.ask_model,
        content=list(content), stop_reason=stop, stop_sequence=None,
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


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
