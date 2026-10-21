"""
ingest/livetennis.py

Fetches tennis matches from livetennisapi.com and writes them to `players`,
`matches`, and `h2h`. Replaces the Playwright-based Sofascore scraper.

Because this is a plain HTTP API, there is no ProactorEventLoop/SelectorEventLoop
conflict and therefore no two-phase split — one async `run()` does fetch and write.

TIER GATING — the free tier is deliberately partial:
  free   : status=upcoming / live only. No completed results, no H2H. 100 calls/day.
  basic+ : adds status=completed (winner + score) and /h2h. 1,000 calls/day.
A 403 on a paid endpoint is logged as an upgrade hint and skipped, never fatal, so
the same command works on both tiers.

ENV VARS:
  LIVETENNIS_API_KEY  — required
  DATABASE_URL        — in api/app/.env

Run:
    python -m app.ingest.livetennis                          # today + tomorrow
    python -m app.ingest.livetennis --days-back 1
    python -m app.ingest.livetennis --dry-run                # no writes; name report
    python -m app.ingest.livetennis --date 2026-08-24 --no-h2h
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import difflib
import json
import logging
import sys
from typing import Any, Iterable, Optional, TypedDict

import httpx

from app.core.tennis_format import infer_best_of_or_none
from app.core.tennis_surface_overrides import apply_surface_override

from app.ingest.log_config import configure_ingest_logging

logger = logging.getLogger("livetennis_ingest")
configure_ingest_logging()

BASE_URL = "https://api.livetennisapi.com/api/public/v1"
PAGE_LIMIT = 200          # API maximum
MAX_PAGES = 25            # safety valve against a bad `has_more`
REQUEST_TIMEOUT = 30

# Provider tour vocabulary → our `tour` column. Anything absent is skipped,
# which is how juniors/itf stay out (matching the old KEEP_TOURS filter).
TOUR_MAP = {
    "atp": "ATP",
    "wta": "WTA",
    "challenger": "CHALLENGER",
}
DEFAULT_TOURS = ("atp", "wta", "challenger")

SURFACE_MAP = {"hard": "Hard", "clay": "Clay", "grass": "Grass"}

# Provider lifecycle → our `status` column.
STATUS_MAP = {
    "upcoming": "scheduled",
    "live": "live",
    "completed": "completed",
    "cancelled": "cancelled",
}

FORMAT_MAP = {"BO3": 3, "BO5": 5}

# Provider surface keys inside the H2H `by_surface` block → our `surface` values.
# 'unknown' is intentionally absent: it maps to the all-surface row instead.
H2H_SURFACE_MAP = {"hard": "Hard", "clay": "Clay", "grass": "Grass"}


class H2HResult(TypedDict):
    overall: tuple[int, int]
    by_surface: dict[str, tuple[int, int]]


# =============================================================================
# HTTP client
# =============================================================================

class TierBlocked(Exception):
    """Raised when the API returns 403 upgrade_required for the current plan."""


class FatalStatus(Exception):
    """A 4xx that will not change on retry (bad request, ambiguous name, auth)."""

    def __init__(self, status_code: int, path: str, body: str = "") -> None:
        super().__init__(f"{path}: HTTP {status_code}")
        self.status_code = status_code
        self.path = path
        self.body = body


def _log_tier_hint(status_code: int, path: str, body: str) -> None:
    """Classify an error the way odds_api.py does, so the fix is obvious from the log."""
    snippet = (body or "")[:200]
    if status_code == 400:
        # Usually `ambiguous_name` from /h2h — an expected, skippable outcome.
        logger.debug("%s: HTTP 400 — %s", path, snippet)
    elif status_code == 401:
        logger.error(
            "%s: HTTP 401 — LIVETENNIS_API_KEY missing, unknown, or disabled. %s", path, snippet
        )
    elif status_code == 403:
        logger.warning(
            "%s: HTTP 403 upgrade_required — this endpoint needs a paid plan "
            "(completed results and /h2h start at BASIC). Continuing without it. %s",
            path, snippet,
        )
    elif status_code == 429:
        logger.warning(
            "%s: HTTP 429 — rate limited (free = 30/min, 100/day). "
            "Check GET /usage, which is quota-exempt. %s", path, snippet
        )
    else:
        logger.error("%s: HTTP %d — %s", path, status_code, snippet)


async def _get(client: httpx.AsyncClient, path: str, params: Optional[dict] = None) -> Any:
    """GET with linear backoff on 429. Raises TierBlocked on 403."""
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            r = await client.get(f"{BASE_URL}{path}", params=params, timeout=REQUEST_TIMEOUT)

            if r.status_code == 429 and attempt < 3:
                # Prefer the server's own backoff hint when it sends one.
                retry_after = r.headers.get("Retry-After")
                wait_s = float(retry_after) if retry_after and retry_after.isdigit() else 2 * attempt
                logger.warning("%s: HTTP 429, retrying in %ss (attempt %d/3)", path, wait_s, attempt)
                await asyncio.sleep(wait_s)
                continue

            if r.status_code == 403:
                _log_tier_hint(403, path, r.text)
                raise TierBlocked(path)

            if r.status_code >= 400:
                _log_tier_hint(r.status_code, path, r.text)

            # A 4xx is a verdict, not a blip — retrying one only burns daily
            # quota. Retries are for 429 (handled above) and 5xx/network faults.
            if 400 <= r.status_code < 500:
                raise FatalStatus(r.status_code, path, r.text)

            r.raise_for_status()
            return r.json()
        except (TierBlocked, FatalStatus):
            raise
        except Exception as e:
            last_error = e
            if attempt < 3:
                await asyncio.sleep(2 * attempt)
                continue
            raise
    raise last_error or RuntimeError(f"Failed to GET {path}")


def _unwrap(payload: Any) -> list[dict]:
    """Pull the row list out of a {data, meta} envelope, tolerating a bare list."""
    if isinstance(payload, dict):
        data = payload.get("data")
        return data if isinstance(data, list) else []
    return payload if isinstance(payload, list) else []


def _has_more(payload: Any, received: int) -> bool:
    """`meta.has_more` is authoritative; fall back to a full page meaning more."""
    if isinstance(payload, dict):
        meta = payload.get("meta")
        if isinstance(meta, dict) and isinstance(meta.get("has_more"), bool):
            return meta["has_more"]
    return received >= PAGE_LIMIT


async def _get_paginated(client: httpx.AsyncClient, path: str, params: dict) -> list[dict]:
    """Page through a list endpoint until exhausted or MAX_PAGES."""
    rows: list[dict] = []
    offset = 0
    for _ in range(MAX_PAGES):
        payload = await _get(client, path, {**params, "limit": PAGE_LIMIT, "offset": offset})
        page = _unwrap(payload)
        rows.extend(page)
        if not page or not _has_more(payload, len(page)):
            break
        offset += len(page)
    else:
        logger.warning("%s: hit MAX_PAGES (%d) — results may be truncated", path, MAX_PAGES)
    return rows


# =============================================================================
# Field mapping
# =============================================================================

def _is_qualifying(raw: dict) -> bool:
    """The provider's own qualifying flag, which the round and tournament cannot supply."""
    return bool(raw.get("is_qualifying"))


