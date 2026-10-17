"""
ingest/odds_api.py

Fetches tennis match odds from Odds-API.io and writes them to `match_odds`.

Bookmakers:
  - DraftKings: moneyline, totals, set winner markets
  - Bet365: moneyline, match total, game spread, set handicap (stored as betonline.ag before 2026-09-25)

ENV VARS:
  ODDS_API_KEY   — required
  DATABASE_URL   — in api/app/.env

Run:
    python -m app.ingest.odds_api                      # next 4 hours
    python -m app.ingest.odds_api --hours-ahead 12
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

from app.core.bookmakers import bookmaker_scope_param
from app.core.tennis_odds_events import event_start, match_event, odds_event_tour
from app.ingest.log_config import configure_ingest_logging

logger = logging.getLogger("odds_api_ingest")
configure_ingest_logging()

BASE_URL = "https://api.odds-api.io/v3"
DEFAULT_BOOKMAKERS = "DraftKings,Bet365"
BATCH_SIZE = 10
DEFAULT_MIN_REQUESTS_REMAINING = 5
DEFAULT_INVENTORY_OUTPUT = Path(__file__).resolve().parents[3] / "docs" / "odds-market-inventory.md"

DONE_STATUSES = ("completed", "cancelled", "live")


@dataclass(frozen=True)
class RateLimitState:
    limit: int | None = None
    remaining: int | None = None
    reset: str | None = None

    @property
    def present(self) -> bool:
        return self.limit is not None or self.remaining is not None or self.reset is not None


@dataclass(frozen=True)
class BookmakerMarketInventory:
    """One bookmaker and the raw market names returned for it."""

    bookmaker: str
    markets: tuple[str, ...]


@dataclass(frozen=True)
class StoredMarketRow:
    market: str
    p1_odds: int | None
    p2_odds: int | None
    line: float | None = None


@dataclass(frozen=True)
class BookConfig:
    canonical_name: str
    aliases: tuple[str, ...]
    standard_parser: Callable[[list[dict]], dict] | None
    standard_markets: tuple[str, ...]
    spread_parser: Callable[[list[dict]], dict] | None
    spread_markets: tuple[str, ...]


def _parse_int_header(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _rate_limit_state(headers: Any) -> RateLimitState:
    return RateLimitState(
        limit=_parse_int_header(headers.get("x-ratelimit-limit")),
        remaining=_parse_int_header(headers.get("x-ratelimit-remaining")),
        reset=headers.get("x-ratelimit-reset"),
    )


def _quota_too_low(state: RateLimitState, min_remaining: int) -> bool:
    return state.remaining is not None and state.remaining <= max(0, min_remaining)


def _log_rate_limit_state(label: str, state: RateLimitState) -> None:
    if not state.present:
        return
    logger.info(
        "Odds API quota after %s: remaining=%s limit=%s reset=%s",
        label,
        state.remaining if state.remaining is not None else "?",
        state.limit if state.limit is not None else "?",
        state.reset or "?",
    )


def _bookmaker_markets(bookmakers: Any, aliases: list[str]) -> list[dict]:
    """
    Extract market list for a bookmaker across possible response shapes.
    Supports:
      - dict: {"DraftKings": [...], "bet365": [...]}
      - list: [{"key":"draftkings","markets":[...]}]
    """
    if not bookmakers:
        return []

    alias_set = {a.lower() for a in aliases}

    if isinstance(bookmakers, dict):
        for key, value in bookmakers.items():
            if str(key).lower() in alias_set and isinstance(value, list):
                return value
        return []

    if isinstance(bookmakers, list):
        for item in bookmakers:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or item.get("name") or "").lower()
            if key in alias_set:
                markets = item.get("markets")
                if isinstance(markets, list):
                    return markets
        return []

    return []


def _iter_bookmaker_market_sets(bookmakers: Any) -> list[tuple[str, list[dict]]]:
    """
    Return (bookmaker_name, markets) pairs across known response shapes.
    """
    pairs: list[tuple[str, list[dict]]] = []
    if not bookmakers:
        return pairs

    if isinstance(bookmakers, dict):
        for key, value in bookmakers.items():
            if isinstance(value, list):
                pairs.append((str(key), value))
        return pairs

    if isinstance(bookmakers, list):
        for item in bookmakers:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("key") or "").strip()
            markets = item.get("markets")
            if name and isinstance(markets, list):
                pairs.append((name, markets))
        return pairs

    return pairs


def bookmaker_market_inventory(bookmakers: Any) -> list[BookmakerMarketInventory]:
    """Return stable bookmaker and raw-market inventory from an odds response."""
    names_by_key: dict[str, set[str]] = {}
    markets_by_key: dict[str, set[str]] = {}
    for bookmaker, markets in _iter_bookmaker_market_sets(bookmakers):
        name = bookmaker.strip()
        if not name:
            continue
        key = name.casefold()
        names_by_key.setdefault(key, set()).add(name)
        market_names = markets_by_key.setdefault(key, set())
        for market in markets:
            if not isinstance(market, dict):
                continue
            market_name = str(market.get("name") or "").strip()
            if market_name:
                market_names.add(market_name)
    return [
        BookmakerMarketInventory(
            bookmaker=min(names_by_key[key], key=lambda value: (value.casefold(), value)),
            markets=tuple(sorted(markets_by_key[key], key=lambda value: (value.casefold(), value))),
        )
        for key in sorted(names_by_key)
    ]


def event_market_inventory(events: list[dict]) -> list[BookmakerMarketInventory]:
    """Return one bookmaker inventory merged across an odds event batch."""
    bookmaker_sets: list[dict] = []
    for event in events:
        bookmakers = event.get("bookmakers")
        for bookmaker, markets in _iter_bookmaker_market_sets(bookmakers):
            bookmaker_sets.append({"name": bookmaker, "markets": markets})
    return bookmaker_market_inventory(bookmaker_sets)


def render_market_inventory(
    inventory: list[BookmakerMarketInventory],
    captured_at: datetime,
    request_scope: str,
    result: str | None = None,
) -> str:
    """Render the safe, durable portion of a provider inventory capture."""
    lines = [
        "# Odds market inventory",
        "",
        f"- Captured at: {captured_at.isoformat()}",
        f"- Request scope: {request_scope}",
    ]
    if result:
        lines.append(f"- Result: {result}")
    lines.extend(("", "| Bookmaker | Markets |", "|---|---|"))
    for entry in inventory:
        markets = ", ".join(entry.markets) or "No named markets returned"
        lines.append(f"| {entry.bookmaker} | {markets} |")
    return "\n".join(lines) + "\n"


def _find_set_spread_markets(bookmakers: Any) -> dict[str, set[str]]:
    """
    Detect bookmaker markets that look like tennis set spread/handicap.
    """
    hits: dict[str, set[str]] = {}
    for book_name, markets in _iter_bookmaker_market_sets(bookmakers):
        for market in markets:
            if not isinstance(market, dict):
                continue
            market_name = str(market.get("name") or "").strip()
            if not market_name:
                continue
            m = market_name.lower()
            if "set" in m and any(k in m for k in ("spread", "handicap", "asian")):
                hits.setdefault(book_name, set()).add(market_name)
    return hits


# =============================================================================
# Odds conversion
# =============================================================================

def _decimal_to_american(dec: Any) -> Optional[int]:
    try:
        d = float(dec)
        if d <= 1.0:
            return None
        if d >= 2.0:
            return round((d - 1) * 100)
        return round(-100 / (d - 1))
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _safe_float(val: Any) -> Optional[float]:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


# =============================================================================
# Market parsers
# =============================================================================

def _parse_draftkings(markets: list[dict]) -> dict:
    """Returns p1/p2 moneyline, totals, and set winner odds (American)."""
    result: dict = {
        "p1_odds": None, "p2_odds": None,
        "total_line": None, "total_over": None, "total_under": None,
        "set1_p1_odds": None, "set1_p2_odds": None,
        "set2_p1_odds": None, "set2_p2_odds": None,
    }
    for mkt in markets:
        name = (mkt.get("name") or "").lower().strip()
        odds_list = [o for o in (mkt.get("odds") or []) if isinstance(o, dict) and o]
        if not odds_list:
            continue
        o = odds_list[0]

        if "1st set" in name and any(x in name for x in ["ml", "moneyline", "winner"]):
            result["set1_p1_odds"] = _decimal_to_american(o.get("home"))
            result["set1_p2_odds"] = _decimal_to_american(o.get("away"))
        elif "2nd set" in name and any(x in name for x in ["ml", "moneyline", "winner"]):
            result["set2_p1_odds"] = _decimal_to_american(o.get("home"))
            result["set2_p2_odds"] = _decimal_to_american(o.get("away"))
        elif name in ("ml", "h2h", "moneyline", "winner", "match winner", "match ml"):
            result["p1_odds"] = _decimal_to_american(o.get("home"))
            result["p2_odds"] = _decimal_to_american(o.get("away"))
        elif _is_match_total_market(name):
            main = _main_total_line(odds_list)
            if main is not None:
                result["total_line"] = _safe_float(main.get("hdp"))
                result["total_over"] = _decimal_to_american(main.get("over"))
                result["total_under"] = _decimal_to_american(main.get("under"))
    return result


# Books list aces, double-fault, team, and first-set totals beside the match total,
# e.g. Bet365's "Totals (Games)" next to "Totals (Aces)" and "Team Total (Games) Home".
# A loose "total" test stored whichever came last, so only these exact names count.
_MATCH_TOTAL_NAMES = frozenset({"total games", "totals games", "totals", "total"})


def _is_match_total_market(name: str) -> bool:
    words = "".join(c if c.isalpha() else " " for c in name.lower()).split()
    return " ".join(words) in _MATCH_TOTAL_NAMES


def _main_total_line(odds_list: list[dict]) -> Optional[dict]:
    """The main line: the two-sided entry priced closest to even.

    Entries without both sides are ladder rungs (alternate overs), and the old
    "nearest 21.5 games" rule picked those as readily as the real line.
    """
    two_sided = []
    for entry in odds_list:
        over, under = _safe_float(entry.get("over")), _safe_float(entry.get("under"))
        if _safe_float(entry.get("hdp")) is None or not over or not under or over <= 1 or under <= 1:
            continue
        two_sided.append((abs(1 / over - 1 / under), entry))
    return min(two_sided, key=lambda pair: pair[0])[1] if two_sided else None


def _parse_bet365_spread(markets: list[dict]) -> dict:
    """Returns game spread and set handicap lines + odds from Bet365."""
    result: dict = {
        "spread_line": None, "spread_p1_odds": None, "spread_p2_odds": None,
        "set_handicap_line": None, "set_handicap_p1_odds": None, "set_handicap_p2_odds": None,
    }
    for mkt in markets:
        name = (mkt.get("name") or "").lower().strip()
        odds_list = [o for o in (mkt.get("odds") or []) if isinstance(o, dict) and o]
        if not odds_list:
            continue
        o = odds_list[0]
        if "total" in name or "winner" in name or "ml" in name:
            continue
        if ("spread" in name or "handicap" in name or "asian" in name) and "set" in name:
            hdp = _safe_float(o.get("hdp"))
            result["set_handicap_line"] = hdp
            result["set_handicap_p1_odds"] = _decimal_to_american(o.get("home"))
            result["set_handicap_p2_odds"] = _decimal_to_american(o.get("away"))
        elif "spread" in name or "handicap" in name or "asian" in name or "game" in name:
            hdp = _safe_float(o.get("hdp"))
            if hdp is not None:
                result["spread_line"] = hdp
                result["spread_p1_odds"] = _decimal_to_american(o.get("home"))
                result["spread_p2_odds"] = _decimal_to_american(o.get("away"))
    return result


def _orient_standard_markets(parsed: dict, home_is_p1: bool) -> dict:
    if home_is_p1:
        return parsed
    oriented = dict(parsed)
    for left, right in (
        ("p1_odds", "p2_odds"),
        ("set1_p1_odds", "set1_p2_odds"),
        ("set2_p1_odds", "set2_p2_odds"),
    ):
        oriented[left], oriented[right] = oriented[right], oriented[left]
    return oriented


def _orient_spread_markets(parsed: dict, home_is_p1: bool) -> dict:
    if home_is_p1:
        return parsed
    oriented = dict(parsed)
    for line_key, left, right in (
        ("spread_line", "spread_p1_odds", "spread_p2_odds"),
        ("set_handicap_line", "set_handicap_p1_odds", "set_handicap_p2_odds"),
    ):
        if oriented[line_key] is not None:
            oriented[line_key] = -oriented[line_key]
        oriented[left], oriented[right] = oriented[right], oriented[left]
    return oriented


def _bookmaker_market_rows(config: BookConfig, markets: list[dict], home_is_p1: bool) -> list[StoredMarketRow]:
    rows: list[StoredMarketRow] = []
    if config.standard_parser is not None:
        standard = _orient_standard_markets(config.standard_parser(markets), home_is_p1)
        field_map = {
            "moneyline": ("p1_odds", "p2_odds", None),
            "total_games": ("total_over", "total_under", "total_line"),
            "set1_winner": ("set1_p1_odds", "set1_p2_odds", None),
            "set2_winner": ("set2_p1_odds", "set2_p2_odds", None),
        }
        for market in config.standard_markets:
            p1_key, p2_key, line_key = field_map[market]
            line = standard[line_key] if line_key else None
            if (line_key and line is not None) or (not line_key and (standard[p1_key] or standard[p2_key])):
                rows.append(StoredMarketRow(market, standard[p1_key], standard[p2_key], line))

    if config.spread_parser is not None:
        spread = _orient_spread_markets(config.spread_parser(markets), home_is_p1)
        field_map = {
            "game_spread": ("spread_p1_odds", "spread_p2_odds", "spread_line"),
            "set_handicap": ("set_handicap_p1_odds", "set_handicap_p2_odds", "set_handicap_line"),
        }
        for market in config.spread_markets:
            p1_key, p2_key, line_key = field_map[market]
            if spread[line_key] is not None:
                rows.append(StoredMarketRow(market, spread[p1_key], spread[p2_key], spread[line_key]))
    return rows


BOOK_CONFIGS = (
    BookConfig(
        canonical_name="draftkings", aliases=("draftkings",),
        standard_parser=_parse_draftkings,
        standard_markets=("moneyline", "total_games", "set1_winner", "set2_winner"),
        spread_parser=None, spread_markets=(),
    ),
    BookConfig(
        canonical_name="betfair exchange",
        aliases=("betfair exchange", "betfair_exchange"),
        standard_parser=_parse_draftkings,
        standard_markets=("moneyline", "total_games", "set1_winner", "set2_winner"),
        spread_parser=_parse_bet365_spread, spread_markets=("game_spread",),
    ),
    BookConfig(
        canonical_name="bet365",
        aliases=("bet365", "betonline.ag", "betonline"),
        standard_parser=_parse_draftkings, standard_markets=("moneyline", "total_games"),
        spread_parser=_parse_bet365_spread, spread_markets=("game_spread", "set_handicap"),
    ),
)


# =============================================================================
# API helpers
# =============================================================================

async def _fetch_events(client: httpx.AsyncClient, api_key: str) -> list[dict]:
    r = await client.get(f"{BASE_URL}/events", params={"sport": "tennis", "apiKey": api_key}, timeout=30)
    r.raise_for_status()
    _log_rate_limit_state("events", _rate_limit_state(r.headers))
    data = r.json()
    return (data.get("data") or data.get("events") or []) if isinstance(data, dict) else (data or [])


async def _fetch_odds_batch(
    client: httpx.AsyncClient, api_key: str, event_ids: list[int], bookmakers: str
) -> tuple[list[dict], RateLimitState]:
    r = await client.get(
        f"{BASE_URL}/odds/multi",
        params={"eventIds": ",".join(str(i) for i in event_ids), "bookmakers": bookmakers, "apiKey": api_key},
        timeout=30,
    )
    r.raise_for_status()
    rate_limit = _rate_limit_state(r.headers)
    _log_rate_limit_state("odds batch", rate_limit)
    data = r.json()
    events = (data.get("data") or data.get("events") or []) if isinstance(data, dict) else (data or [])
    return events, rate_limit


def _inventory_event_ids(events: list[dict]) -> list[int]:
    event_ids: list[int] = []
    for event in events:
        try:
            event_id = int(event["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if event_id not in event_ids:
            event_ids.append(event_id)
        if len(event_ids) == BATCH_SIZE:
            break
    return event_ids


def _inventory_request_scope(bookmakers: str, event_count: int) -> str:
    return (
        "sport=tennis; one /events request; one /odds/multi request for "
        f"{event_count} event(s), up to {BATCH_SIZE}; bookmakers={bookmakers}"
    )


async def capture_market_inventory(
    output_path: Path,
    bookmakers: str | None = None,
    api_key: str | None = None,
) -> Path:
    """Capture one read-only tennis odds batch as a safe market inventory."""
    if api_key is None or bookmakers is None:
        from app.config import settings

        if api_key is None:
            api_key = settings.odds_api_key
        if bookmakers is None:
            bookmakers = settings.live_odds_bookmakers
    if not api_key:
        raise RuntimeError("ODDS_API_KEY is required - set it in api/app/.env")
    bookmaker_scope = bookmaker_scope_param(bookmakers)

    async with httpx.AsyncClient() as client:
        events = await _fetch_events(client, api_key)
        event_ids = _inventory_event_ids(events)
        scope = _inventory_request_scope(bookmaker_scope, len(event_ids))
        if not event_ids:
            report = render_market_inventory(
                [],
                datetime.now(timezone.utc),
                scope,
                "No active tennis events returned.",
            )
        else:
            odds_events, _ = await _fetch_odds_batch(client, api_key, event_ids, bookmaker_scope)
            inventory = event_market_inventory([event for event in odds_events if isinstance(event, dict)])
            result = None if inventory else "No bookmaker markets returned for the scoped batch."
            report = render_market_inventory(inventory, datetime.now(timezone.utc), scope, result)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    logger.info("Wrote odds market inventory to %s", output_path)
    return output_path


def _log_odds_api_limit_hint(status_code: int, response_text: str, bookmakers: str) -> None:
    msg = (response_text or "").strip().replace("\n", " ")
    short_msg = msg[:220] if msg else ""
    if status_code == 401:
        logger.error("Odds API auth error (401). Check ODDS_API_KEY. Response: %s", short_msg)
        return
    if status_code == 402:
        logger.error(
            "Odds API plan limit (402). Your tier may not include this odds endpoint/bookmaker set. "
            "bookmakers=%s response=%s",
            bookmakers,
            short_msg,
        )
        return
    if status_code == 403:
        logger.error(
            "Odds API forbidden (403). Access to requested markets/bookmakers may be blocked on your tier. "
            "bookmakers=%s response=%s",
            bookmakers,
            short_msg,
        )
        return
    if status_code == 429:
        logger.error(
            "Odds API rate limit (429). Slow request cadence or reduce hours-ahead/bookmakers. response=%s",
            short_msg,
        )
        return
    logger.error("Batch odds error: %s %s", status_code, short_msg)


# =============================================================================
# DB helpers
# =============================================================================

async def _load_upcoming(db, hours_ahead: int, limit: int) -> list[dict]:
    from sqlalchemy import text
    rows = await db.execute(
        text("""
            SELECT m.id AS match_id, m.start_utc, m.tour,
                   p1.name AS p1_name, p2.name AS p2_name
            FROM matches m
            JOIN players p1 ON p1.id = m.p1_id
            JOIN players p2 ON p2.id = m.p2_id
            WHERE m.start_utc IS NOT NULL
              AND m.start_utc >= NOW()
              AND m.start_utc <= (NOW() + (:hours || ' hours')::interval)
              AND m.status NOT IN ('completed', 'cancelled')
            ORDER BY m.start_utc ASC
            LIMIT :lim
        """),
        {"hours": hours_ahead, "lim": limit},
    )
    return [{"match_id": r[0], "start_utc": r[1], "tour": r[2], "p1_name": r[3], "p2_name": r[4]}
            for r in rows.fetchall()]


async def _insert_odds(db, match_id: int, book: str, market: str,
                        p1_odds: Optional[int], p2_odds: Optional[int],
                        line: Optional[float] = None) -> None:
    from app.repositories.matches import upsert_odds
    await upsert_odds(db, match_id, book, market, p1_odds, p2_odds, line)


# =============================================================================
# Main
# =============================================================================

async def run(hours_ahead: int = 8, sleep_sec: float = 0.1, limit: int = 300,
              bookmakers: str | None = None,
              min_requests_remaining: int = DEFAULT_MIN_REQUESTS_REMAINING) -> None:
    from app.config import settings
    from app.db.pool import SessionLocal

    bookmakers = bookmaker_scope_param(bookmakers or settings.live_odds_bookmakers)

    api_key = settings.odds_api_key if hasattr(settings, "odds_api_key") else None
    if not api_key:
        import os
        api_key = os.getenv("ODDS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ODDS_API_KEY is required — set it in .env or environment")

    async with SessionLocal() as db:
        candidates = await _load_upcoming(db, hours_ahead, limit)
        logger.info("Upcoming matches in next %dh: %d", hours_ahead, len(candidates))
        if not candidates:
            return

        async with httpx.AsyncClient() as client:
            logger.info("Fetching tennis events from Odds-API.io...")
            api_events = await _fetch_events(client, api_key)
            logger.info("Odds-API events: %d", len(api_events))

            singles_events = [
                ev for ev in api_events
                if odds_event_tour(((ev.get("league") or {}).get("name")) or "") is not None
            ]
            logger.info("Tour singles events: %d", len(singles_events))

            # Match DB rows to API events
            matched: list[dict] = []
            for row in candidates:
                for ev in singles_events:
                    home_is_p1 = match_event(
                        row["p1_name"], row["p2_name"],
                        ev.get("home", ""), ev.get("away", ""),
                        match_start=row["start_utc"], event_start=event_start(ev),
                    )
                    if home_is_p1 is not None:
                        matched.append({
                            "match_id": row["match_id"],
                            "odds_api_id": int(ev["id"]),
                            "p1_name": row["p1_name"],
                            "p2_name": row["p2_name"],
                            "home_is_p1": home_is_p1,
                        })
                        break
                else:
                    logger.debug("No Odds-API match: %s vs %s", row["p1_name"], row["p2_name"])

            logger.info("Matched %d / %d", len(matched), len(candidates))
            if not matched:
                return

            # Batch fetch odds
            odds_by_id: dict[int, dict] = {}
            blocked_by_plan = False
            event_ids = [m["odds_api_id"] for m in matched]
            for i in range(0, len(event_ids), BATCH_SIZE):
                batch = event_ids[i:i + BATCH_SIZE]
                try:
                    results, rate_limit = await _fetch_odds_batch(client, api_key, batch, bookmakers)
                    for ev in results:
                        odds_by_id[int(ev["id"])] = ev
                    if _quota_too_low(rate_limit, min_requests_remaining):
                        logger.warning(
                            "Stopping odds batch fetch with %s requests remaining at safety floor %s.",
                            rate_limit.remaining,
                            min_requests_remaining,
                        )
                        break
                except httpx.HTTPStatusError as e:
                    code = e.response.status_code
                    _log_odds_api_limit_hint(code, e.response.text, bookmakers)
                    if code in (402, 403):
                        blocked_by_plan = True
                        break
                if sleep_sec > 0:
                    await asyncio.sleep(sleep_sec)

            logger.info("Odds responses: %d", len(odds_by_id))
            if blocked_by_plan and not odds_by_id:
                logger.warning(
                    "Stopping ingest: current Odds API plan appears to block requested tennis odds data. "
                    "Try fewer/supported bookmakers on your tier."
                )
                return

            # Parse and insert
            updated_matches = 0
            inserted_rows = 0
            set_spread_books: dict[str, set[str]] = {}
            for m in matched:
                ev_data = odds_by_id.get(m["odds_api_id"])
                if not ev_data:
                    continue

                bks: dict = ev_data.get("bookmakers") or {}
                set_spread_hits = _find_set_spread_markets(bks)
                for book_name, market_names in set_spread_hits.items():
                    set_spread_books.setdefault(book_name, set()).update(market_names)
                home_is_p1: bool = m["home_is_p1"]
                mid = m["match_id"]
                inserted_for_match = 0

                for config in BOOK_CONFIGS:
                    markets = _bookmaker_markets(bks, list(config.aliases))
                    for row in _bookmaker_market_rows(config, markets, home_is_p1):
                        await _insert_odds(
                            db, mid, config.canonical_name, row.market,
                            row.p1_odds, row.p2_odds, row.line,
                        )
                        inserted_for_match += 1

                if inserted_for_match > 0:
                    updated_matches += 1
                    inserted_rows += inserted_for_match

            await db.commit()
            if set_spread_books:
                books_sorted = sorted(set_spread_books.keys(), key=lambda x: x.lower())
                logger.info("Bookmakers with tennis set spread/handicap markets: %s", ", ".join(books_sorted))
                for book_name in books_sorted:
                    logger.info(
                        "  %s markets: %s",
                        book_name,
                        ", ".join(sorted(set_spread_books[book_name], key=lambda x: x.lower())),
                    )
            else:
                logger.info("No tennis set spread/handicap markets found in the fetched bookmaker data.")
            logger.info("Done. Updated %d matches, inserted %d odds rows.", updated_matches, inserted_rows)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Refresh tennis odds from Odds-API.io")
    parser.add_argument("--hours-ahead", type=int, default=24)
    parser.add_argument("--sleep-sec", type=float, default=0.1)
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--bookmakers", type=str)
    parser.add_argument("--min-requests-remaining", type=int, default=DEFAULT_MIN_REQUESTS_REMAINING)
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--inventory-output", type=Path, default=DEFAULT_INVENTORY_OUTPUT)
    args = parser.parse_args()
    if args.inventory_only:
        await capture_market_inventory(args.inventory_output, bookmakers=args.bookmakers)
        return
    await run(
        hours_ahead=args.hours_ahead,
        sleep_sec=args.sleep_sec,
        limit=args.limit,
        bookmakers=args.bookmakers,
        min_requests_remaining=args.min_requests_remaining,
    )


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
