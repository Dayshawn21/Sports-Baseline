import asyncio
import datetime as dt
import json

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.routers.ask import ask_client_factory, ask_session_factory
from app.schemas.ask import ToolResult
from app.services.ask import tools
from app.services.ask.answer_stream import ask_frames, error_kind
from app.services.ask.stream import ERROR_MESSAGES, SSE_PING
from tests.test_ask_loop import SETTINGS, FakeClient, _message, _text, _tool_use

NOW = dt.datetime(2026, 10, 28, 22, 0, tzinfo=dt.UTC)


class FakeSession:
    async def rollback(self):
        pass


class FakeSessions:
    """Stands in for SessionLocal: records that every session it opens is closed."""

    def __init__(self):
        self.opened = 0
        self.closed = 0

    def __call__(self):
        return self

    async def __aenter__(self):
        self.opened += 1
        return FakeSession()

    async def __aexit__(self, *exc):
        self.closed += 1


class RaisingMessages:
    def __init__(self, error):
        self.error = error

    def stream(self, **kwargs):
        raise self.error


class RaisingClient(FakeClient):
    def __init__(self, error):
        super().__init__()
        self.messages = RaisingMessages(error)


def _status_error(cls, status):
    response = httpx2.Response(status, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))
    return cls("secret detail from the provider", response=response, body=None)


def _frames(text):
    """(event, data) per frame; a comment frame reads as ("ping", None)."""
    frames = []
    for chunk in text.split("\n\n"):
        if not chunk:
            continue
        if chunk.startswith(":"):
            frames.append(("ping", None))
            continue
        event, data = chunk.split("\n")
        frames.append((event.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return frames


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "ask_enabled", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")


@pytest.fixture
def sessions():
    fake = FakeSessions()
    app.dependency_overrides[ask_session_factory] = lambda: fake
    yield fake
    app.dependency_overrides.pop(ask_session_factory, None)


@pytest.fixture
def use_client():
    def install(fake):
        app.dependency_overrides[ask_client_factory] = lambda: (lambda _settings: fake)
        return fake
    yield install
    app.dependency_overrides.pop(ask_client_factory, None)


@pytest.mark.parametrize(
    ("enabled", "key", "expected"),
    [(True, "sk-test", True), (True, "", False), (False, "sk-test", False), (False, "", False)],
)
def test_status_needs_the_setting_and_a_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, enabled: bool, key: str, expected: bool
) -> None:
    monkeypatch.setattr(settings, "ask_enabled", enabled)
    monkeypatch.setattr(settings, "anthropic_api_key", key)
    res = client.get("/ask/status")
    assert res.status_code == 200
    assert res.json() == {"enabled": expected}


def test_ask_is_off_by_default() -> None:
    assert type(settings).model_fields["ask_enabled"].default is False


@pytest.mark.parametrize("body", [{"question": "who plays?"}, {"question": ""}, {}])
def test_disabled_is_a_404_before_the_body_is_read(client, monkeypatch, body):
    monkeypatch.setattr(settings, "ask_enabled", False)
    assert client.post("/ask", json=body).status_code == 404


@pytest.mark.parametrize("question", ["", "   ", "x" * 501])
def test_a_bad_question_is_a_422(client, enabled, question):
    assert client.post("/ask", json={"question": question}).status_code == 422


def test_no_key_is_a_503(client, monkeypatch):
    monkeypatch.setattr(settings, "ask_enabled", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    res = client.post("/ask", json={"question": "who plays?"})
    assert res.status_code == 503
    assert res.json() == {"detail": "Ask Lineform is not configured"}


def test_a_two_tool_question_streams_status_text_then_done(client, enabled, sessions, use_client, monkeypatch):
    async def slate(inp, ctx):
        return ToolResult(tool="get_slate", sport=inp.sport, url="/nba", as_of=NOW)

    monkeypatch.setitem(tools.EXECUTORS, "get_slate", slate)
    fake = use_client(FakeClient(
        _message(
            _text("Let me check."),
            _tool_use("toolu_1", "get_slate", {"sport": "nba"}),
            _tool_use("toolu_2", "get_weather", {}),
            stop="tool_use",
        ),
        _message(_text("Two games "), _text("tonight.")),
    ))

    res = client.post("/ask", json={"question": "  who plays tonight?  "})

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    assert res.headers["cache-control"] == "no-cache"
    assert _frames(res.text) == [
        ("text", {"delta": "Let me check."}),
        ("tool_start", {"name": "get_slate", "sport": "nba"}),
        ("tool_end", {"name": "get_slate", "ok": True}),
        ("tool_start", {"name": "get_weather", "sport": None}),
        ("tool_end", {"name": "get_weather", "ok": False}),
        ("text", {"delta": "Two games "}),
        ("text", {"delta": "tonight."}),
        ("done", {"stop": "answered", "text": "Two games tonight."}),
    ]
    assert fake.messages.calls[0]["messages"][0]["content"].endswith("\n\nwho plays tonight?")
    assert fake.closed
    assert (sessions.opened, sessions.closed) == (1, 1)


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (_status_error(anthropic.RateLimitError, 429), "busy"),
        (_status_error(anthropic.OverloadedError, 529), "busy"),
        (_status_error(anthropic.InternalServerError, 500), "unavailable"),
        (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com")), "unavailable"),
        (RuntimeError("password=hunter2"), "failed"),
    ],
)
def test_a_raised_error_ends_with_fixed_copy(client, enabled, sessions, use_client, error, kind):
    fake = use_client(RaisingClient(error))
    res = client.post("/ask", json={"question": "who plays?"})

    assert res.status_code == 200
    assert _frames(res.text) == [("error", {"message": ERROR_MESSAGES[kind]})]
    assert "secret" not in res.text and "hunter2" not in res.text
    assert fake.closed
    assert sessions.closed == sessions.opened == 1


def test_error_kind_covers_every_sdk_error():
    assert error_kind(_status_error(anthropic.BadRequestError, 400)) == "unavailable"
    assert error_kind(ValueError()) == "failed"


class HangingStream:
    def __init__(self):
        self.exited = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.exited = True

    @property
    async def text_stream(self):
        await asyncio.Event().wait()
        yield ""


class HangingMessages:
    def __init__(self):
        self.stream_opened = HangingStream()

    def stream(self, **kwargs):
        return self.stream_opened


class HangingClient(FakeClient):
    def __init__(self):
        super().__init__()
        self.messages = HangingMessages()


def _frames_for(fake, sessions, ping_seconds=0.01):
    return ask_frames("who plays?", fake, sessions, None, SETTINGS, NOW, True, ping_seconds=ping_seconds)


def test_silence_sends_a_ping_and_a_disconnect_closes_everything():
    fake, sessions = HangingClient(), FakeSessions()

    async def run():
        frames = _frames_for(fake, sessions)
        first = await anext(frames)
        await frames.aclose()  # what Starlette does when the browser goes away
        return first

    assert asyncio.run(run()) == SSE_PING
    assert fake.messages.stream_opened.exited
    assert fake.closed
    assert (sessions.opened, sessions.closed) == (1, 1)
