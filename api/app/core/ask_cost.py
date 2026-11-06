from __future__ import annotations

from dataclasses import dataclass

from app.core.ask_messages import AskUsage

PER_MILLION = 1_000_000


@dataclass(frozen=True)
class AskPrices:
    """USD per million tokens. Ask prompts stay far under Haiku 5.5's 100K
    long-context threshold, so only the standard rates are modelled."""

    input: float
    output: float
    cache_read: float
    cache_write: float


def estimate_cost_usd(usage: AskUsage, prices: AskPrices) -> float:
    return (
        usage.input_tokens * prices.input
        + usage.output_tokens * prices.output
        + usage.cache_read_input_tokens * prices.cache_read
        + usage.cache_creation_input_tokens * prices.cache_write
    ) / PER_MILLION


# Input is not capped in code; a typical round sends about 3,600 tokens.
RESERVE_INPUT_TOKENS_PER_REQUEST = 20_000


def max_question_cost_usd(prices: AskPrices, max_requests: int, max_tokens: int) -> float:
    """The cost one question holds against the daily cap until it settles.
    Output is capped per request by max_tokens; input assumes
    RESERVE_INPUT_TOKENS_PER_REQUEST at the dearer of the uncached and cache-write rates."""
    input_price = max(prices.input, prices.cache_write)
    per_request = RESERVE_INPUT_TOKENS_PER_REQUEST * input_price + max_tokens * prices.output
    return max_requests * per_request / PER_MILLION
