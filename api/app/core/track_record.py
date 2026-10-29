"""Color rules for the model track record pages, and the retired tennis tier verdict rule.

Shared by tennis (32b) and NFL (33d). A number earns a signal color only when it
clears its baseline by more than two standard errors. The tier rule was fixed on
2026-09-29, before any tier's graded picks were read; changing it after seeing
them would make the verdict worthless.

Pure: no database, no clock. The caller passes the as-of date.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import sqrt
from typing import Iterable, Literal, Optional

from app.core.prop_ev import STANDARD_LEG_DECIMAL

Signal = Literal["positive", "neutral", "negative"]
Verdict = Literal["accruing", "pass", "reject"]

SIGNAL_SE_MULTIPLE = 2.0

# History only: tennis props carry no tier since 48f (2026-10-28), so the 48a
# re-registration for props-v3 was withdrawn before any v3 row was graded by it.
TIER_RULE_VERSION = "props-v2"
TIER_RULE_TIERS = ("LOCK", "STRONG", "LEAN")
TIER_VERDICT_SAMPLE = 200
# Box-score stats settle after the next day's refetch (26e), so a snapshot day
# joins the sample only once its late picks have had time to land.
TIER_MATURITY_DAYS = 3
TIER_BREAK_EVEN = 1 / STANDARD_LEG_DECIMAL


def loss_signal(mean_diff: float, standard_error: Optional[float]) -> Signal:
    """Candidate minus baseline log loss. Losing to the market is expected, so never negative."""
    if standard_error is None:
        return "neutral"
    return "positive" if mean_diff + SIGNAL_SE_MULTIPLE * standard_error < 0 else "neutral"


def rate_signal(rate: float, standard_error: Optional[float], break_even: float) -> Signal:
    if standard_error is None:
        return "neutral"
    if rate - SIGNAL_SE_MULTIPLE * standard_error > break_even:
        return "positive"
    if rate + SIGNAL_SE_MULTIPLE * standard_error < break_even:
        return "negative"
    return "neutral"


def verdict_signal(
    decided: bool, value: Optional[float], standard_error: Optional[float], baseline: float,
) -> Signal:
    """A pre-registered result stays gray until its verdict is in, however far a running rate strays."""
    if not decided or value is None:
        return "neutral"
    return rate_signal(value, standard_error, baseline)


def binomial_standard_error(rate: float, n: int) -> Optional[float]:
    return sqrt(rate * (1 - rate) / n) if n else None


@dataclass(frozen=True)
class TierVerdict:
    verdict: Verdict
    sample_size: int
    """Decided picks in the verdict sample, or on the mature days so far while accruing."""
    hit_rate: Optional[float]
    standard_error: Optional[float]
    signal: Signal


def tier_verdict(picks: Iterable[tuple[date, bool]], as_of: date) -> TierVerdict:
    """Verdict for one tier from (snapshot day, hit) pairs of decided standard picks.

    The sample is the first whole mature days holding TIER_VERDICT_SAMPLE picks, so
    it can run slightly past 200 and never moves once filled.
    """
    last_mature_day = as_of - timedelta(days=TIER_MATURITY_DAYS)
    by_day: dict[date, list[bool]] = {}
    for day, hit in picks:
        if day <= last_mature_day:
            by_day.setdefault(day, []).append(hit)

    sample: list[bool] = []
    for day in sorted(by_day):
        if len(sample) >= TIER_VERDICT_SAMPLE:
            break
        sample.extend(by_day[day])

    n = len(sample)
    hit_rate = sum(sample) / n if n else None
    se = binomial_standard_error(hit_rate, n) if hit_rate is not None else None
    if n < TIER_VERDICT_SAMPLE:
        return TierVerdict("accruing", n, hit_rate, se, "neutral")
    signal = rate_signal(hit_rate, se, TIER_BREAK_EVEN)
    return TierVerdict("pass" if signal == "positive" else "reject", n, hit_rate, se, signal)
