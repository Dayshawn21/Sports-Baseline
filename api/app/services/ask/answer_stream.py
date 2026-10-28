"""Run one Ask Lineform question and yield its server-sent event frames.

The loop runs as a task feeding a queue, so tool status and text reach the
browser as they happen, and a ping keeps the stream alive through slow tools.
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager

import anthropic
from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.ml.registry import ModelRegistry
from app.services.ask.loop import AskEvent, AskOutcome, run_ask
from app.services.ask.stream import SSE_PING, ErrorKind, done_frame, error_frame, event_frame
from app.services.ask.tools import ToolContext

logger = logging.getLogger(__name__)

PING_SECONDS = 10.0

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def error_kind(error: BaseException) -> ErrorKind:
    if isinstance(error, (anthropic.RateLimitError, anthropic.OverloadedError)):
        return "busy"
    if isinstance(error, anthropic.APIError):
        return "unavailable"
    return "failed"


async def ask_frames(
    question: str,
    client: AsyncAnthropic,
    sessions: SessionFactory,
    registry: ModelRegistry | None,
    settings: Settings,
    now: dt.datetime,
    production: bool,
    ping_seconds: float = PING_SECONDS,
) -> AsyncIterator[str]:
    # None marks the end; the task's result is read after the queue drains.
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def on_event(event: AskEvent) -> None:
        await queue.put(event_frame(event))

    async def answer() -> AskOutcome:
        # Its own session: FastAPI closes `yield` dependencies before a streamed body runs.
        async with sessions() as db:
            return await run_ask(client, question, ToolContext(db, registry, now, production), settings, on_event)

    task = asyncio.create_task(answer())
    task.add_done_callback(lambda _: queue.put_nowait(None))
    try:
        while True:
            try:
                frame = await asyncio.wait_for(queue.get(), timeout=ping_seconds)
            except TimeoutError:
                yield SSE_PING
                continue
            if frame is None:
                break
            yield frame
        try:
            outcome = task.result()
        except Exception as error:
            logger.exception("Ask Lineform question failed")
            yield error_frame(error_kind(error))
        else:
            yield done_frame(outcome)
    finally:
        # A client disconnect closes this generator early: stop the model call and the session.
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await client.close()
