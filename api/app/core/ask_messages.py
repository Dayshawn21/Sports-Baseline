from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal
from zoneinfo import ZoneInfo

from anthropic.types import ToolResultBlockParam, Usage

CENTRAL = ZoneInfo("America/Chicago")

AskStop = Literal["answered", "truncated", "refused", "iteration_limit", "error"]


def user_turn(question: str, now: dt.datetime) -> str:
    local = now.astimezone(CENTRAL)
    hour = local.hour % 12 or 12
    am_pm = "AM" if local.hour < 12 else "PM"
    stamp = f"{local:%A}, {local:%B} {local.day}, {local.year}, {hour}:{local.minute:02d} {am_pm} CT"
    return f"Today is {stamp}.\n\n{question}"


def tool_result_block(tool_use_id: str, content: str, is_error: bool = False) -> ToolResultBlockParam:
    block: ToolResultBlockParam = {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": content,
    }
    if is_error:
        block["is_error"] = True
    return block


@dataclass
class AskUsage:
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def add(self, usage: Usage) -> None:
        self.requests += 1
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.cache_read_input_tokens += usage.cache_read_input_tokens or 0
        self.cache_creation_input_tokens += usage.cache_creation_input_tokens or 0


_STOPS: dict[str, AskStop | None] = {
    "end_turn": "answered",
    "max_tokens": "truncated",
    "refusal": "refused",
    "tool_use": None,
}


def stop_for(stop_reason: str | None) -> AskStop | None:
    if stop_reason in _STOPS:
        return _STOPS[stop_reason]
    return "error"

