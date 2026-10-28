"""Ask Lineform's daily limits, held in memory.

One API process (Render runs one instance), so no shared store; a restart
resets both. The Anthropic Console spend limit is the hard backstop.
"""
from __future__ import annotations

import datetime as dt

from app.core.rate_limits import RateRule
from app.rate_limit import retry_after_seconds


class DailySpend:
    """Estimated USD spent on the current UTC day; a new day starts from zero."""

    def __init__(self) -> None:
        self._day: dt.date | None = None
        self._total = 0.0

    def spent(self, today: dt.date) -> float:
        return self._total if today == self._day else 0.0

    def record(self, today: dt.date, cost_usd: float) -> float:
        if today != self._day:
            self._day, self._total = today, 0.0
        self._total += cost_usd
        return self._total

    def exhausted(self, today: dt.date, cap_usd: float) -> bool:
        return self.spent(today) >= cap_usd


spend = DailySpend()


def question_retry_after(client_ip: str, per_day: int) -> int | None:
    """Count one question; seconds until the client may ask again, or None."""
    return retry_after_seconds(client_ip, RateRule(f"{per_day}/day", "ask_daily"))