def _map_tour(raw: Optional[str]) -> Optional[str]:
    """Match.tour uses the filter vocabulary. Player.tour does NOT — never use that one."""
    return TOUR_MAP.get((raw or "").strip().lower())


def _map_surface(raw: Optional[str]) -> Optional[str]:
    return SURFACE_MAP.get((raw or "").strip().lower())


def _map_status(raw: Optional[str], event_status: Optional[str] = None) -> str:
    """
    Map the lifecycle status, letting a cancellation override it.

    Observed live: a match can carry `status: upcoming` alongside
    `event_status: "Cancelled"` — the lifecycle gate that flips upcoming→cancelled
    runs late and deliberately, so the admin status is the earlier signal. Note
    also that event_status returns values outside its documented enum (e.g.
    "Finished"), so match on the ones we care about rather than validating.
    """
    status = STATUS_MAP.get((raw or "").strip().lower(), "scheduled")
    if status in ("scheduled", "live") and (event_status or "").strip().lower() == "cancelled":
        return "cancelled"
    return status


def _map_best_of(raw: Optional[str]) -> Optional[int]:
    return FORMAT_MAP.get((raw or "").strip().upper())


def _parse_dt(raw: Optional[str]) -> Optional[dt.datetime]:
    """Parse an ISO-8601 UTC timestamp, tolerating a trailing 'Z'."""
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _parse_date(raw: Optional[str]) -> Optional[dt.date]:
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def _format_score(score: Optional[dict]) -> Optional[str]:
    """
    Build "6-3 7-5" from Score.games, which is [games_p1, games_p2] — each entry
    a per-set list, NOT a per-set pair. Completed matches can carry empty games
    arrays, so an unusable shape yields None rather than a misleading string.
    """
    if not isinstance(score, dict):
        return None
    games = score.get("games")
    if not isinstance(games, list) or len(games) != 2:
        return None
    p1_sets, p2_sets = games[0], games[1]
    if not isinstance(p1_sets, list) or not isinstance(p2_sets, list):
        return None

    parts = []
    for p1_games, p2_games in zip(p1_sets, p2_sets):
        if not isinstance(p1_games, int) or not isinstance(p2_games, int):
            continue
        parts.append(f"{p1_games}-{p2_games}")
    return " ".join(parts) or None


