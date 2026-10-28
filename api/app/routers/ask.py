from __future__ import annotations

import datetime as dt
from collections.abc import Callable

from anthropic import AsyncAnthropic
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import Settings, settings
from app.core.production_settings import is_production
from app.db.pool import SessionLocal
from app.schemas.ask import AskRequest, AskStatusResponse
from app.services.ask import guardrails
from app.services.ask.answer_stream import SessionFactory, ask_frames
from app.services.ask.client import AskNotConfigured, ask_available, make_client

router = APIRouter()

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def require_ask_enabled() -> None:
    # A dependency, so a disabled route is a 404 before the body is validated.
    if not settings.ask_enabled:
        raise HTTPException(status_code=404, detail="Not Found")


def require_ask_budget(request: Request, today: dt.date) -> None:
    """Refuse before the stream opens, so a refused question costs nothing. Called
    in the endpoint, not as a dependency: dependencies run before the body is
    validated, and a 422 must not use up one of the visitor's questions."""
    # The global cap first, so a refusal here does not count against the visitor.
    if guardrails.spend.exhausted(today, settings.ask_daily_spend_cap_usd):
        raise HTTPException(
            status_code=503, detail="Ask Lineform has reached today's limit. It resets at midnight UTC.",
        )
    client_ip = request.client.host if request.client else "unknown"
    per_day = settings.ask_daily_questions_per_ip
    retry_after = guardrails.question_retry_after(client_ip, per_day)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail=f"You've used today's {per_day} questions. Try again tomorrow.",
            headers={"Retry-After": str(retry_after)},
        )


def ask_client_factory() -> Callable[[Settings], AsyncAnthropic]:
    return make_client


def ask_session_factory() -> SessionFactory:
    return SessionLocal


@router.get("/status", response_model=AskStatusResponse)
async def get_status() -> AskStatusResponse:
    return AskStatusResponse(enabled=ask_available(settings))


@router.post("", dependencies=[Depends(require_ask_enabled)])
async def ask(
    body: AskRequest,
    request: Request,
    make: Callable[[Settings], AsyncAnthropic] = Depends(ask_client_factory),
    sessions: SessionFactory = Depends(ask_session_factory),
) -> StreamingResponse:
    now = dt.datetime.now(dt.UTC)
    require_ask_budget(request, now.date())
    try:
        client = make(settings)
    except AskNotConfigured:
        raise HTTPException(status_code=503, detail="Ask Lineform is not configured")
    frames = ask_frames(
        body.question, client, sessions, getattr(request.app.state, "registry", None), settings,
        now, is_production(settings.api_env),
    )
    return StreamingResponse(frames, media_type="text/event-stream", headers=SSE_HEADERS)
