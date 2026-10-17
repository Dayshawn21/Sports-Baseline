"""In-memory moving-window counters; one API instance, so no shared store is needed."""
from __future__ import annotations

import math
import time

from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from app.core.rate_limits import RateRule

storage = MemoryStorage()
_limiter = MovingWindowRateLimiter(storage)


def retry_after_seconds(client: str, rule: RateRule) -> int | None:
    """Count one request; return seconds to wait when the client is over the limit."""
    item = parse(rule.limit)
    if _limiter.hit(item, rule.scope, client):
        return None
    reset_at = _limiter.get_window_stats(item, rule.scope, client).reset_time
    return max(1, math.ceil(reset_at - time.time()))
