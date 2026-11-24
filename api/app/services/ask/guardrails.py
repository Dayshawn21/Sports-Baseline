"""Ask Lineform's daily limits, held in memory.

One API process (Render runs one instance), so no shared store; a restart
resets both. The Anthropic Console spend limit is the hard backstop.
"""
from __future__ import annotations

import datetime as dt

from app.core.rate_limits import RateRule
from app.rate_limit import retry_after_seconds


class DailySpend:
    """Estimated USD spent on the current UTC day, plus what questions still in
    flight hold against it; a new day starts from zero."""

    def __init__(self) -> None:
        self._day: dt.date | None = None
        self._total = 0.0
        self._held = 0.0

    def _roll(self, today: dt.date) -> None:
        if today != self._day:
            self._day, self._total, self._held = today, 0.0, 0.0

    def spent(self, today: dt.date) -> float:
        return self._total if today == self._day else 0.0

    def held(self, today: dt.date) -> float:
        return self._held if today == self._day else 0.0

    def record(self, today: dt.date, cost_usd: float) -> float:
        self._roll(today)
        self._total += cost_usd
        return self._total

    def reserve(self, today: dt.date, amount_usd: float, cap_usd: float) -> Reservation | None:
        """Hold a question's worst-case cost, or None when it would not fit under
        the cap. Checked and held with no await between, so concurrent questions
        cannot all pass on the same remaining budget."""
        self._roll(today)
        if self._total + self._held + amount_usd > cap_usd:
            return None
        self._held += amount_usd
        return Reservation(self, today, amount_usd)

    def _settle(self, day: dt.date, held_usd: float, cost_usd: float) -> float:
        # A question that ran past midnight: the reset already dropped its hold,
        # and its cost belongs to a day that is over.
        if day == self._day:
            self._held = max(0.0, self._held - held_usd)
            self._total += cost_usd
        return self._total


class Reservation:
    """One admitted question's hold. The first settle or release ends it; any
    later call is a no-op, so a release after the real cost is recorded keeps it."""

    def __init__(self, spend: DailySpend, day: dt.date, amount_usd: float) -> None:
        self._spend = spend
        self._day = day
        self.amount_usd = amount_usd
        self._open = True

    def settle(self, cost_usd: float) -> float:
        """Replace the hold with the real cost; returns today's spend."""
        if self._open:
            self._open = False
            return self._spend._settle(self._day, self.amount_usd, cost_usd)
        return self._spend.spent(self._day)

    def release(self) -> None:
        self.settle(0.0)


spend = DailySpend()


def question_retry_after(client_ip: str, per_day: int) -> int | None:
    """Count one question; seconds until the client may ask again, or None."""
    return retry_after_seconds(client_ip, RateRule(f"{per_day}/day", "ask_daily"))
