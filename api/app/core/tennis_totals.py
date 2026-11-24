"""Tennis total-games lines from The Odds API (item 48b). Pure: no DB, no I/O.

Odds-API.io's free books (DraftKings, FanDuel) send tennis moneylines only, so
the book total that prop projections anchor on comes from The Odds API's
tour-level tennis keys instead.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.core.odds import decimal_to_american
from app.core.tennis_odds_events import match_event

# Pinnacle is the sharpest line; the rest are the `eu` books that priced all or
# most of the 2026-10-28 Basel probe, for matches Pinnacle has not posted.
BOOK_PREFERENCE = ("pinnacle", "marathonbet", "betsson", "nordicbet", "onexbet", "coolbet")


@dataclass(frozen=True)
class TennisTotal:
    book: str
    line: float
    over: int
    under: int


def _price(value: object) -> float | None:
    try:
        price = float(str(value))
    except ValueError:
        return None
    return price if price > 1 else None


def _main_total(outcomes: Sequence[Mapping[str, object]]) -> tuple[float, float, float] | None:
    """(line, over, under) in decimal for the two-sided rung priced closest to even."""
    sides: dict[float, dict[str, float]] = {}
    for outcome in outcomes:
        price = _price(outcome.get("price"))
        try:
            point = float(str(outcome.get("point")))
        except ValueError:
            continue
        name = str(outcome.get("name") or "").casefold()
        if price is not None and name in ("over", "under"):
            sides.setdefault(point, {})[name] = price
    rungs = [(point, s["over"], s["under"]) for point, s in sides.items() if len(s) == 2]
    return min(rungs, key=lambda r: abs(1 / r[1] - 1 / r[2])) if rungs else None


def book_totals(event: Mapping[str, object]) -> dict[str, TennisTotal]:
    """Each book's main match total for one The Odds API event, keyed by book."""
    totals: dict[str, TennisTotal] = {}
    bookmakers = event.get("bookmakers")
    for bookmaker in bookmakers if isinstance(bookmakers, list) else []:
        book = str(bookmaker.get("key") or "").casefold()
        for market in bookmaker.get("markets") or []:
            if market.get("key") != "totals":
                continue
            main = _main_total(market.get("outcomes") or [])
            if book and main is not None:
                line, over, under = main
                totals[book] = TennisTotal(book, line, decimal_to_american(over), decimal_to_american(under))
    return totals


def preferred_total(event: Mapping[str, object]) -> TennisTotal | None:
    """The first book in `BOOK_PREFERENCE` that prices the event's total."""
    totals = book_totals(event)
    return next((totals[book] for book in BOOK_PREFERENCE if book in totals), None)


def _commence_time(event: Mapping[str, object]) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(str(event.get("commence_time") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def match_stored(event: Mapping[str, object], matches: Sequence[Mapping[str, object]]) -> int | None:
    """The stored match id this event is, or None unless exactly one match fits."""
    home, away = str(event.get("home_team") or ""), str(event.get("away_team") or "")
    start = _commence_time(event)
    found = [
        int(str(m["match_id"]))
        for m in matches
        if match_event(
            str(m["p1_name"]), str(m["p2_name"]), home, away,
            match_start=m.get("start_utc") if isinstance(m.get("start_utc"), dt.datetime) else None,
            event_start=start,
        ) is not None
    ]
    return found[0] if len(found) == 1 else None
