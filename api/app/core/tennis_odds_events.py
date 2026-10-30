"""Deciding whether an Odds-API.io tennis event is a given stored match."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Optional

# The same window prop linking uses: a real start can drift from the scheduled one,
# but the same two players rarely meet twice within half a day.
MAX_START_GAP = timedelta(hours=12)


def odds_event_tour(league_name: str) -> Optional[str]:
    """Tour for an ATP, WTA, or Challenger singles league, or None for anything else.

    Odds-API.io names leagues "<circuit> - <event>", e.g. "ATP - Chengdu, China",
    "WTA 125K - Adana, Turkiye", "Challenger - Bari, Italy", with doubles suffixed
    ", Doubles". ITF events arrive as "Tennis - ITF ...", and UTR, team cups, and
    exhibitions under their own circuit names, so none of them map to a tour.
    """
    if "Doubles" in league_name or "Mixed" in league_name:
        return None
    circuit = league_name.split(" - ", 1)[0].strip()
    if circuit == "ATP":
        return "ATP"
    if circuit == "WTA" or circuit.startswith("WTA 125"):
        return "WTA"
    if circuit == "Challenger":
        return "CHALLENGER"
    return None


def tour_level_circuit(league_name: str) -> str | None:
    """ATP or WTA for a main-tour singles league, or None for anything else.

    Unlike odds_event_tour, WTA 125 and Challenger are left out: the 48d probe asks
    what books price on main-tour singles only.
    """
    if "Doubles" in league_name or "Mixed" in league_name:
        return None
    circuit = league_name.split(" - ", 1)[0].strip()
    return circuit if circuit in ("ATP", "WTA") else None


def near_start_events(events: list[dict], now: datetime, within_hours: float, limit: int) -> list[dict]:
    """Main-tour singles events starting after now and within the window, soonest first."""
    horizon = now + timedelta(hours=within_hours)
    timed: list[tuple[datetime, dict]] = []
    for event in events:
        if event.get("id") is None:
            continue
        if tour_level_circuit((event.get("league") or {}).get("name") or "") is None:
            continue
        start = event_start(event)
        if start is None or not now < start <= horizon:
            continue
        timed.append((start, event))
    timed.sort(key=lambda pair: pair[0])
    return [event for _, event in timed[:limit]]


def event_start(event: dict) -> Optional[datetime]:
    """UTC start of an Odds-API.io event, or None when absent or unparseable."""
    raw = event.get("start") or event.get("date") or event.get("commenceTime")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _tokens(name: str) -> list[str]:
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    # Any non-letter separates words: hyphens, commas ("Legout, Timo"), and the
    # non-breaking spaces some stored names carry.
    return re.sub(r"[^a-z]+", " ", name.lower()).split()


_SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv"})


def _without_suffix(tokens: list[str]) -> list[str]:
    # "Martin Damm Jr" must compare on "damm": one source adds the suffix, another drops it.
    return tokens[:-1] if len(tokens) > 1 and tokens[-1] in _SUFFIXES else tokens


def _names_player(db_name: str, api_name: str) -> bool:
    db, api = _without_suffix(_tokens(db_name)), _without_suffix(_tokens(api_name))
    if not db or not api:
        return False
    # Whole-token surname match, so "Li" never matches "Lin".
    return db[-1] in api


# Box-score joining uses the same rule, so one name comparison serves both sources.
names_player = _names_player


def match_event(
    p1_name: str,
    p2_name: str,
    home: str,
    away: str,
    match_start: Optional[datetime] = None,
    event_start: Optional[datetime] = None,
) -> Optional[bool]:
    """Whether home is p1 when the event is this match, or None when it is not.

    Orientation comes from the pairing that matched, so it cannot disagree with the
    match test. A pairing that fits both ways (siblings sharing a surname) is
    refused rather than guessed, since a wrong guess swaps every price.
    """
    if match_start is not None and event_start is not None:
        if abs(event_start - match_start) > MAX_START_GAP:
            return None
    straight = _names_player(p1_name, home) and _names_player(p2_name, away)
    reversed_ = _names_player(p1_name, away) and _names_player(p2_name, home)
    if straight == reversed_:
        return None
    return straight
