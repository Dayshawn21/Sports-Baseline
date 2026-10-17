"""
TennisAbstract ELO ingest.

Two modes:
  - Scrape:  fetch live from tennisabstract.com (weekly refresh)
  - CSV:     load from a local snapshot CSV (initial seed)

Both modes upsert into `players` and `player_elo` tables.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import re
import sys
from io import StringIO
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.ingest.log_config import configure_ingest_logging

logger = logging.getLogger(__name__)

ATP_URL = "https://tennisabstract.com/reports/atp_elo_ratings.html"
WTA_URL = "https://tennisabstract.com/reports/wta_elo_ratings.html"


# ── Scraping ──────────────────────────────────────────────────────────────────

def _extract_as_of_date(html: str) -> Optional[dt.date]:
    m = re.search(r"Last\s+update:\s*(\d{4}-\d{2}-\d{2})", html, re.IGNORECASE)
    if m:
        try:
            return dt.date.fromisoformat(m.group(1))
        except ValueError:
            pass
    return None


def _snake(s: str) -> str:
    s = str(s).strip()
    s = re.sub(r"[^0-9A-Za-z]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_").lower()


def _pick_leaderboard(tables: list[pd.DataFrame]) -> pd.DataFrame:
    for t in tables:
        cols = [str(c).lower() for c in t.columns]
        if any("player" in c for c in cols) and any("elo" in c for c in cols):
            return t.copy()
    return max(tables, key=lambda x: x.shape[1]).copy()


def scrape_elo(url: str, tour: str) -> tuple[pd.DataFrame, dt.date]:
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    as_of = _extract_as_of_date(r.text) or dt.date.today()
    tables = pd.read_html(StringIO(r.text))
    df = _pick_leaderboard(tables)
    seen: dict[str, int] = {}
    new_cols = []
    for c in df.columns:
        c2 = _snake(c)
        if c2 in seen:
            seen[c2] += 1
            c2 = f"{c2}_{seen[c2]}"
        else:
            seen[c2] = 0
        new_cols.append(c2)
    df.columns = new_cols
    df.insert(0, "tour", tour.upper())
    df.insert(1, "as_of_date", as_of.isoformat())
    return df, as_of


def load_csv(path: Path, tour: str) -> tuple[pd.DataFrame, dt.date]:
    df = pd.read_csv(path)
    as_of = dt.date.today()
    if "as_of_date" in df.columns:
        try:
            as_of = dt.date.fromisoformat(str(df["as_of_date"].iloc[0]))
        except Exception:
            pass
    return df, as_of


# ── DB write ──────────────────────────────────────────────────────────────────

def _col(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _f(v: Any) -> Optional[float]:
    try:
        f = float(str(v).strip())
        return None if str(f) == "nan" else f
    except (ValueError, TypeError):
        return None


def _estimate_birth_date(age_decimal: float, as_of: dt.date) -> Optional[dt.date]:
    """Approximate birth date from decimal age and snapshot date. Accurate to ~2 weeks."""
    try:
        days = int(age_decimal * 365.25)
        return as_of - dt.timedelta(days=days)
    except (TypeError, ValueError):
        return None


async def upsert_elo_dataframe(db: AsyncSession, df: pd.DataFrame, as_of: dt.date) -> int:
    """Upsert ELO snapshot into players + player_elo tables."""
    from app.repositories.players import normalize_name, upsert_player, upsert_elo

    col_player = _col(df, "player", "player_name", "name")
    col_tour   = _col(df, "tour")
    col_elo    = _col(df, "elo")
    col_helo   = _col(df, "helo")
    col_celo   = _col(df, "celo")
    col_gelo   = _col(df, "gelo")
    col_age    = _col(df, "age")

    if not col_player or not col_elo:
        raise ValueError(f"Required columns missing. Got: {list(df.columns)}")

    count = 0
    for _, row in df.iterrows():
        player_name = str(row[col_player]).strip()
        if not player_name or player_name.lower() == "nan":
            continue

        tour = str(row[col_tour]).strip().upper() if col_tour else "ATP"
        elo  = _f(row[col_elo])
        if elo is None:
            continue

        helo = _f(row[col_helo]) if col_helo else None
        celo = _f(row[col_celo]) if col_celo else None
        gelo = _f(row[col_gelo]) if col_gelo else None

        # Estimate birth date from age column (accurate to ~2 weeks, sufficient for d_age feature)
        birth_date = None
        if col_age:
            age_val = _f(row[col_age])
            if age_val is not None:
                birth_date = _estimate_birth_date(age_val, as_of)

        # Upsert player (creates if not exists, sets birth_date only if not already stored)
        player_id = await upsert_player(db, player_name, tour, birth_date=birth_date)

        # Upsert ELO
        await upsert_elo(db, player_id, as_of, elo, helo, celo, gelo)
        count += 1

    await db.commit()
    return count


# ── Single-player ELO fetch (used by admin API endpoint) ──────────────────────

def elo_tours_for(tour: str) -> list[str]:
    """
    TennisAbstract ELO tables to search for a player on `tour`, in order.

    There is no Challenger ELO page — Challenger men sit in the ATP table and
    livetennisapi files women's 125/ITF events under `challenger` too, so that
    label is gender-ambiguous and has to try both.
    """
    t = (tour or "").strip().upper()
    if t in ("ATP", "WTA"):
        return [t]
    if t == "CHALLENGER":
        return ["ATP", "WTA"]
    return []

async def fetch_single_player_elo(
    db: AsyncSession,
    player_id: int,
    player_name: str,
    tour: str,
    ta_name_override: Optional[str] = None,
) -> dict:
    """
    Scrape TennisAbstract's ELO ratings page for the player's tour, find the
    player by name (normalized match), and upsert their ELO.

    ta_name_override: pass the correct TennisAbstract spelling when it differs
    from the Sofascore name stored in our DB.

    NOTE: scrape_elo() uses blocking requests.get() — acceptable for admin use.

    Returns: {success, player_name, elo, error}
    """
    from app.repositories.players import normalize_name, upsert_elo as _upsert_elo

    candidates = elo_tours_for(tour)
    if not candidates:
        return {"success": False, "player_name": player_name, "elo": None,
                "error": f"Unknown tour '{tour}' — expected ATP, WTA or CHALLENGER"}

    search_name = ta_name_override.strip() if ta_name_override else player_name
    search_norm = normalize_name(search_name)

    urls = {"ATP": ATP_URL, "WTA": WTA_URL}
    match_row = None
    as_of: dt.date | None = None
    col_elo = col_helo = col_celo = col_gelo = None
    errors: list[str] = []

    # CHALLENGER covers both the men's tour and women's 125/ITF, so the label
    # cannot pick the table — search each until the name turns up.
    for cand in candidates:
        try:
            df, cand_as_of = scrape_elo(urls[cand], cand)
        except Exception as e:
            errors.append(f"{cand}: failed to scrape TennisAbstract: {e}")
            continue

        col_player = _col(df, "player", "player_name", "name")
        col_elo    = _col(df, "elo")
        col_helo   = _col(df, "helo")
        col_celo   = _col(df, "celo")
        col_gelo   = _col(df, "gelo")

        if not col_player or not col_elo:
            errors.append(f"{cand}: could not parse ELO table from TennisAbstract")
            continue

        for _, row in df.iterrows():
            ta_name = str(row[col_player]).strip()
            if not ta_name or ta_name.lower() == "nan":
                continue
            if normalize_name(ta_name) == search_norm:
                match_row = row
                as_of = cand_as_of
                break

        if match_row is not None:
            break

    if match_row is None:
        if errors and len(errors) == len(candidates):
            return {"success": False, "player_name": player_name, "elo": None,
                    "error": "; ".join(errors)}
        searched = "/".join(candidates)
        return {
            "success": False,
            "player_name": player_name,
            "elo": None,
            "error": f"'{search_name}' not found in TennisAbstract {searched} ELO table",
        }

    elo = _f(match_row[col_elo])
    if elo is None:
        return {"success": False, "player_name": player_name, "elo": None,
                "error": "ELO value is null for this player in TennisAbstract"}

    helo = _f(match_row[col_helo]) if col_helo else None
    celo = _f(match_row[col_celo]) if col_celo else None
    gelo = _f(match_row[col_gelo]) if col_gelo else None

    await _upsert_elo(db, player_id, as_of, elo, helo, celo, gelo, source="admin_fetch")
    await db.commit()

    return {"success": True, "player_name": player_name, "elo": elo, "error": None}


# ── Entry points ──────────────────────────────────────────────────────────────

async def ingest_from_web(db: AsyncSession, tours: list[str] = ("ATP", "WTA")) -> dict[str, int]:
    urls = {"ATP": ATP_URL, "WTA": WTA_URL}
    results = {}
    for tour in tours:
        df, as_of = scrape_elo(urls[tour], tour)
        n = await upsert_elo_dataframe(db, df, as_of)
        results[tour] = n
        logger.info("Upserted %d %s ELO rows (as_of=%s)", n, tour, as_of)
    return results


async def ingest_from_csv(db: AsyncSession, csv_path: Path, tour: str) -> int:
    df, as_of = load_csv(csv_path, tour)
    n = await upsert_elo_dataframe(db, df, as_of)
    logger.info("Seeded %d %s ELO rows from %s (as_of=%s)", n, tour, csv_path.name, as_of)
    return n


# =============================================================================
# CLI entry point
# =============================================================================

async def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="TennisAbstract ELO ingest")
    parser.add_argument("--web", action="store_true", help="Scrape live from TennisAbstract")
    parser.add_argument("--tour", type=str, default=None, help="ATP or WTA (default: both)")
    args = parser.parse_args()

    from app.db.pool import SessionLocal

    tours = [args.tour.upper()] if args.tour else ["ATP", "WTA"]

    if args.web:
        async with SessionLocal() as db:
            results = await ingest_from_web(db, tours)
            for tour, n in results.items():
                logger.info("%s: %d rows upserted", tour, n)
    else:
        parser.print_help()


if __name__ == "__main__":
    configure_ingest_logging(fmt="%(levelname)s %(message)s")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