def _is_stub_name(name: str) -> bool:
    """
    True for a not-yet-resolved name like "V. Kopriva" or "H. Seongchan".

    The feed publishes these before it has the full name. Inserting one creates a
    player row that the spelled-out name will NOT resolve to later, forking the
    person — so skip the match instead and pick it up on a later run. Known stubs
    for players we already hold are mapped in KNOWN_NAME_NORM_ALIASES and resolve
    normally before this ever applies.
    """
    first = name.split()[0] if name.split() else ""
    return len(first) == 2 and first.endswith(".")


def _player_tour(player: Any) -> Optional[str]:
    """
    ATP or WTA off an embedded Player, or None when it does not say.

    This is the one place Player.tour may be read, and only for the circuit's
    gender. Its vocabulary is NOT the filter vocabulary — live payloads carry
    plain 'atp'/'wta' here, but the field also emits 'challenger_men' and
    uppercase forms for doubles teams, so match on the prefix rather than the
    whole string, and never feed the result to _map_tour.
    """
    if not isinstance(player, dict):
        return None
    raw = (player.get("tour") or "").strip().lower()
    if raw.startswith("atp") or raw.endswith("_men"):
        return "ATP"
    if raw.startswith("wta") or raw.endswith("_women"):
        return "WTA"
    return None


_EMPTY_PLAYER_FIELDS = {
    "id": None, "name": None, "rank": None, "birth_date": None, "tour": None,
    "ranking_points": None, "ranking_movement": None, "hand": None, "country": None,
}


def _ranking_points(raw: Any) -> Optional[int]:
    """Points are 0-based, unlike rank, so 0 is a real value and only <0 is junk."""
    return raw if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0 else None


def _text_field(raw: Any, upper: bool = False) -> Optional[str]:
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    if not value:
        return None
    return value.upper() if upper else value.lower()


def _player_fields(player: Any) -> dict:
    """Pull the bits we store off an embedded Player object."""
    if not isinstance(player, dict):
        return dict(_EMPTY_PLAYER_FIELDS)
    ranking = player.get("ranking")
    return {
        "id": player.get("id"),
        "name": (player.get("name") or "").strip() or None,
        # Rankings are 1-based; treat 0/negative as "not ranked".
        "rank": ranking if isinstance(ranking, int) and ranking > 0 else None,
        "birth_date": _parse_date(player.get("birthday")),
        "tour": _player_tour(player),
        "ranking_points": _ranking_points(player.get("ranking_points")),
        "ranking_movement": _text_field(player.get("ranking_movement")),
        # The feed sends hand as 'R'/'L' and country as a lowercase ISO code;
        # normalize both so downstream comparisons don't have to case-fold.
        "hand": _text_field(player.get("hand"), upper=True),
        "country": _text_field(player.get("country"), upper=True),
    }


