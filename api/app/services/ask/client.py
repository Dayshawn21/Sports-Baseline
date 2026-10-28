from __future__ import annotations

from anthropic import AsyncAnthropic

from app.config import Settings


class AskNotConfigured(Exception):
    """ANTHROPIC_API_KEY is not set, so Ask Lineform cannot call Claude."""


def ask_available(settings: Settings) -> bool:
    return settings.ask_enabled and bool(settings.anthropic_api_key)


def make_client(settings: Settings) -> AsyncAnthropic:
    if not settings.anthropic_api_key:
        raise AskNotConfigured("ANTHROPIC_API_KEY is not set")
    return AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=60, max_retries=2)
