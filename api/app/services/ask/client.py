from __future__ import annotations

from anthropic import AsyncAnthropic

from app.config import Settings
from app.core.ask_cost import AskPrices, max_question_cost_usd


class AskNotConfigured(Exception):
    """ANTHROPIC_API_KEY is not set, so Ask Lineform cannot call Claude."""


def ask_available(settings: Settings) -> bool:
    return settings.ask_enabled and bool(settings.anthropic_api_key)


def make_client(settings: Settings) -> AsyncAnthropic:
    if not settings.anthropic_api_key:
        raise AskNotConfigured("ANTHROPIC_API_KEY is not set")
    return AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=60, max_retries=2)


def ask_prices(settings: Settings) -> AskPrices:
    return AskPrices(
        input=settings.ask_price_input_per_mtok,
        output=settings.ask_price_output_per_mtok,
        cache_read=settings.ask_price_cache_read_per_mtok,
        cache_write=settings.ask_price_cache_write_per_mtok,
    )


def question_reserve_usd(settings: Settings) -> float:
    # One request per tool round plus the final answer.
    return max_question_cost_usd(ask_prices(settings), settings.ask_max_tool_iterations + 1, settings.ask_max_tokens)