def normalize_match(raw: dict) -> Optional[dict]:
    """
    Convert one provider Match into our internal record dict, or None if it is
    not a match we ingest (unknown/unwanted tour, doubles, missing players).
    """
    tour = _map_tour(raw.get("tour"))
    if tour is None:
        return None

    # `draw` is the honest three-valued field; is_doubles conflates false/unknown.
    # Null draw covers team ties (Davis/BJK/United Cup), which we also exclude.
    if raw.get("draw") != "singles":
        return None

    players = raw.get("players") or {}
    p1 = _player_fields(players.get("p1"))
    p2 = _player_fields(players.get("p2"))
    if not p1["name"] or not p2["name"]:
        return None

    match_id = raw.get("id")
    if not isinstance(match_id, int):
        return None

    start_utc = _parse_dt(raw.get("scheduled_time"))
    match_date = start_utc.date() if start_utc else None
    if match_date is None:
        return None

    tournament_id = _text_field(raw.get("tournament_id"))
    surface, indoor = apply_surface_override(
        tournament_id,
        _map_surface(raw.get("surface")),
        raw.get("indoor") if isinstance(raw.get("indoor"), bool) else None,
    )

    return {
        "match_id": match_id,
        "day": match_date,
        "start_utc": start_utc,
        "tour": tour,
        "tournament": (raw.get("tournament") or "").strip() or None,
        "surface": surface,
        # round_code is the archive's controlled vocabulary (F/SF/QF/R32/...),
        # which is what feature_builder.ROUND_ORDINALS keys on. The free-text
        # `round` label is not.
        "round_": raw.get("round_code"),
        # The provider's `format` is authoritative when present; infer_best_of_or_none
        # only fills the gap (ATP slam main draw = BO5) and returns None rather than
        # guessing, so upsert_match's COALESCE keeps any correct stored value.
        #
        # `is_qualifying` has to be consulted, because a slam's qualifying draw carries
        # the tournament name of the slam itself and its own internal round codes: US Open
        # qualifying arrives as tournament "US Open" with rounds QF/SF/F, meaning the
        # qualifying quarter, semi and final. Without this flag those look like an ATP slam
        # main draw and get best-of-5, when qualifying is best-of-3 everywhere.
        "best_of": 3 if _is_qualifying(raw) else infer_best_of_or_none(
            tour,
            raw.get("tournament"),
            raw.get("round_code") or raw.get("round"),
            _map_best_of(raw.get("format")),
        ),
        "status": _map_status(raw.get("status"), raw.get("event_status")),
        "p1_name": p1["name"], "p2_name": p2["name"],
        "p1_lt_id": p1["id"], "p2_lt_id": p2["id"],
        "p1_rank": p1["rank"], "p2_rank": p2["rank"],
        "p1_birth_date": p1["birth_date"], "p2_birth_date": p2["birth_date"],
        "p1_ranking_points": p1["ranking_points"], "p2_ranking_points": p2["ranking_points"],
        "p1_ranking_movement": p1["ranking_movement"],
        "p2_ranking_movement": p2["ranking_movement"],
        "p1_hand": p1["hand"], "p2_hand": p2["hand"],
        "p1_country": p1["country"], "p2_country": p2["country"],
        # Court type is on the match, not the tournament: an event can move
        # matches indoors for weather without changing its own record.
        "indoor": indoor,
        "tournament_id": tournament_id,
        # Player-level circuit, used only when creating a player. A women's 125
        # draw arrives with tour=challenger, so without this the new player row
        # would be stored as CHALLENGER and lose the gender for good.
        "p1_tour": p1["tour"] or tour, "p2_tour": p2["tour"] or tour,
        "winner_code": raw.get("winner") if raw.get("winner") in (1, 2) else None,
        "score_str": _format_score(raw.get("score")),
    }


def parse_h2h(payload: Any) -> H2HResult | None:
    """
    Extract win totals plus the per-surface split from a /h2h response.

    Returns {"overall": (p1_wins, p2_wins), "by_surface": {"Hard": (w1, w2), ...}}
    or None when the pairing resolved to nothing.
    """
    if not isinstance(payload, dict) or not payload.get("players"):
        return None

    totals = payload.get("totals") or {}
    p1_wins = totals.get("p1_wins") or 0
    p2_wins = totals.get("p2_wins") or 0
    if not isinstance(p1_wins, int) or not isinstance(p2_wins, int):
        return None
    if p1_wins + p2_wins <= 0:
        return None

    by_surface: dict[str, tuple[int, int]] = {}
    raw_split = payload.get("by_surface")
    if isinstance(raw_split, dict):
        for key, split in raw_split.items():
            surface = H2H_SURFACE_MAP.get(str(key).strip().lower())
            if surface is None or not isinstance(split, dict):
                continue  # 'unknown' and anything unrecognised fold into overall only
            s1, s2 = split.get("p1") or 0, split.get("p2") or 0
            if isinstance(s1, int) and isinstance(s2, int) and s1 + s2 > 0:
                by_surface[surface] = (s1, s2)

    return {"overall": (p1_wins, p2_wins), "by_surface": by_surface}


def parse_history_h2h(
    rows: Iterable[dict[str, object]], p1_lt_id: int, p2_lt_id: int,
) -> H2HResult | None:
    """Aggregate completed singles history for one exact provider-ID pair."""
    if p1_lt_id == p2_lt_id:
        return None

    wins = [0, 0]
    surface_wins: dict[str, list[int]] = {}

    for row in rows:
        if row.get("status") != "completed" or row.get("draw") != "singles":
            continue

        players = row.get("players")
        if not isinstance(players, dict):
            continue
        raw_p1 = players.get("p1")
        raw_p2 = players.get("p2")
        if not isinstance(raw_p1, dict) or not isinstance(raw_p2, dict):
            continue

        provider_ids = (raw_p1.get("id"), raw_p2.get("id"))
        if any(type(player_id) is not int for player_id in provider_ids):
            continue
        if set(provider_ids) != {p1_lt_id, p2_lt_id}:
            continue

        winner = row.get("winner")
        if type(winner) is not int or winner not in (1, 2):
            continue
        winner_id = provider_ids[winner - 1]
        requested_side = 0 if winner_id == p1_lt_id else 1
        wins[requested_side] += 1

        raw_surface = row.get("surface")
        surface = _map_surface(raw_surface if isinstance(raw_surface, str) else None)
        if surface is not None:
            counts = surface_wins.setdefault(surface, [0, 0])
            counts[requested_side] += 1

    if sum(wins) == 0:
        return None

    return {
        "overall": (wins[0], wins[1]),
        "by_surface": {
            surface: (counts[0], counts[1])
            for surface, counts in surface_wins.items()
        },
    }


