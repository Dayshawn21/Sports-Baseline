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
