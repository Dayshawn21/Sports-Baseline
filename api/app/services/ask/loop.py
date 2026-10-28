from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from anthropic import AsyncAnthropic, omit
from anthropic.types import Message, MessageParam, TextBlockParam, ToolResultBlockParam, ToolUseBlock

from app.config import Settings
from app.core.ask_messages import AskStop, AskUsage, stop_for, tool_result_block, user_turn
from app.services.ask.prompt import SYSTEM_PROMPT
from app.services.ask.tools import TOOLS, ToolContext, ToolInputError, UnknownToolError, run_tool

logger = logging.getLogger(__name__)

REFUSAL_TEXT = "I can't help with that one. Ask me about a slate, a player or the model's track record."
TOOL_FAILED = "{name} failed on the server; tell the user this data could not be checked."

# The breakpoint caches tools then system: the part every question shares.
SYSTEM: list[TextBlockParam] = [
    {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
]


@dataclass
class ToolCallRecord:
    name: str
    input: dict[str, object]
    is_error: bool
    ms: int


@dataclass
class AskOutcome:
    text: str
    stop: AskStop
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    usage: AskUsage = field(default_factory=AskUsage)


@dataclass(frozen=True)
class ToolStarted:
    name: str
    input: dict[str, object]


@dataclass(frozen=True)
class ToolFinished:
    name: str
    ok: bool
    note: str | None


@dataclass(frozen=True)
class TextDelta:
    text: str


AskEvent = ToolStarted | ToolFinished | TextDelta
OnEvent = Callable[[AskEvent], Awaitable[None]]


def answer_text(response: Message) -> str:
    return "".join(block.text for block in response.content if block.type == "text")


def finish(response: Message, stop: AskStop, usage: AskUsage, tool_calls: list[ToolCallRecord]) -> AskOutcome:
    if stop == "refused":
        text = REFUSAL_TEXT
    elif stop == "error":
        text = ""
    else:
        text = answer_text(response)
    return AskOutcome(text=text, stop=stop, tool_calls=tool_calls, usage=usage)


async def run_one_tool(
    block: ToolUseBlock, ctx: ToolContext, tool_calls: list[ToolCallRecord], on_event: OnEvent | None,
) -> ToolResultBlockParam:
    if on_event:
        await on_event(ToolStarted(name=block.name, input=dict(block.input)))
    started = time.perf_counter()
    note: str | None = None
    try:
        result = await run_tool(block.name, block.input, ctx)
        content, is_error, note = result.model_dump_json(), False, result.note
    except (UnknownToolError, ToolInputError) as error:
        content, is_error = str(error), True
    except Exception:
        # The model sees a fixed sentence: exception text can carry connection details.
        logger.exception("Ask tool %s failed", block.name)
        await ctx.db.rollback()
        content, is_error = TOOL_FAILED.format(name=block.name), True
    ms = round((time.perf_counter() - started) * 1000)
    tool_calls.append(ToolCallRecord(name=block.name, input=dict(block.input), is_error=is_error, ms=ms))
    if on_event:
        await on_event(ToolFinished(name=block.name, ok=not is_error, note=note))
    return tool_result_block(block.id, content, is_error=is_error)


async def run_ask(
    client: AsyncAnthropic, question: str, ctx: ToolContext, settings: Settings,
    on_event: OnEvent | None = None,
    usage: AskUsage | None = None,
) -> AskOutcome:
    messages: list[MessageParam] = [{"role": "user", "content": user_turn(question, ctx.now)}]
    usage = usage if usage is not None else AskUsage()
    tool_calls: list[ToolCallRecord] = []
    tool_rounds = 0
    while True:
        final = tool_rounds == settings.ask_max_tool_iterations
        async with client.messages.stream(
            model=settings.ask_model,
            max_tokens=settings.ask_max_tokens,
            output_config={"effort": settings.ask_effort},
            system=SYSTEM,
            tools=TOOLS,
            tool_choice={"type": "none"} if final else omit,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                if on_event:
                    await on_event(TextDelta(text))
            response = await stream.get_final_message()
        usage.add(response.usage)
        stop = stop_for(response.stop_reason)
        if final and stop == "answered":
            stop = "iteration_limit"
        elif final and stop is None:
            stop = "error"
        if stop is not None:
            return finish(response, stop, usage, tool_calls)

        messages.append({"role": "assistant", "content": response.content})
        results: list[ToolResultBlockParam] = []
        for block in response.content:
            if block.type == "tool_use":
                 results.append(await run_one_tool(block, ctx, tool_calls, on_event))

        messages.append({"role": "user", "content": results})
        tool_rounds += 1
