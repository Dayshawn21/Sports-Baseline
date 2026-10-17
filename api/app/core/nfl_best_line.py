"""Each side's best price across books, beside a de-vigged fair price (item 36b).

A line-shopping reference, never a pick. Pinnacle is the fair price and is
never a candidate; quotes older than `MAX_AGE_HOURS` are dropped rather than
shown stale. Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from app.core.odds import american_to_decimal

# Sunday's last Pinnacle refresh (12:10 UTC) still covers Monday night's kickoff.
MAX_AGE_HOURS = 36
PINNACLE = "pinnacle"
MARKETS = ("moneyline", "spread", "total")
SIDES = {"moneyline": ("home", "away"), "spread": ("home", "away"), "total": ("over", "under")}

FairSource = Literal["pinnacle", "consensus"]


@dataclass(frozen=True)
class Quote:
    """One book's latest pre-kickoff two-way price; `line` is the home spread in book sign, or the total."""

    book: str
    provider: str
    market: str
    line: float | None
    first_odds: int
    second_odds: int
    first_probability: float
    fetched_at: datetime


@dataclass(frozen=True)
class Fair:
    source: FairSource
    line: float | None
    first_probability: float
    fetched_at: datetime


@dataclass(frozen=True)
class BestSide:
    side: str
    line: float | None
    odds: int
    book: str
    provider: str
    fetched_at: datetime
    ev_pct: float | None
    points_vs_fair: float | None


@dataclass(frozen=True)
class MarketBest:
    market: str
    fair: Fair | None
    sides: list[BestSide]


def _newest_per_book(quotes: Sequence[Quote]) -> list[Quote]:
    newest: dict[str, Quote] = {}
    for quote in quotes:
        if quote.book not in newest or quote.fetched_at > newest[quote.book].fetched_at:
            newest[quote.book] = quote
    return list(newest.values())


def _side_points(market: str, index: int, line: float | None) -> float:
    """Points from the side's own view, higher is better (more points taken, or a better total)."""
    if line is None or market == "moneyline":
        return 0.0
    if market == "spread":
        return line if index == 0 else -line
    return -line if index == 0 else line


def _best(market: str, index: int, candidates: Sequence[Quote]) -> Quote:
    def key(quote: Quote) -> tuple[float, float, float, str]:
        odds = quote.first_odds if index == 0 else quote.second_odds
        return (-_side_points(market, index, quote.line), -american_to_decimal(odds), -quote.fetched_at.timestamp(), quote.book)
    return min(candidates, key=key)


def _fair(pinnacle: Quote | None, candidates: Sequence[Quote]) -> Fair | None:
    if pinnacle is not None:
        return Fair("pinnacle", pinnacle.line, pinnacle.first_probability, pinnacle.fetched_at)
    lines = Counter(quote.line for quote in candidates)
    if not lines:
        return None
    line, count = min(lines.items(), key=lambda item: (-item[1], item[0] if item[0] is not None else 0.0))
    if count < 2:
        return None
    at_line = [quote for quote in candidates if quote.line == line]
    probability = sum(quote.first_probability for quote in at_line) / len(at_line)
    return Fair("consensus", line, probability, max(quote.fetched_at for quote in at_line))


def _side(market: str, index: int, quote: Quote, fair: Fair | None) -> BestSide:
    odds = quote.first_odds if index == 0 else quote.second_odds
    ev_pct = points_vs_fair = None
    if fair is not None and (market == "moneyline" or quote.line == fair.line):
        probability = fair.first_probability if index == 0 else 1 - fair.first_probability
        ev_pct = american_to_decimal(odds) * probability - 1
    elif fair is not None:
        points_vs_fair = _side_points(market, index, quote.line) - _side_points(market, index, fair.line)
    return BestSide(SIDES[market][index], quote.line, odds, quote.book, quote.provider, quote.fetched_at, ev_pct, points_vs_fair)


def best_lines(quotes: Sequence[Quote], now: datetime) -> list[MarketBest]:
    """Per market, each side's best candidate price and the fair price it is read against."""
    fresh = [quote for quote in quotes if now - quote.fetched_at <= timedelta(hours=MAX_AGE_HOURS)]
    result = []
    for market in MARKETS:
        in_market = [quote for quote in fresh if quote.market == market]
        candidates = _newest_per_book([quote for quote in in_market if quote.book != PINNACLE])
        if not candidates:
            continue
        pinnacle = max((quote for quote in in_market if quote.book == PINNACLE), key=lambda quote: quote.fetched_at, default=None)
        fair = _fair(pinnacle, candidates)
        sides = [_side(market, index, _best(market, index, candidates), fair) for index in (0, 1)]
        result.append(MarketBest(market, fair, sides))
    return result