# =============================================================================
# Fetching
# =============================================================================

async def fetch_matches(
    client: httpx.AsyncClient,
    date_from: dt.date,
    date_to: dt.date,
    tours: Iterable[str],
    statuses: Iterable[str],
) -> list[dict]:
    """Fetch and normalize matches for a date window, one query per tour × status."""
    records: dict[int, dict] = {}
    for status in statuses:
        for tour in tours:
            params = {
                "status": status,
                "tour": tour,
                "draw": "singles",
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
            }
            try:
                rows = await _get_paginated(client, "/matches", params)
            except TierBlocked:
                logger.warning(
                    "  status=%s is not available on this plan — skipping (needs BASIC)", status
                )
                break  # same for every tour; don't burn calls re-proving it
            except Exception as e:
                logger.error("  %s/%s fetch failed: %s", status, tour, e)
                continue

            kept = 0
            for raw in rows:
                rec = normalize_match(raw)
                if rec is None:
                    continue
                # A match can surface under more than one status query as it
                # progresses; last write wins, and statuses are ordered so the
                # most settled one lands last.
                records[rec["match_id"]] = rec
                kept += 1
            logger.info("  %s/%s: %d fetched, %d kept", status, tour, len(rows), kept)

    return list(records.values())


def _provider_error_code(body: str) -> str | None:
    try:
        payload: object = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    return error if isinstance(error, str) else None


async def fetch_h2h(
    client: httpx.AsyncClient,
    p1_name: str,
    p2_name: str,
    p1_lt_id: int | None = None,
    p2_lt_id: int | None = None,
) -> H2HResult | None:
    """
    Fetch H2H by provider spelling, falling back to exact IDs when names collide.
    """
    if len(p1_name) < 3 or len(p2_name) < 3:
        return None
    try:
        payload = await _get(client, "/h2h", {"p1": p1_name, "p2": p2_name})
    except TierBlocked:
        raise
    except FatalStatus as e:
        if e.status_code != 400:
            raise
        if _provider_error_code(e.body) != "ambiguous_name":
            logger.debug("  h2h unresolvable: %s vs %s", p1_name, p2_name)
            return None
        if (
            type(p1_lt_id) is not int
            or type(p2_lt_id) is not int
            or p1_lt_id == p2_lt_id
        ):
            logger.debug(
                "  h2h ambiguous and provider IDs unavailable: %s vs %s",
                p1_name,
                p2_name,
            )
            return None

        rows = await _get_paginated(
            client,
            "/history/matches",
            {"player": p1_lt_id, "draw": "singles", "from": "2023-01-01"},
        )
        return parse_history_h2h(rows, p1_lt_id, p2_lt_id)
    return parse_h2h(payload)


async def fetch_usage(client: httpx.AsyncClient) -> Optional[dict]:
    """GET /usage is quota-exempt, so this is free to call for budget logging."""
    try:
        return await _get(client, "/usage")
    except Exception as e:
        logger.debug("Could not read /usage: %s", e)
        return None


# =============================================================================
# DB write
# =============================================================================

async def _resolve_any_tour(db, name: str):
    """
    Look a player up by normalized name, ignoring tour.

    `resolve_player` scopes its primary lookup to `tour`, which is a false-negative
    generator here: this provider files women's 125/ITF events under `challenger`
    where our rows say `WTA`, so a tour-scoped miss would fork the player. Because
    `idx_players_name_norm` is UNIQUE on name_norm ALONE, there is at most one row
    per name anyway — dropping the tour predicate cannot introduce ambiguity.
    """
    from sqlalchemy import text

    from app.repositories.players import Player, normalize_name

    row = await db.execute(
        text("""
            SELECT id, name, name_norm, tour, sofascore_id, ta_id, birth_date, ta_slug,
                   livetennis_id
            FROM players WHERE name_norm = :n
        """),
        {"n": normalize_name(name)},
    )
    r = row.fetchone()
    return Player(*r) if r else None


