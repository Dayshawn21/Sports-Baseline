"""Run one Ask Lineform question and yield its server-sent event frames.

The loop runs as a task feeding a queue, so tool status and text reach the
browser as they happen, and a ping keeps the stream alive through slow tools.
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import logging
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager

import anthropic
from anthropic import AsyncAnthropic
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import Receive, Scope, Send

from app.config import Settings
from app.core.ask_cost import estimate_cost_usd
from app.core.ask_messages import AskUsage
from app.ml.registry import ModelRegistry
from app.services.ask.client import ask_prices
from app.services.ask.guardrails import Reservation
from app.services.ask.loop import AskEvent, AskOutcome, ToolStarted, run_ask
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


def record_question(
    usage: AskUsage, stop: str, tools: list[str], ms: int, settings: Settings, reservation: Reservation,
) -> None:
    """Settle the question's reservation to its cost and log it. Never the
    question, the answer or the client IP: Ask stores no user data."""
    if usage.requests == 0:
        reservation.release()
        return
    cost = estimate_cost_usd(usage, ask_prices(settings))
    total = reservation.settle(cost)
    logger.info(
        "ask question stop=%s requests=%d input=%d output=%d cache_read=%d cache_write=%d "
        "cost_usd=%.6f spent_today_usd=%.4f tools=%s ms=%d",
        stop, usage.requests, usage.input_tokens, usage.output_tokens,
        usage.cache_read_input_tokens, usage.cache_creation_input_tokens,
        cost, total, ",".join(tools), ms,
    )


async def ask_frames(
    question: str,
    client: AsyncAnthropic,
    sessions: SessionFactory,
    registry: ModelRegistry | None,
    settings: Settings,
    now: dt.datetime,
    production: bool,
    reservation: Reservation,
    ping_seconds: float = PING_SECONDS,
) -> AsyncGenerator[str, None]:
    # None marks the end; the task's result is read after the queue drains.
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    # Owned here, not by the loop, so rounds before an error or a disconnect are still counted.
    usage = AskUsage()
    tools: list[str] = []
    started = time.perf_counter()

    async def on_event(event: AskEvent) -> None:
        if isinstance(event, ToolStarted):
            tools.append(event.name)
        await queue.put(event_frame(event))

    async def answer() -> AskOutcome:
        # Its own session: FastAPI closes `yield` dependencies before a streamed body runs.
        async with sessions() as db:
            ctx = ToolContext(db, registry, now, production)
            return await run_ask(client, question, ctx, settings, on_event, usage=usage)

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
        if task.done():
            # Read from the task, not the frames: a disconnect can land after it finished.
            stop = "error" if task.exception() else task.result().stop
        else:
            stop = "cancelled"
            task.cancel()
        # Before any await: a disconnect can cancel the awaits below, and usage is
        # final once the task is cancelled (a round it cuts off is never added).
        record_question(usage, stop, tools, round((time.perf_counter() - started) * 1000), settings, reservation)
        if stop == "cancelled":
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await client.close()


class ReservedStreamingResponse(StreamingResponse):
    """Ends the question's reservation however the response ends. Starlette never
    closes the body on a disconnect, and one that never started never runs its
    `finally`, so close it here, then release whatever it did not settle."""

    def __init__(
        self, frames: AsyncGenerator[str, None], reservation: Reservation, headers: dict[str, str],
    ) -> None:
        super().__init__(frames, media_type="text/event-stream", headers=headers)
        self._frames = frames
        self._reservation = reservation

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            await self._frames.aclose()
            self._reservation.release()
