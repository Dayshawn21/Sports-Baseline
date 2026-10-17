"""
ingest/prizepicks.py

Fetches PrizePicks player prop lines for tennis (ATP + WTA) and stores them
in the `props` table, attempting to link each prop to a canonical player.

PrizePicks exposes a public API — no API key required.

Run:
    python -m app.ingest.prizepicks               # fetch and store
    python -m app.ingest.prizepicks --dry-run     # print only, no DB write
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
import sys
from typing import Optional

import httpx

from app.ingest.log_config import configure_ingest_logging

logger = logging.getLogger("prizepicks_ingest")
configure_ingest_logging()

PRIZEPICKS_BASE = "https://partner-api.prizepicks.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://app.prizepicks.com/",
    "Origin": "https://app.prizepicks.com",
}


# =============================================================================
# PrizePicks API helpers
# =============================================================================

async def _fetch_leagues(client: httpx.AsyncClient) -> list[dict]:
    """Fetch the league catalog, retrying throttled responses.

    A swallowed 429 here is indistinguishable from "this sport has no leagues",
    which silently turns a rate-limited run into an apparently empty one.
    """
    try:
        for attempt in range(1, RATE_LIMIT_ATTEMPTS + 1):
            r = await client.get(f"{PRIZEPICKS_BASE}/leagues", headers=HEADERS, timeout=15)
            if r.status_code == 429 and attempt < RATE_LIMIT_ATTEMPTS:
                wait_s = retry_after_seconds(r, attempt)
                logger.warning(
                    "  leagues: HTTP 429, retrying in %ss (attempt %d/%d)",
                    wait_s, attempt, RATE_LIMIT_ATTEMPTS,
                )
                await asyncio.sleep(wait_s)
                continue
            r.raise_for_status()
            return r.json().get("data") or []
    except Exception as e:
        logger.warning("Could not fetch leagues: %s", e)
    return []


RATE_LIMIT_ATTEMPTS = 5
RATE_LIMIT_MAX_WAIT_S = 120.0
# Some PrizePicks leagues answer 429 with "Retry-After: 0", which would otherwise
# spend the whole retry budget in a tight loop.
RATE_LIMIT_MIN_WAIT_S = 1.0


def retry_after_seconds(response: httpx.Response, attempt: int) -> float:
    """Wait before the next 429 retry, preferring the provider's own instruction.

    PrizePicks throttles hard enough that the previous 2s/4s ramp exhausted all
    retries inside a window it never intended to reopen that fast.
    """
    header = (response.headers.get("Retry-After") or "").strip()
    if header:
        try:
            return min(max(float(header), RATE_LIMIT_MIN_WAIT_S), RATE_LIMIT_MAX_WAIT_S)
        except ValueError:
            pass
    return min(5.0 * (2 ** (attempt - 1)), RATE_LIMIT_MAX_WAIT_S)


async def _fetch_projections(client: httpx.AsyncClient, league_id: int) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, RATE_LIMIT_ATTEMPTS + 1):
        try:
            r = await client.get(
                f"{PRIZEPICKS_BASE}/projections",
                params={"league_id": league_id, "per_page": 250, "single_stat": "True"},
                headers=HEADERS,
                timeout=20,
            )
            if r.status_code == 429 and attempt < RATE_LIMIT_ATTEMPTS:
                wait_s = retry_after_seconds(r, attempt)
                logger.warning(
                    "  league %d: HTTP 429, retrying in %ss (attempt %d/%d)",
                    league_id, wait_s, attempt, RATE_LIMIT_ATTEMPTS,
                )
                await asyncio.sleep(wait_s)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_error = e
            if attempt < RATE_LIMIT_ATTEMPTS:
                await asyncio.sleep(min(5.0 * (2 ** (attempt - 1)), RATE_LIMIT_MAX_WAIT_S))
                continue
            raise
    raise last_error or RuntimeError(f"Failed to fetch projections for league {league_id}")


def _parse_projections(raw: dict, league_id: int) -> list[dict]:
    """Parse JSON:API projections response into flat dicts."""
    players: dict[str, dict] = {}
    for inc in raw.get("included") or []:
        if inc.get("type") == "new_player":
            players[str(inc["id"])] = inc.get("attributes") or {}

    results = []
    for item in raw.get("data") or []:
        if item.get("type") != "projection":
            continue

        attrs = item.get("attributes") or {}
        stat_type = attrs.get("stat_type") or ""
        line_score = attrs.get("line_score")
        if line_score is None or not stat_type:
            continue

        # Resolve player name
        player_id = None
        rels = item.get("relationships") or {}
        player_data = (rels.get("new_player") or {}).get("data") or {}
        if isinstance(player_data, dict):
            player_id = str(player_data.get("id", ""))

        player_attrs = players.get(player_id, {}) if player_id else {}
        player_name = player_attrs.get("name") or attrs.get("player_display_name") or ""
        position = player_attrs.get("position") or player_attrs.get("sport") or ""
        tour: Optional[str] = position.upper() if position.upper() in ("ATP", "WTA") else None
        event_id = None
        for rel_name in ("game", "league_game", "projection_game"):
            rel_data = ((rels.get(rel_name) or {}).get("data") or {})
            if isinstance(rel_data, dict) and rel_data.get("id") is not None:
                event_id = str(rel_data.get("id"))
                break

        # Parse start time
        start_time: Optional[dt.datetime] = None
        for ts_key in ("start_time", "game_scheduled_at"):
            ts_str = attrs.get(ts_key)
            if ts_str:
                try:
                    start_time = dt.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    break
                except ValueError:
                    pass

        results.append({
            "player_name": player_name,
            "tour": tour,
            # Team code and roster position, kept because first-initial-plus-surname
            # is not a unique key for NFL players (three J.Williams and counting).
            "player_team": player_attrs.get("team") or None,
            "player_position": player_attrs.get("position") or None,
            "stat_type": stat_type,
            "line": float(line_score),
            "odds_type": attrs.get("odds_type") or None,
            "start_time": start_time,
            "event_id": event_id,
            "raw_json": item,
        })

    return results


# =============================================================================
# DB helpers
# =============================================================================

def link_date_utc(start_time: dt.datetime | str) -> dt.date:
    """The UTC calendar day of a prop's start, for matching `matches.match_date`.

    PrizePicks sends an ET offset ("2026-08-28T21:00:00.000-04:00"), so reading
    the day straight off that value yields the previous date for anything after
    20:00 ET, and the match lookup then lands on the wrong day. `match_date` is
    stored in UTC, so the offset has to be resolved before taking the date.
    """
    if isinstance(start_time, dt.datetime):
        if start_time.tzinfo is None:
            return start_time.date()
        return start_time.astimezone(dt.timezone.utc).date()
    return dt.date.fromisoformat(str(start_time)[:10])


async def _store_props(db, props: list[dict]) -> int:
    from sqlalchemy import text as _text
    from app.repositories.players import resolve_player
    from app.repositories.matches import find_match_for_player
    from app.repositories.props import upsert_prop

    # Clear existing PrizePicks props fetched today to prevent duplicates on re-run
    await db.execute(_text("""
        DELETE FROM props
        WHERE source = 'prizepicks'
          AND fetched_at >= CURRENT_DATE
    """))

    stored = 0
    for p in props:
        player_id = None
        if p["player_name"] and p["tour"]:
            player = await resolve_player(db, p["player_name"], p["tour"])
            if player:
                player_id = player.id
        elif p["player_name"]:
            # Try both tours
            for tour in ("ATP", "WTA"):
                player = await resolve_player(db, p["player_name"], tour)
                if player:
                    player_id = player.id
                    break

        # Link to match so we can look up surface
        match_id = None
        match_link_method = None
        if player_id and p.get("start_time"):
            match_date = link_date_utc(p["start_time"])
            match_id = await find_match_for_player(db, player_id, match_date, p["start_time"])
            match_link_method = "player_start_time" if match_id else None
        elif player_id:
            match_link_method = "player_date_fallback"

        await upsert_prop(
            db,
            player_id=player_id,
            match_id=match_id,
            source="prizepicks",
            stat_type=p["stat_type"],
            line=p["line"],
            odds_type=p["odds_type"],
            start_time=p["start_time"],
            raw_json={
                **(p["raw_json"] or {}),
                "player_name": p["player_name"],
                "tour": p["tour"],
                "prizepicks_event_id": p.get("event_id"),
                "match_link_method": match_link_method,
            },
        )
        stored += 1

    return stored


# =============================================================================
# Main
# =============================================================================

async def run(dry_run: bool = False) -> None:
    from app.db.pool import SessionLocal

    async with httpx.AsyncClient() as client:
        logger.info("Fetching PrizePicks leagues...")
        leagues = await _fetch_leagues(client)

        tennis_ids: list[int] = []
        for lg in leagues:
            attrs = lg.get("attributes") or {}
            name = (attrs.get("name") or "").lower()
            lg_id = int(lg.get("id", 0))
            if "tennis" in name:
                logger.info("  Tennis league: id=%d name=%s", lg_id, attrs.get("name"))
                tennis_ids.append(lg_id)

        if not tennis_ids:
            logger.info("No tennis leagues found on PrizePicks today.")
            return

        all_props: list[dict] = []
        for lg_id in tennis_ids:
            try:
                raw = await _fetch_projections(client, lg_id)
                props = _parse_projections(raw, lg_id)
                logger.info("  league %d: %d props", lg_id, len(props))
                all_props.extend(props)
            except httpx.HTTPStatusError as e:
                logger.error("  league %d: HTTP %d", lg_id, e.response.status_code)
            except Exception as e:
                logger.error("  league %d: %s", lg_id, e)
            await asyncio.sleep(0.5)

        logger.info("Total props: %d", len(all_props))

        # Print stat type breakdown
        by_stat: dict[str, int] = {}
        for p in all_props:
            by_stat[p["stat_type"]] = by_stat.get(p["stat_type"], 0) + 1
        for stat, count in sorted(by_stat.items()):
            logger.info("  %s: %d", stat, count)

        if dry_run:
            logger.info("DRY RUN — sample (first 10):")
            for p in all_props[:10]:
                logger.info("  %s [%s] | %s: %.1f | %s | %s",
                            p["player_name"], p["tour"] or "?", p["stat_type"],
                            p["line"], p["odds_type"] or "standard",
                            p["start_time"].isoformat() if p["start_time"] else "?")
            return

        if not all_props:
            return

        async with SessionLocal() as db:
            stored = await _store_props(db, all_props)
            await db.commit()
            logger.info("Stored %d props.", stored)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PrizePicks tennis props")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    await run(dry_run=args.dry_run)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