async def _resolve_or_create(
    db, name: str, tour: str, lt_id: Optional[int], birth_date: Optional[dt.date],
    unmatched: list, stubs: set, dry_run: bool,
    hand: Optional[str] = None, country: Optional[str] = None,
) -> Optional[int]:
    """
    Alias-first player resolution.

    `players.name_norm` carries a UNIQUE index and upsert_player conflicts on it,
    so calling upsert_player with a spelling that differs from the stored one
    silently creates a DUPLICATE player — splitting that person's ELO and rolling
    stats. Resolve first; only insert when the player is genuinely new.
    """
    from app.repositories.players import resolve_player, upsert_alias, upsert_player

    # Canonical name + tour, then aliases, then name alone across tours.
    existing = await resolve_player(db, name, tour) or await _resolve_any_tour(db, name)
    if existing:
        if dry_run:
            return existing.id
        if existing.name != name:
            # Record the provider's spelling so the next run resolves on the first hop.
            await upsert_alias(db, existing.id, name, "livetennis")
        # Backfill provider id, DOB, and profile fields without disturbing the
        # canonical name. upsert_player COALESCEs, so a None never clobbers.
        await upsert_player(
            db, existing.name, existing.tour,
            livetennis_id=lt_id,
            birth_date=birth_date if existing.birth_date is None else None,
            hand=hand,
            country=country,
        )
        return existing.id

    # Checked only after resolution fails: a stub we already have a mapping for
    # (e.g. "V. Kopriva") resolves above and never reaches here.
    if _is_stub_name(name):
        stubs.add(name)
        return None

    unmatched.append((name, tour))
    if dry_run:
        return None
    return await upsert_player(
        db, name, tour, livetennis_id=lt_id, birth_date=birth_date,
        hand=hand, country=country,
    )


async def write_to_db(
    db, records: list[dict], client: Optional[httpx.AsyncClient],
    ingest_h2h: bool, dry_run: bool,
) -> dict:
    """Upsert players and matches, and optionally refresh H2H. Returns a summary."""
    from app.repositories.matches import upsert_h2h, upsert_match

    unmatched: list[tuple[str, str]] = []
    stubs: set[str] = set()
    written = 0
    h2h_written = 0
    h2h_seen: set[tuple[int, int]] = set()
    h2h_blocked = False

    for rec in records:
        tour = rec["tour"]
        # Player rows take the player-level circuit, not the match's — see
        # normalize_match. The match itself still stores `tour`.
        p1_id = await _resolve_or_create(
            db, rec["p1_name"], rec["p1_tour"], rec["p1_lt_id"], rec["p1_birth_date"],
            unmatched, stubs, dry_run, rec["p1_hand"], rec["p1_country"],
        )
        p2_id = await _resolve_or_create(
            db, rec["p2_name"], rec["p2_tour"], rec["p2_lt_id"], rec["p2_birth_date"],
            unmatched, stubs, dry_run, rec["p2_hand"], rec["p2_country"],
        )
        if p1_id is None or p2_id is None:
            continue  # dry-run, an unresolved stub name, or an unresolvable player

        winner_id = None
        if rec["winner_code"] == 1:
            winner_id = p1_id
        elif rec["winner_code"] == 2:
            winner_id = p2_id

        if not dry_run:
            await upsert_match(
                db,
                match_key=f"livetennis:{rec['match_id']}",
                match_date=rec["day"],
                tour=tour,
                p1_id=p1_id,
                p2_id=p2_id,
                surface=rec["surface"],
                tournament=rec["tournament"],
                round_=rec["round_"],
                best_of=rec["best_of"],
                p1_rank=rec["p1_rank"],
                p2_rank=rec["p2_rank"],
                status=rec["status"],
                start_utc=rec["start_utc"],
                winner_id=winner_id,
                score=rec["score_str"],
                livetennis_id=rec["match_id"],
                indoor=rec["indoor"],
                tournament_id=rec["tournament_id"],
                p1_ranking_points=rec["p1_ranking_points"],
                p2_ranking_points=rec["p2_ranking_points"],
                p1_ranking_movement=rec["p1_ranking_movement"],
                p2_ranking_movement=rec["p2_ranking_movement"],
            )
        written += 1

        if not ingest_h2h or h2h_blocked or client is None or dry_run:
            continue

        pair = (min(p1_id, p2_id), max(p1_id, p2_id))
        if pair in h2h_seen:
            continue  # same pairing can appear twice in a window; one call is enough
        h2h_seen.add(pair)

        try:
            h2h = await fetch_h2h(
                client,
                rec["p1_name"],
                rec["p2_name"],
                rec["p1_lt_id"],
                rec["p2_lt_id"],
            )
        except TierBlocked:
            logger.warning("H2H needs BASIC — skipping H2H for the rest of this run")
            h2h_blocked = True
            continue
        except Exception as e:
            logger.debug("  h2h failed for %s vs %s: %s", rec["p1_name"], rec["p2_name"], e)
            continue

        if not h2h:
            continue

        overall_p1, overall_p2 = h2h["overall"]
        await upsert_h2h(db, p1_id, p2_id, overall_p1, overall_p2)
        # Unlike the old Sofascore path — which wrote the OVERALL totals under a
        # surface label, mislabelling every surface row — these are the provider's
        # real per-surface splits.
        for surface, (s1, s2) in h2h["by_surface"].items():
            await upsert_h2h(db, p1_id, p2_id, s1, s2, surface=surface)
        h2h_written += 1

    if not dry_run:
        await db.commit()

    if stubs:
        logger.info(
            "Skipped %d match(es) whose player name is still an unresolved stub: %s",
            len(stubs), ", ".join(sorted(stubs)),
        )

    return {"written": written, "h2h": h2h_written, "unmatched": unmatched, "stubs": stubs}


