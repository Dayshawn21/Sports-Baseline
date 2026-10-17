"""
ingest/player_stats.py

Fetches serve + return stats for players from TennisAbstract player pages
and stores them in `player_rolling_stats` (stat_period = "last_52w").

TennisAbstract exposes per-match raw counts in the player-classic pages:
  ATP: https://www.tennisabstract.com/cgi-bin/player-classic.cgi?p={PlayerName}
  WTA: https://www.tennisabstract.com/cgi-bin/wplayer-classic.cgi?p={PlayerName}

No Playwright needed — plain requests.

Column indices from matchhead array:
  0=date(YYYYMMDD), 4=wl, 21=aces, 22=dfs, 23=pts,
  24=firsts, 25=fwon, 26=swon, 27=games, 28=saved, 29=chances,
  30=oaces, 31=odfs, 32=opts, 33=ofirsts, 34=ofwon, 35=oswon,
  36=ogames, 37=osaved, 38=ochances

Aggregation formulas (verified against Sabalenka last-52w):
  svc_pts_won  = (sum_fwon + sum_swon) / sum_pts
  ret_pts_won  = 1 - (sum_ofwon + sum_oswon) / sum_opts
  aces_per_game = sum_aces / sum_pts   (ace% — aces per serve point, same as TennisAbstract)
  df_per_game   = sum_dfs / sum_pts    (df%  — DFs per serve point, same as TennisAbstract)
  hold_pct      = (sum_games - (sum_chances - sum_saved)) / sum_games
  break_pct     = (sum_ochances - sum_osaved) / sum_ochances
  win_rate      = wins / (wins + losses)

Run:
    python -m app.ingest.player_stats           # all players
    python -m app.ingest.player_stats --tour ATP
    python -m app.ingest.player_stats --limit 50
    python -m app.ingest.player_stats --sleep 0.1
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import re
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta
from typing import Optional

import requests

from app.ingest.log_config import configure_ingest_logging

logger = logging.getLogger("player_stats_ingest")

TA_JS_BASE = "https://www.tennisabstract.com/jsmatches"
TA_ATP_PAGE = "https://www.tennisabstract.com/cgi-bin/player-classic.cgi"
TA_WTA_PAGE = "https://www.tennisabstract.com/cgi-bin/wplayer-classic.cgi"
STAT_PERIOD = "last_52w"
WINDOW_DAYS = 365
MIN_MATCHES = 3
RECENCY_WINDOWS: dict[str, int] = {
    "last_52w": 365,
    "last90d": 90,
    "last180d": 180,
}
OPP_RANK_BUCKETS: tuple[str, ...] = ("top5", "top10", "top20", "top50", "plus51")

# Column indices in each match row (from matchhead)
I_DATE = 0     # tournament start, shared by every round of the event
I_TOURNAMENT = 1
I_SURFACE = 2   # 'Hard', 'Clay', 'Grass' (index 3 is indoor/outdoor flag)
I_WL = 4
I_ROUND = 8
I_SCORE = 9     # winner first, tie-break points in parentheses
I_OPPONENT = 11
I_ACES = 21
I_DFS = 22
I_PTS = 23
I_FIRSTS = 24
I_FWON = 25
I_SWON = 26
I_GAMES = 27
I_SAVED = 28
I_CHANCES = 29
# Opponent
I_ORANK = 12
I_OACES = 30
I_ODFS = 31
I_OPTS = 32
I_OFIRSTS = 33
I_OFWON = 34
I_OSWON = 35
I_OGAMES = 36
I_OSAVED = 37
I_OCHANCES = 38


# Sofascore name → TennisAbstract slug overrides (add new mismatches here)
TA_SLUG_OVERRIDES: dict[str, str] = {
    "Catherine McNally": "CatyMcnally",
    "Guiomar Maristany": "GuiomarMaristanyZuletaDeReales",
    # Hyphenated names — _slug() only strips spaces, not hyphens
    "Felix Auger-Aliassime": "FelixAugerAliassime",
    "Elena-Gabriela Ruse": "ElenaGabrielaRuse",
    # Sofascore first-name abbreviations / alternate spellings
    "Alex De Minaur": "AlexDeMinaur",
    "Jo-Wilfried Tsonga": "JoWilfriedTsonga",
}


def _slug(name: str) -> str:
    """'Aryna Sabalenka' -> 'ArynaSabalenka', with known override support."""
    if name in TA_SLUG_OVERRIDES:
        return TA_SLUG_OVERRIDES[name]
    return name.replace(" ", "")


_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
})



# A page whose newest match predates this is treated as a stale mirror and we
# try the next source. /jsmatches/ stopped updating for men years ago (it serves
# ~2018 data), which silently produced "fewer than 3 matches in last 52 weeks".
STALE_AFTER_DAYS = 400


def _identity_ok(page_text: str, slug: str) -> bool:
    """
    Confirm the page we got back is actually the player we asked for.

    player-classic.cgi does NOT 404 on a name it cannot find — it serves a
    different player's career (observed: `?p=LoisBoisson` returns Benoit Paire's
    1076 matches). Without this check, falling back to the ATP page for a woman
    would write someone else's stats into her row.

    Compared against the slug rather than our DB name, so a TA_SLUG_OVERRIDES
    spelling still validates. Prefix matching tolerates Jr/Sr suffixes.
    """
    m = re.search(r"var\s+fullname\s*=\s*'([^']*)'", page_text)
    if not m:
        return True  # no marker to check against; the caller's other guards apply

    def squash(s: str) -> str:
        norm = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z]", "", norm.lower())

    got, want = squash(m.group(1)), squash(slug)
    if not got or not want:
        return True
    return got == want or got.startswith(want) or want.startswith(got)


def _newest_date(rows: list) -> str:
    return max((str(r[I_DATE]) for r in rows if r and len(r) > I_DATE), default="")


def _fetch_one(url: str, name: str, slug: str) -> Optional[list]:
    """Fetch one source. Returns parsed rows, or None if unusable."""
    for attempt in range(3):
        try:
            resp = _session.get(url, timeout=30)
        except requests.RequestException as e:
            logger.warning("Request failed for %s: %s", name, e)
            return None
        if resp.status_code == 404:
            logger.debug("Not found: %s", url)
            return None
        if resp.status_code == 429:
            wait = 10 * (attempt + 1)
            logger.warning("Rate limited for %s — waiting %ds (attempt %d/3)", name, wait, attempt + 1)
            time.sleep(wait)
            continue
        if resp.status_code != 200:
            logger.warning("HTTP %d for %s", resp.status_code, url)
            return None
        break
    else:
        logger.warning("Gave up on %s after 3 rate-limit retries", name)
        return None

    if not _identity_ok(resp.text, slug):
        logger.debug("Identity mismatch for %s at %s — wrong player served", name, url)
        return None

    m = re.search(r"matchmx\s*=\s*(\[[\s\S]*?\]\s*\])\s*;", resp.text)
    if not m:
        logger.debug("No matches array for %s at %s", name, url)
        return None

    try:
        rows = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        logger.warning("JSON parse failed for %s: %s", name, e)
        return None
    return rows or None


def _fetch_matches(name: str, tour: str = "", slug_override: Optional[str] = None) -> Optional[list]:
    """
    Fetch and parse a TennisAbstract player page. Returns list of rows or None.

    Neither source covers everyone:
      - the classic HTML page is current for men but serves the WRONG player for
        women (see _identity_ok)
      - /jsmatches/ is current for women but frozen around 2018 for men

    `tour` only orders the attempts, it does not decide. That matters because
    livetennisapi files women's 125/ITF events under `challenger` alongside the
    men's Challenger tour, so the label cannot tell us which page to use.
    """
    slug = slug_override if slug_override else _slug(name)
    classic = f"{TA_ATP_PAGE}?p={slug}"
    jsmatches = f"{TA_JS_BASE}/{slug}.js"

    # Most likely source first, so the common case still costs one request.
    candidates = [jsmatches, classic] if tour.upper() == "WTA" else [classic, jsmatches]

    fresh_cutoff = (date.today() - timedelta(days=STALE_AFTER_DAYS)).strftime("%Y%m%d")
    best: Optional[list] = None
    best_date = ""

    for url in candidates:
        rows = _fetch_one(url, name, slug)
        if not rows:
            continue
        newest = _newest_date(rows)
        if newest > best_date:
            best, best_date = rows, newest
        if newest >= fresh_cutoff:
            return best  # current data — no need to pay for the other source

    if best is not None and best_date < fresh_cutoff:
        logger.warning(
            "%s: every TennisAbstract source is stale (newest match %s) — stats will be thin",
            name, best_date or "none",
        )
    return best


def _norm_surface(row: list) -> Optional[str]:
    """Return normalized surface name from a match row, or None if unrecognized."""
    s = row[I_SURFACE] if len(row) > I_SURFACE else ""
    if s == "Hard":
        return "Hard"
    if s == "Clay":
        return "Clay"
    if s == "Grass":
        return "Grass"
    return None


def _safe(row: list, idx: int) -> float:
    """Return row[idx] as float, or 0.0 on any error."""
    try:
        v = row[idx]
        return float(v) if v not in (None, "", "NA") else 0.0
    except (IndexError, TypeError, ValueError):
        return 0.0


def _optional_int(row: list, idx: int) -> Optional[int]:
    """Return an exact count from a raw row, retaining missing data as None."""
    try:
        value = row[idx]
        if value in (None, "", "NA"):
            return None
        return int(float(value))
    except (IndexError, TypeError, ValueError):
        return None


def box_score_key(
    tournament_start: str,
    tournament: Optional[str],
    round_name: Optional[str],
    opponent: Optional[str],
    raw_row: list,
) -> str:
    """The row key a box score is upserted on.

    TennisAbstract edits a row as a match goes from scheduled to scored to full stats,
    so a hash of the raw row stored each stage as a new row. The match itself (event,
    round, opponent) stays put. Round robins make the opponent necessary. Rows missing
    a part, pre-26e only, keep the raw-row hash. Migration 0038 builds the same v2 key
    in SQL, so this formula must not change without a new migration.
    """
    parts = [(part or "").strip().lower() for part in (tournament, round_name, opponent)]
    if all(parts):
        return hashlib.sha256("|".join(["v2", tournament_start, *parts]).encode("utf-8")).hexdigest()
    source_row = json.dumps(raw_row, ensure_ascii=True, separators=(",", ":"), default=str)
    return hashlib.sha256(source_row.encode("utf-8")).hexdigest()


def _parse_player_match_stats(player_id: int, raw_rows: list, cutoff: str) -> list:
    """Convert TennisAbstract raw rows into exact, player-oriented box scores."""
    from app.repositories.player_match_stats import PlayerMatchStat

    stats: list[PlayerMatchStat] = []
    for row in raw_rows:
        if not row or len(row) <= I_OCHANCES:
            continue
        raw_date = str(row[I_DATE])
        if raw_date < cutoff:
            continue
        try:
            match_date = datetime.strptime(raw_date, "%Y%m%d").date()
        except ValueError:
            continue

        chances_created = _optional_int(row, I_OCHANCES)
        opponent_saved = _optional_int(row, I_OSAVED)
        converted = None
        if chances_created is not None and opponent_saved is not None:
            converted = max(chances_created - opponent_saved, 0)

        result = str(row[I_WL]) if row[I_WL] in ("W", "L") else None
        tournament = _optional_text(row, I_TOURNAMENT)
        round_name = _optional_text(row, I_ROUND)
        opponent = _optional_text(row, I_OPPONENT)
        stats.append(
            PlayerMatchStat(
                player_id=player_id,
                source_match_key=box_score_key(raw_date, tournament, round_name, opponent, row),
                match_date=match_date,
                surface=_norm_surface(row),
                result=result,
                aces=_optional_int(row, I_ACES),
                double_faults=_optional_int(row, I_DFS),
                service_games=_optional_int(row, I_GAMES),
                break_points_faced=_optional_int(row, I_CHANCES),
                break_points_saved=_optional_int(row, I_SAVED),
                break_chances_created=chances_created,
                break_points_converted=converted,
                opponent_name=opponent,
                round=round_name,
                tournament=tournament,
                score=_optional_text(row, I_SCORE),
            )
        )
    return stats


def _optional_text(row: list, index: int) -> Optional[str]:
    value = row[index] if len(row) > index else None
    text_value = str(value).strip() if value is not None else ""
    return text_value or None


def _opp_rank(row: list) -> Optional[int]:
    try:
        raw = row[I_ORANK]
        if raw in (None, "", "NA"):
            return None
        rank = int(raw)
        return rank if rank > 0 else None
    except (IndexError, TypeError, ValueError):
        return None


def _opp_rank_bucket_matches(row: list, bucket: str) -> bool:
    rank = _opp_rank(row)
    if rank is None:
        return False
    if bucket == "top5":
        return rank <= 5
    if bucket == "top10":
        return rank <= 10
    if bucket == "top20":
        return rank <= 20
    if bucket == "top50":
        return rank <= 50
    if bucket == "plus51":
        return rank >= 51
    return False


def _aggregate(
    rows: list,
    cutoff: str,
    surface: Optional[str] = None,
    opp_rank_bucket: Optional[str] = None,
) -> Optional[dict]:
    """
    Filter rows to a cutoff and aggregate stats.
    If surface is given, only include rows matching that surface.
    If opp_rank_bucket is given, only include rows matching that opponent-rank bucket.
    Returns dict of stats or None if insufficient data.
    """
    wins = losses = 0
    pts = fwon = swon = firsts = 0.0
    aces = dfs = games = saved = chances = 0.0
    oaces = odfs = opts = ofirsts = ofwon = oswon = 0.0
    ogames = osaved = ochances = 0.0

    for row in rows:
        if not row or len(row) < I_OCHANCES + 1:
            continue
        dt = str(row[I_DATE])
        if dt < cutoff:
            continue
        if surface is not None and _norm_surface(row) != surface:
            continue
        if opp_rank_bucket is not None and not _opp_rank_bucket_matches(row, opp_rank_bucket):
            continue

        wl = row[I_WL]
        if wl == "W":
            wins += 1
        elif wl == "L":
            losses += 1

        pts += _safe(row, I_PTS)
        firsts += _safe(row, I_FIRSTS)
        fwon += _safe(row, I_FWON)
        swon += _safe(row, I_SWON)
        aces += _safe(row, I_ACES)
        dfs += _safe(row, I_DFS)
        games += _safe(row, I_GAMES)
        saved += _safe(row, I_SAVED)
        chances += _safe(row, I_CHANCES)
        oaces += _safe(row, I_OACES)
        odfs += _safe(row, I_ODFS)
        opts += _safe(row, I_OPTS)
        ofirsts += _safe(row, I_OFIRSTS)
        ofwon += _safe(row, I_OFWON)
        oswon += _safe(row, I_OSWON)
        ogames += _safe(row, I_OGAMES)
        osaved += _safe(row, I_OSAVED)
        ochances += _safe(row, I_OCHANCES)

    matches_count = wins + losses
    if matches_count < MIN_MATCHES:
        return None

    def _pct(num, den):
        return round(num / den, 4) if den > 0 else None

    svc_pts_won = _pct(fwon + swon, pts)
    ret_pts_won = _pct(opts - ofwon - oswon, opts)

    # DR = SPW% / (1 - RPW%)
    dominance_ratio = None
    if svc_pts_won is not None and ret_pts_won is not None and (1 - ret_pts_won) > 0:
        dominance_ratio = round(svc_pts_won / (1 - ret_pts_won), 4)

    seconds = pts - firsts  # second serve attempts
    oseconds = opts - ofirsts  # opponent second-serve attempts

    return {
        "win_rate": _pct(wins, matches_count),
        "svc_pts_won": svc_pts_won,
        "ret_pts_won": ret_pts_won,
        "aces_per_game": _pct(aces, pts),       # A%  = aces / serve points
        "df_per_game": _pct(dfs, pts),           # DF% = DFs  / serve points
        "hold_pct": _pct(games - (chances - saved), games),
        "break_pct": _pct(ochances - osaved, ochances),
        "matches_count": int(matches_count),
        "first_in_pct": _pct(firsts, pts),       # 1stIn%
        "first_won_pct": _pct(fwon, firsts),     # 1stWon%
        "second_won_pct": _pct(swon, seconds),   # 2ndWon%
        "dominance_ratio": dominance_ratio,      # SPW% / (1 - RPW%)
        # Opponent-allowed (defensive) stats — "what opponents achieve vs this player"
        "allowed_aces_per_sp":    _pct(oaces, opts),            # opp ace%   against this player
        "allowed_df_per_sp":      _pct(odfs, opts),             # opp DF%    against this player
        "allowed_first_in_pct":   _pct(ofirsts, opts),          # opp 1stIn% against this player
        "allowed_first_won_pct":  _pct(ofwon, ofirsts),         # opp 1stWon% vs this player
        "allowed_second_won_pct": _pct(oswon, oseconds),        # opp 2ndWon% vs this player
        "allowed_hold_pct":       _pct(ogames - (ochances - osaved), ogames),  # opp hold% vs this player
        "break_points_created_per_return_game": _pct(ochances, ogames),
        "allowed_break_points_per_service_game": _pct(chances, games),
    }


def _season_cutoff(today: date) -> str:
    return date(today.year, 1, 1).strftime("%Y%m%d")


def _filter_players_for_refresh(
    players: list[tuple[int, str, str]],
    fresh_player_ids: set[int],
    *,
    skip_computed_today: bool,
) -> list[tuple[int, str, str]]:
    if not skip_computed_today:
        return players
    return [player for player in players if player[0] not in fresh_player_ids]


def _resolve_backfill_active_options(
    today_only: bool,
    match_days_back: int,
    match_days_ahead: int,
    skip_computed_today: bool,
    backfill_active: bool,
) -> tuple[bool, int, int, bool]:
    """Force a current-slate raw-history refresh without changing normal daily runs."""
    if not backfill_active:
        return today_only, match_days_back, match_days_ahead, skip_computed_today
    return True, 0, max(match_days_ahead, 1), False


async def _get_fresh_player_ids(
    db: "AsyncSession",
    player_ids: list[int],
    *,
    skip_computed_today: bool,
) -> set[int]:
    if not skip_computed_today or not player_ids:
        return set()

    from sqlalchemy import text

    rows = await db.execute(
        text(
            """
                SELECT DISTINCT player_id
                FROM player_rolling_stats
                WHERE player_id = ANY(:player_ids)
                  AND stat_period = :period
                  AND surface IS NULL
                  AND split_type = 'overall'
                  AND split_value = 'all'
                  AND computed_at >= CURRENT_DATE
            """
        ),
        {"player_ids": player_ids, "period": STAT_PERIOD},
    )
    return {row[0] for row in rows.fetchall()}


async def _upsert_stat_row(
    db: "AsyncSession",
    *,
    player_id: int,
    surface: Optional[str],
    stat_period: str,
    split_type: str,
    split_value: str,
    stats: dict,
) -> None:
    from app.repositories.players import PlayerRollingStats, upsert_rolling_stats

    await upsert_rolling_stats(db, PlayerRollingStats(
        player_id=player_id,
        surface=surface,
        stat_period=stat_period,
        split_type=split_type,
        split_value=split_value,
        **stats,
    ))


async def _upsert_baseline_rows(db: "AsyncSession", player_id: int, raw_rows: list, today: date) -> None:
    for stat_period, days in RECENCY_WINDOWS.items():
        cutoff = (today - timedelta(days=days)).strftime("%Y%m%d")
        stats = _aggregate(raw_rows, cutoff)
        if stats is None:
            continue
        await _upsert_stat_row(
            db,
            player_id=player_id,
            surface=None,
            stat_period=stat_period,
            split_type="overall",
            split_value="all",
            stats=stats,
        )
        if stat_period == STAT_PERIOD:
            for surf in ("Hard", "Clay", "Grass"):
                surf_stats = _aggregate(raw_rows, cutoff, surface=surf)
                if surf_stats is None:
                    continue
                await _upsert_stat_row(
                    db,
                    player_id=player_id,
                    surface=surf,
                    stat_period=stat_period,
                    split_type="overall",
                    split_value="all",
                    stats=surf_stats,
                )

    season_stats = _aggregate(raw_rows, _season_cutoff(today))
    if season_stats is not None:
        await _upsert_stat_row(
            db,
            player_id=player_id,
            surface=None,
            stat_period="season",
            split_type="overall",
            split_value="all",
            stats=season_stats,
        )


async def _upsert_opp_rank_rows(db: "AsyncSession", player_id: int, raw_rows: list, today: date) -> None:
    cutoff = (today - timedelta(days=WINDOW_DAYS)).strftime("%Y%m%d")
    for bucket in OPP_RANK_BUCKETS:
        bucket_stats = _aggregate(raw_rows, cutoff, opp_rank_bucket=bucket)
        if bucket_stats is None:
            continue
        await _upsert_stat_row(
            db,
            player_id=player_id,
            surface=None,
            stat_period=STAT_PERIOD,
            split_type="opp_rank",
            split_value=bucket,
            stats=bucket_stats,
        )
        for surf in ("Hard", "Clay", "Grass"):
            surf_bucket_stats = _aggregate(raw_rows, cutoff, surface=surf, opp_rank_bucket=bucket)
            if surf_bucket_stats is None:
                continue
            await _upsert_stat_row(
                db,
                player_id=player_id,
                surface=surf,
                stat_period=STAT_PERIOD,
                split_type="opp_rank",
                split_value=bucket,
                stats=surf_bucket_stats,
            )


async def _persist_player_stats(
    db: "AsyncSession",
    player_id: int,
    raw_rows: list,
    today: date,
) -> None:
    """Write every rolling-stats row for one player.

    Separate from the fetch so the batch run can replay the write after a deadlock
    without spending another TennisAbstract request.
    """
    await _upsert_baseline_rows(db, player_id, raw_rows, today)
    await _upsert_opp_rank_rows(db, player_id, raw_rows, today)
    from app.repositories.player_match_stats import upsert_player_match_stats

    cutoff = (today - timedelta(days=WINDOW_DAYS)).strftime("%Y%m%d")
    await upsert_player_match_stats(db, _parse_player_match_stats(player_id, raw_rows, cutoff))


# =============================================================================
# Single-player ingest (used by admin API endpoint)
# =============================================================================

async def ingest_single_player(
    db: "AsyncSession",
    player_id: int,
    player_name: str,
    tour: str,
    ta_slug_override: Optional[str] = None,
    commit: bool = True,
) -> dict:
    """
    Fetch TennisAbstract stats for a single player and upsert to DB.

    Slug resolution order:
      1. ta_slug_override argument (from admin endpoint or DB ta_slug field)
      2. _slug(player_name) — computed from name

    NOTE: _fetch_matches uses synchronous requests.get() which blocks the event loop.
    For the admin endpoint (low traffic / one player at a time) this is acceptable.
    For production hardening, wrap _fetch_matches in run_in_executor.

    Returns: {success, player_name, matches_found, error}
    """
    today = date.today()
    cutoff = (today - timedelta(days=WINDOW_DAYS)).strftime("%Y%m%d")

    raw_rows = _fetch_matches(player_name, tour=tour or "", slug_override=ta_slug_override)

    if raw_rows is None:
        return {
            "success": False,
            "player_name": player_name,
            "matches_found": 0,
            "error": "Not found on TennisAbstract (404 or parse error)",
        }

    stats = _aggregate(raw_rows, cutoff)
    if stats is None:
        return {
            "success": False,
            "player_name": player_name,
            "matches_found": len(raw_rows),
            "error": f"Insufficient data — fewer than 3 matches in last 52 weeks (found {len(raw_rows)} total)",
        }

    await _persist_player_stats(db, player_id, raw_rows, today)

    if commit:
        await db.commit()

    return {
        "success": True,
        "player_name": player_name,
        "matches_found": len(raw_rows),
        "error": None,
    }


# =============================================================================
# Main ingest
# =============================================================================

async def run(
    tour_filter: Optional[str] = None,
    limit: int = 500,
    sleep: float = 0.2,
    today_only: bool = False,
    match_days_back: int = 0,
    match_days_ahead: int = 0,
    skip_computed_today: bool = False,
    backfill_active: bool = False,
) -> None:
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    from app.db.pool import SessionLocal
    from app.db.retry import is_retryable_conflict, run_in_session_with_retry

    today_only, match_days_back, match_days_ahead, skip_computed_today = _resolve_backfill_active_options(
        today_only,
        match_days_back,
        match_days_ahead,
        skip_computed_today,
        backfill_active,
    )
    cutoff = (date.today() - timedelta(days=WINDOW_DAYS)).strftime("%Y%m%d")

    async with SessionLocal() as db:
        if today_only:
            # Players with a match in the window [today - match_days_back, today]
            query = """
                SELECT DISTINCT p.id, p.name, p.tour, p.ta_slug
                FROM players p
                JOIN matches m ON (m.p1_id = p.id OR m.p2_id = p.id)
                WHERE m.match_date >= CURRENT_DATE - :days_back
                  AND m.match_date <= CURRENT_DATE + :days_ahead
            """
            params: dict = {"days_back": match_days_back, "days_ahead": match_days_ahead}
            if tour_filter:
                query += " AND p.tour = :tour"
                params["tour"] = tour_filter.upper()
            query += " ORDER BY p.name"
        else:
            query = "SELECT id, name, tour, ta_slug FROM players"
            params = {}
            if tour_filter:
                query += " WHERE tour = :tour"
                params["tour"] = tour_filter.upper()
            query += " ORDER BY name LIMIT :lim"
            params["lim"] = limit

        rows = await db.execute(text(query), params)
        selected_players = [(r[0], r[1], r[2], r[3]) for r in rows.fetchall()]
        fresh_player_ids = await _get_fresh_player_ids(
            db,
            [player_id for player_id, *_ in selected_players],
            skip_computed_today=skip_computed_today,
        )

    players = _filter_players_for_refresh(
        selected_players,
        fresh_player_ids,
        skip_computed_today=skip_computed_today,
    )
    skipped_fresh = len(selected_players) - len(players)

    logger.info(
        "Player selection: players_selected=%d players_skipped_fresh=%d players_to_process=%d limit=%d window=%s",
        len(selected_players),
        skipped_fresh,
        len(players),
        limit,
        cutoff,
    )

    ok = fail = skip = 0
    today = date.today()

    for player_id, name, tour, ta_slug in players:
        # Fetched outside any transaction: a retry must not spend another
        # TennisAbstract request, and the 429 backoff inside this call is exactly
        # what used to hold row locks open for minutes.
        raw_rows = _fetch_matches(name, tour=tour or "", slug_override=ta_slug)

        if raw_rows is None:
            skip += 1
            logger.debug("Skip %s: Not found on TennisAbstract (404 or parse error)", name)
        elif _aggregate(raw_rows, cutoff) is None:
            skip += 1
            logger.debug(
                "Skip %s: Insufficient data, fewer than 3 matches in last 52 weeks (found %d total)",
                name,
                len(raw_rows),
            )
        else:
            async def _write(db, rows=raw_rows, pid=player_id):
                await _persist_player_stats(db, pid, rows, today)
                await db.commit()

            try:
                await run_in_session_with_retry(
                    _write, description=f"player_stats write for {name}"
                )
            except DBAPIError as exc:
                # One player losing every retry is not a reason to drop the rest
                # of the slate, which is what the unguarded deadlock used to do.
                # Anything that is not a lock conflict is a real bug, so let it
                # surface instead of reporting a slate of mystery failures.
                if not is_retryable_conflict(exc):
                    raise
                fail += 1
                logger.warning("Failed %s: write aborted after deadlock retries", name)
            else:
                ok += 1
                logger.debug("  %s (%s): %d matches", name, tour, len(raw_rows))

        if (ok + fail + skip) % 50 == 0 and (ok + fail + skip) > 0:
            logger.info("  Progress: %d ok, %d skip, %d fail", ok, skip, fail)

        time.sleep(sleep)

    logger.info("Done. %d ok, %d skipped, %d failed.", ok, skip, fail)


async def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest player serve/return stats from TennisAbstract JS files"
    )
    parser.add_argument("--tour", type=str, default=None, help="ATP or WTA (default: both)")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--sleep", type=float, default=0.2, help="Sleep between requests (seconds)")
    parser.add_argument("--today-only", action="store_true", help="Only fetch stats for players with a match today")
    parser.add_argument("--match-days-back", type=int, default=0, help="Include players from N days back (used with --today-only)")
    parser.add_argument("--match-days-ahead", type=int, default=1, help="Include players with matches N days ahead (default: 1)")
    parser.add_argument("--skip-computed-today", action="store_true", help="Skip players whose baseline last_52w stats were already computed today")
    parser.add_argument(
        "--backfill-active",
        action="store_true",
        help="Force a rate-limited 12-month raw-stat backfill for the current and next-day slate",
    )
    args = parser.parse_args()
    await run(
        tour_filter=args.tour,
        limit=args.limit,
        sleep=args.sleep,
        today_only=args.today_only,
        match_days_back=args.match_days_back,
        match_days_ahead=args.match_days_ahead,
        skip_computed_today=args.skip_computed_today,
        backfill_active=args.backfill_active,
    )


if __name__ == "__main__":
    configure_ingest_logging(level=logging.DEBUG, fmt="%(levelname)s %(message)s")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
