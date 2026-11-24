"""Server-sent event frames for `POST /ask`.

Only what the drawer needs crosses the wire: tool names and sport, text, the
final answer and stop. Tool inputs beyond `sport`, data rows and token usage
stay on the server.
"""
from __future__ import annotations

import json
from typing import Literal

from app.services.ask.loop import AskEvent, AskOutcome, TextDelta, ToolStarted

ErrorKind = Literal["busy", "unavailable", "failed"]

SSE_PING = ": ping\n\n"

ERROR_MESSAGES: dict[ErrorKind, str] = {
    "busy": "Ask Lineform is busy right now. Try again in a minute.",
    "unavailable": "Ask Lineform can't reach its model right now. Try again shortly.",
    "failed": "Something went wrong answering that. Try again.",
}


def sse_frame(event: str, data: dict[str, object]) -> str:
    # Compact JSON keeps a multi-line answer on one `data:` line.
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def event_frame(event: AskEvent) -> str:
    if isinstance(event, TextDelta):
        return sse_frame("text", {"delta": event.text})
    if isinstance(event, ToolStarted):
        sport = event.input.get("sport")
        return sse_frame("tool_start", {"name": event.name, "sport": sport if isinstance(sport, str) else None})
    return sse_frame("tool_end", {"name": event.name, "ok": event.ok})


def done_frame(outcome: AskOutcome) -> str:
    return sse_frame("done", {"stop": outcome.stop, "text": outcome.text})


def error_frame(kind: ErrorKind) -> str:
    return sse_frame("error", {"message": ERROR_MESSAGES[kind]})