def _report_unmatched(unmatched: list[tuple[str, str]], known_names: list[str]) -> None:
    """Print new-player names beside their closest existing name, for eyeballing."""
    if not unmatched:
        logger.info("Name check: every player resolved to an existing row.")
        return

    logger.info("")
    logger.info("=" * 70)
    logger.info("UNMATCHED PLAYERS (%d) — would be INSERTED as new rows", len(unmatched))
    logger.info("A close match below usually means a spelling variant, not a new player.")
    logger.info("Fix by adding to KNOWN_NAME_NORM_ALIASES in app/repositories/players.py")
    logger.info("or seeding a player_aliases row.")
    logger.info("=" * 70)
    for name, tour in sorted(set(unmatched)):
        close = difflib.get_close_matches(name, known_names, n=1, cutoff=0.75)
        hint = f"  ~ closest existing: {close[0]!r}" if close else ""
        logger.info("  [%s] %s%s", tour, name, hint)
    logger.info("=" * 70)


# =============================================================================
# Entry point
# =============================================================================

def _windows(date_from: dt.date, date_to: dt.date, chunk_days: int) -> list[tuple[dt.date, dt.date]]:
    """Split a date range into inclusive slices of at most chunk_days.

    One /matches query paginates to MAX_PAGES * PAGE_LIMIT rows, so a wide backfill
    window silently loses everything past that ceiling. The archive runs roughly 550
    matches per tour per month, so month-sized slices stay an order of magnitude clear
    of it. chunk_days <= 0 keeps the whole range as a single window.
    """
    if chunk_days <= 0 or date_from >= date_to:
        return [(date_from, date_to)]
    out: list[tuple[dt.date, dt.date]] = []
    start = date_from
    while start <= date_to:
        end = min(start + dt.timedelta(days=chunk_days - 1), date_to)
        out.append((start, end))
        start = end + dt.timedelta(days=1)
    return out


