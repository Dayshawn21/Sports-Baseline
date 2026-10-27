"""Pure parsing of Odds-API.io NFL game markets into `sport_game_odds` rows (item 36a).

Odds-API.io sends decimal prices as strings, keyed by book name, and Bet365's
spread as a ladder of alternate lines. The main line is the rung with the
least vig, because alternates carry more margin than the line the book
actually sets (on 2026-10-07 Bet365's DAL -9.5 carried 1.050, the rungs
beside it about 1.09). FanDuel's total ladder is the exception at its ends,
so rungs priced past `MAX_MAIN_LINE_PROBABILITY` are set aside first.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite

from app.core.nfl_odds import NflGameMarket
from app.core.odds import decimal_to_american, devig_two_way, near_even_rungs

_MARKETS = {"ML": "moneyline", "Spread": "spread", "Totals": "total"}


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _decimal(value: object) -> float | None:
    number = _number(value)
    return number if number is not None and number > 1.0 else None


def _main_rung(rungs: Sequence[Mapping[str, object]], first: str, second: str) -> Mapping[str, object] | None:
    """Among near-even two-sided rungs, the lowest overround, then the one closest to even."""
    priced = []
    for rung in rungs:
        first_price, second_price = _decimal(rung.get(first)), _decimal(rung.get(second))
        if first_price is not None and second_price is not None:
            priced.append((first_price, second_price, rung))
    if not priced:
        return None
    candidates = near_even_rungs(priced, lambda item: (item[0], item[1]))
    return min(candidates, key=lambda item: (1 / item[0] + 1 / item[1], abs(item[0] - item[1])))[2]


def _row(market: str, line: float | None, sides: tuple[str, str], prices: tuple[float, float], raw: Mapping[str, object]) -> NflGameMarket:
    first_probability, second_probability = devig_two_way(1 / prices[0], 1 / prices[1])
    return NflGameMarket(
        market, line, sides[0], sides[1], decimal_to_american(prices[0]), decimal_to_american(prices[1]),
        first_probability, second_probability, dict(raw),
    )


def _parse_market(name: str, raw: Mapping[str, object], home_is_stored_home: bool) -> NflGameMarket | None:
    rungs = raw.get("odds")
    if not isinstance(rungs, list):
        return None
    market = _MARKETS[name]
    first, second = ("over", "under") if market == "total" else ("home", "away")
    rung = _main_rung([item for item in rungs if isinstance(item, Mapping)], first, second)
    if rung is None:
        return None
    prices = (float(rung[first]), float(rung[second]))  # _main_rung only returns priced rungs
    line = _number(rung.get("hdp"))
    # Keep the chosen rung, not the ladder: Bet365's runs to 77 rungs per game per fetch.
    raw = {"name": name, "updatedAt": raw.get("updatedAt"), "odds": [dict(rung)], "rungs": len(rungs)}
    if market != "moneyline" and line is None:
        return None
    if market == "total":
        return _row(market, line, ("over", "under"), prices, raw)
    if not home_is_stored_home:
        # The provider's home is the stored away team: swap prices and restate the line for the stored home.
        prices = (prices[1], prices[0])
        line = None if line is None else -line
    return _row(market, None if market == "moneyline" else line, ("home", "away"), prices, raw)


def parse_io_game_markets(markets: Sequence[Mapping[str, object]], home_is_stored_home: bool) -> list[NflGameMarket]:
    """One book's moneyline, main spread and main total; `hdp` is the home handicap in book sign."""
    parsed = []
    for raw in markets:
        name = raw.get("name")
        if isinstance(name, str) and name in _MARKETS:
            row = _parse_market(name, raw, home_is_stored_home)
            if row is not None:
                parsed.append(row)
    return parsed