async def run(
    days_back: int = 0,
    days_ahead: int = 1,
    specific_date: Optional[dt.date] = None,
    tours: Optional[list[str]] = None,
    ingest_h2h: bool = True,
    dry_run: bool = False,
    date_from_arg: Optional[dt.date] = None,
    date_to_arg: Optional[dt.date] = None,
    chunk_days: int = 0,
) -> None:
    from sqlalchemy import text

    from app.config import settings
    from app.db.pool import SessionLocal
    from app.db.retry import run_in_session_with_retry

    api_key = (settings.livetennis_api_key or "").strip()
    if not api_key:
        import os
        api_key = os.getenv("LIVETENNIS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "LIVETENNIS_API_KEY is required — set it in api/app/.env or the environment"
        )

    if date_from_arg or date_to_arg:
        date_from = date_from_arg or date_to_arg
        date_to = date_to_arg or date_from_arg
    elif specific_date:
        date_from = date_to = specific_date
    else:
        today = dt.date.today()
        date_from = today - dt.timedelta(days=days_back)
        date_to = today + dt.timedelta(days=days_ahead)

    tours = tours or list(DEFAULT_TOURS)

    # Order matters: `completed` runs last so a settled result overwrites the
    # earlier upcoming/live view of the same match.
    statuses = ["upcoming", "live", "completed"]
    if date_to < dt.date.today():
        # A pure backfill window has nothing upcoming or live in it.
        statuses = ["completed"]
    elif days_back == 0 and not specific_date and not date_from_arg:
        # Nothing in a forward-only window can be completed; don't spend the call.
        statuses = ["upcoming", "live"]

    logger.info(
        "livetennisapi ingest: %s to %s | tours=%s | h2h=%s%s",
        date_from, date_to, ",".join(tours), ingest_h2h, " | DRY RUN" if dry_run else "",
    )

    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    async with httpx.AsyncClient(headers=headers) as client:
        usage = await fetch_usage(client)
        if usage:
            tier = usage.get("tier")
            today_calls = (usage.get("today") or {}).get("calls")
            remaining = (usage.get("today") or {}).get("remaining_day")
            logger.info("Plan: tier=%s | calls today=%s | remaining=%s", tier, today_calls, remaining)
            if tier == "free" and ingest_h2h:
                logger.warning(
                    "Free tier: completed results and H2H are unavailable and will be skipped. "
                    "winner_id, score, and the h2h table will not be updated."
                )

        windows = _windows(date_from, date_to, chunk_days)
        if len(windows) > 1:
            logger.info("Splitting into %d windows of up to %d days", len(windows), chunk_days)

        totals = {"records": 0, "written": 0, "h2h": 0}
        all_unmatched: list[str] = []
        for i, (win_from, win_to) in enumerate(windows, 1):
            if len(windows) > 1:
                logger.info("── window %d/%d: %s to %s", i, len(windows), win_from, win_to)

            records = await fetch_matches(client, win_from, win_to, tours, statuses)
            logger.info("Normalized %d singles matches", len(records))
            if not records:
                logger.warning("No matches returned for this window.")
                continue
            totals["records"] += len(records)

            known_names: list[str] = []

            async def _write(db):
                # Rebound each attempt: a retry gets a fresh session, and the previous
                # attempt's reads are gone with the aborted transaction.
                nonlocal known_names
                if dry_run:
                    rows = await db.execute(text("SELECT name FROM players"))
                    known_names = [r[0] for r in rows.fetchall()]
                return await write_to_db(db, records, client, ingest_h2h, dry_run)

            summary = await run_in_session_with_retry(
                _write, description=f"window {win_from}..{win_to}"
            )

            totals["written"] += summary["written"]
            totals["h2h"] += summary["h2h"]
            all_unmatched.extend(summary["unmatched"])

            if dry_run:
                _report_unmatched(summary["unmatched"], known_names)

        if not totals["records"]:
            logger.warning("No matches returned — nothing to write.")
            return

        if dry_run:
            logger.info("DRY RUN — no rows written. %d matches would be upserted.", totals["records"])
        else:
            logger.info(
                "Done. %d matches upserted, %d H2H pairings written, %d new players.",
                totals["written"], totals["h2h"], len(set(all_unmatched)),
            )

        usage = await fetch_usage(client)
        if usage:
            today = usage.get("today") or {}
            logger.info(
                "Usage after run: %s calls today, %s remaining",
                today.get("calls"), today.get("remaining_day"),
            )


async def _main() -> None:
    parser = argparse.ArgumentParser(description="livetennisapi.com tennis match ingest")
    parser.add_argument("--date", type=str, help="Specific date YYYY-MM-DD")
    parser.add_argument("--days-back", type=int, default=0)
    parser.add_argument("--days-ahead", type=int, default=1)
    parser.add_argument("--from", dest="date_from", type=str,
                        help="Backfill window start YYYY-MM-DD (use with --to)")
    parser.add_argument("--to", dest="date_to", type=str,
                        help="Backfill window end YYYY-MM-DD (use with --from)")
    parser.add_argument("--chunk-days", type=int, default=0,
                        help="Split the window into slices of this many days. Required for "
                             "wide backfills: one query caps out at 5,000 rows. 30 is a safe value.")
    parser.add_argument("--no-h2h", action="store_true", help="Skip H2H fetching")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch and resolve but write nothing; report players that would be created",
    )
    parser.add_argument(
        "--tour", type=str, default=",".join(DEFAULT_TOURS),
        help=f"Comma-separated tours to ingest (default: {','.join(DEFAULT_TOURS)})",
    )
    args = parser.parse_args()

    tours = [t.strip().lower() for t in args.tour.split(",") if t.strip()]
    unknown = [t for t in tours if t not in TOUR_MAP]
    if unknown:
        parser.error(f"Unsupported tour(s): {', '.join(unknown)}. Choose from {', '.join(TOUR_MAP)}.")

    await run(
        days_back=args.days_back,
        days_ahead=args.days_ahead,
        specific_date=dt.date.fromisoformat(args.date) if args.date else None,
        tours=tours,
        ingest_h2h=not args.no_h2h,
        dry_run=args.dry_run,
        date_from_arg=dt.date.fromisoformat(args.date_from) if args.date_from else None,
        date_to_arg=dt.date.fromisoformat(args.date_to) if args.date_to else None,
        chunk_days=args.chunk_days,
    )


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
