from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import json
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class Prop:
    id: int
    player_id: Optional[int]
    player_name: Optional[str]
    match_id: Optional[int]
    source: str
    stat_type: str
    line: Decimal
    odds_type: Optional[str]
    fetched_at: datetime
    start_time: Optional[datetime]
    p1_odds: Optional[int] = None
    p2_odds: Optional[int] = None
    surface: Optional[str] = None
    raw_json: Optional[dict[str, Any]] = None
    match_status: Optional[str] = None
    match_link_invalid: bool = False
    # Best-of format of the linked match. None when no match is linked, which is
    # why callers default to 3 rather than treating None as a format.
    best_of: Optional[int] = None
    source_start_time: Optional[datetime] = None
    match_start_time: Optional[datetime] = None


async def get_today_props(db: AsyncSession, source: Optional[str] = None) -> list[Prop]:
    query = """
        WITH latest_props AS (
            SELECT DISTINCT ON (
                p.source,
                COALESCE(
                    p.player_id::text,
                    NULLIF(p.raw_json ->> 'player_name', ''),
                    NULLIF(p.raw_json -> 'attributes' ->> 'player_display_name', ''),
                    NULLIF(p.raw_json -> 'attributes' ->> 'description', '')
                ),
                p.start_time,
                p.stat_type,
                p.line,
                COALESCE(p.odds_type, '')
            )
                p.*
            FROM props p
            WHERE p.fetched_at >= now() - interval '24 hours'
    """
    params: dict = {}
    if source:
        query += " AND p.source = :source"
        params["source"] = source
    query += """
            ORDER BY
                p.source,
                COALESCE(
                    p.player_id::text,
                    NULLIF(p.raw_json ->> 'player_name', ''),
                    NULLIF(p.raw_json -> 'attributes' ->> 'player_display_name', ''),
                    NULLIF(p.raw_json -> 'attributes' ->> 'description', '')
                ),
                p.start_time,
                p.stat_type,
                p.line,
                COALESCE(p.odds_type, ''),
                p.fetched_at DESC,
                p.id DESC
        )
        SELECT
            p.id,
            p.player_id,
            COALESCE(
                pl.name,
                NULLIF(p.raw_json ->> 'player_name', ''),
                NULLIF(p.raw_json -> 'attributes' ->> 'player_display_name', ''),
                NULLIF(p.raw_json -> 'attributes' ->> 'description', '')
            ) AS player_name,
            COALESCE(relinked.id, p.match_id) AS match_id,
            p.source,
            p.stat_type,
            p.line,
            p.odds_type,
            p.fetched_at,
            COALESCE(p.start_time, m.start_utc, relinked.start_utc) AS start_time,
            NULL::int AS p1_odds,
            NULL::int AS p2_odds,
            COALESCE(relinked.surface, m.surface) AS surface,
            p.raw_json,
            COALESCE(relinked.status, m.status) AS match_status,
            (
                relinked.id IS NULL
                AND p.match_id IS NOT NULL
                AND (
                    m.id IS NULL
                    OR m.status IN ('completed', 'cancelled')
                    OR (
                        p.start_time IS NOT NULL
                        AND m.start_utc IS NOT NULL
                        AND ABS(EXTRACT(EPOCH FROM (m.start_utc - p.start_time))) > 12 * 3600
                    )
                )
            ) AS match_link_invalid,
            COALESCE(relinked.best_of, m.best_of) AS best_of,
            p.start_time AS source_start_time,
            CASE WHEN relinked.id IS NOT NULL THEN relinked.start_utc
                 ELSE m.start_utc END AS match_start_time
        FROM latest_props p
        LEFT JOIN players pl ON pl.id = p.player_id
        LEFT JOIN matches m ON m.id = p.match_id
        -- Props are linked to a match at ingest time, so a prop ingested before
        -- its match existed stores match_id NULL forever. Re-resolve here so the
        -- link appears as soon as the match lands, with no re-ingest. The date
        -- window is +/-1 day because a late match's local tournament day can
        -- differ from the prop's UTC date.
        --
        -- That date window alone once matched yesterday's finished meeting
        -- between the same two players, 23h away, and every projection then ran
        -- on the wrong match's odds and opponent. So the candidate must also be
        -- unplayed and close in time: of props linked over a sample week, 97%
        -- sat within 6h of their match and the rest tailed to 11h before a clean
        -- gap, with the wrong-day matches clustering past 21h.
        LEFT JOIN LATERAL (
            SELECT mm.id, mm.start_utc, mm.surface, mm.status, mm.best_of
            FROM matches mm
            WHERE (
                    p.match_id IS NULL
                 OR m.id IS NULL
                 OR m.status IN ('completed', 'cancelled')
                 OR (
                        p.start_time IS NOT NULL
                    AND m.start_utc IS NOT NULL
                    AND ABS(EXTRACT(EPOCH FROM (m.start_utc - p.start_time))) > 12 * 3600
                 )
              )
              AND p.player_id IS NOT NULL
              AND p.start_time IS NOT NULL
              AND (mm.p1_id = p.player_id OR mm.p2_id = p.player_id)
              AND mm.status NOT IN ('completed', 'cancelled')
              -- A match with no start time still ranks last in the ORDER BY.
              AND (
                    mm.start_utc IS NULL
                 OR ABS(EXTRACT(EPOCH FROM (mm.start_utc - p.start_time))) <= 12 * 3600
              )
              AND mm.match_date BETWEEN (p.start_time AT TIME ZONE 'UTC')::date - 1
                                    AND (p.start_time AT TIME ZONE 'UTC')::date + 1
            ORDER BY
                CASE WHEN mm.start_utc IS NULL THEN 1 ELSE 0 END,
                ABS(EXTRACT(EPOCH FROM (mm.start_utc - p.start_time))) ASC,
                mm.id ASC
            LIMIT 1
        ) relinked ON TRUE
    """
    query += " ORDER BY p.start_time ASC NULLS LAST, p.player_id, p.stat_type"

    rows = await db.execute(text(query), params)
    return [Prop(*r) for r in rows.fetchall()]


_BOOK_KEY_SQL = "CASE WHEN LOWER(mo.book) IN ('betonline.ag', 'betonline') THEN 'bet365' ELSE LOWER(mo.book) END"


async def get_today_match_odds_as_props(db: AsyncSession, books: list[str]) -> list[Prop]:
    if not books:
        return []

    # The ingest appends a row per run, so without the DISTINCT ON a day's
    # stale lines (a spread at -1.5 yesterday, -0.5 now) were priced as current.
    # Bet365 was stored as betonline.ag until 2026-09-25, so both names are one book.
    rows = await db.execute(
        text("""
            SELECT * FROM (
            SELECT DISTINCT ON (mo.match_id, mo.market, """ + _BOOK_KEY_SQL + """)
                mo.id,
                NULL::int AS player_id,
                CONCAT(p1.name, ' vs ', p2.name) AS player_name,
                mo.match_id,
                LOWER(mo.book) AS source,
                mo.market AS stat_type,
                mo.line::numeric AS line,
                NULL::text AS odds_type,
                mo.fetched_at,
                m.start_utc AS start_time,
                mo.p1_odds,
                mo.p2_odds,
                m.surface,
                NULL::jsonb AS raw_json,
                m.status AS match_status,
                false AS match_link_invalid,
                m.best_of
            FROM match_odds mo
            JOIN matches m ON m.id = mo.match_id
            JOIN players p1 ON p1.id = m.p1_id
            JOIN players p2 ON p2.id = m.p2_id
            WHERE mo.fetched_at >= now() - interval '24 hours'
              AND mo.line IS NOT NULL
              AND LOWER(mo.book) = ANY(CAST(:books AS text[]))
            ORDER BY mo.match_id, mo.market, """ + _BOOK_KEY_SQL + """, mo.fetched_at DESC
            ) latest
            ORDER BY start_time ASC NULLS LAST, match_id, stat_type, source
        """),
        {"books": [b.lower() for b in books]},
    )
    return [Prop(*r) for r in rows.fetchall()]


@dataclass(frozen=True)
class PrizePicksLineRow:
    prop_id: int
    player_id: int
    match_id: int
    tour: str
    stat_type: str
    odds_type: str | None
    line: float
    fetched_at: datetime
    start_utc: datetime
    player_is_p1: bool
    score: str | None
    best_of: int | None
    is_live: bool
    is_promo: bool


def build_prizepicks_line_row(row: dict) -> PrizePicksLineRow:
    return PrizePicksLineRow(**{**row, "line": float(row["line"])})


async def get_settleable_prizepicks_lines(db: AsyncSession) -> list[PrizePicksLineRow]:
    """Each PrizePicks line as it stood in its last snapshot before the match started.

    Ingest runs once a day and every row of a run shares one fetched_at, so the
    latest pre-start fetched_at per player, match, stat and odds type is one run's
    board. A line fetched at or after the start may already know the result.

    The 12-hour start-time guard is the one the props page applies: a stored link
    can point at an earlier meeting of the same two players, and settling against
    it would grade the wrong match.
    """
    rows = await db.execute(
        text("""
            WITH eligible AS (
                SELECT
                    p.id, p.player_id, p.match_id, p.stat_type, p.odds_type, p.line,
                    p.fetched_at, p.raw_json -> 'attributes' AS attrs,
                    m.tour, m.start_utc, m.score, m.best_of,
                    (p.player_id = m.p1_id) AS player_is_p1,
                    MAX(p.fetched_at) OVER (
                        PARTITION BY p.player_id, p.match_id, p.stat_type, COALESCE(p.odds_type, '')
                    ) AS closing_at
                FROM props p
                JOIN matches m ON m.id = p.match_id
                WHERE p.source = 'prizepicks'
                  AND p.player_id IN (m.p1_id, m.p2_id)
                  AND m.status = 'completed' AND m.winner_id IS NOT NULL AND m.start_utc IS NOT NULL
                  AND p.fetched_at < m.start_utc
                  AND (
                        p.start_time IS NULL
                     OR ABS(EXTRACT(EPOCH FROM (m.start_utc - p.start_time))) <= 12 * 3600
                  )
            )
            SELECT DISTINCT ON (player_id, match_id, stat_type, COALESCE(odds_type, ''), line)
                id AS prop_id, player_id, match_id, tour, stat_type, odds_type, line,
                fetched_at, start_utc, player_is_p1, score, best_of,
                (COALESCE((attrs ->> 'is_live')::boolean, false)
                 OR COALESCE((attrs ->> 'in_game')::boolean, false)) AS is_live,
                (COALESCE((attrs ->> 'is_promo')::boolean, false)
                 OR attrs ->> 'flash_sale_line_score' IS NOT NULL) AS is_promo
            FROM eligible
            WHERE fetched_at = closing_at
            ORDER BY player_id, match_id, stat_type, COALESCE(odds_type, ''), line, id DESC
        """)
    )
    return [build_prizepicks_line_row(dict(r)) for r in rows.mappings().all()]


@dataclass(frozen=True)
class PrizePicksCoverage:
    rows: int
    rows_linked: int
    player_matches: int
    player_matches_settled: int
    box_score_exact_date: int
    box_score_unique_in_window: int


async def get_prizepicks_link_coverage(db: AsyncSession) -> PrizePicksCoverage:
    """How far stored PrizePicks rows get toward a settleable box score.

    TennisAbstract dates its box scores by tournament start, so the same match
    usually sits up to two weeks before `match_date`, and a player's several wins
    in one event are indistinguishable. The window count is how many settled
    player-matches have exactly one candidate row: the baseline 26e must raise.
    """
    row = await db.execute(
        text("""
            WITH linked AS (
                SELECT DISTINCT p.player_id, p.match_id, m.match_date, LOWER(m.surface) AS surface,
                    (m.status = 'completed' AND m.winner_id IS NOT NULL) AS settled,
                    CASE WHEN m.winner_id = p.player_id THEN 'W' ELSE 'L' END AS result
                FROM props p
                JOIN matches m ON m.id = p.match_id
                WHERE p.source = 'prizepicks' AND p.player_id IS NOT NULL
            ), settled AS (
                SELECT l.*,
                    EXISTS (
                        SELECT 1 FROM player_match_stats s
                        WHERE s.player_id = l.player_id AND s.result = l.result
                          AND s.match_date = l.match_date
                    ) AS exact_date,
                    (
                        SELECT COUNT(*) FROM player_match_stats s
                        WHERE s.player_id = l.player_id AND s.result = l.result
                          AND s.match_date BETWEEN l.match_date - 14 AND l.match_date + 3
                          AND (s.surface IS NULL OR l.surface IS NULL OR LOWER(s.surface) = l.surface)
                    ) AS window_candidates
                FROM linked l
                WHERE l.settled
            )
            SELECT
                (SELECT COUNT(*) FROM props WHERE source = 'prizepicks') AS rows,
                (SELECT COUNT(*) FROM props
                 WHERE source = 'prizepicks' AND player_id IS NOT NULL AND match_id IS NOT NULL) AS rows_linked,
                (SELECT COUNT(*) FROM linked) AS player_matches,
                (SELECT COUNT(*) FROM settled) AS player_matches_settled,
                (SELECT COUNT(*) FROM settled WHERE exact_date) AS box_score_exact_date,
                (SELECT COUNT(*) FROM settled WHERE window_candidates = 1) AS box_score_unique_in_window
        """)
    )
    return PrizePicksCoverage(**dict(row.mappings().one()))


async def upsert_prop(
    db: AsyncSession,
    player_id: Optional[int],
    match_id: Optional[int],
    source: str,
    stat_type: str,
    line: float,
    odds_type: Optional[str] = None,
    start_time: Optional[datetime] = None,
    raw_json: Optional[dict] = None,
) -> None:
    await db.execute(
        text("""
            INSERT INTO props (player_id, match_id, source, stat_type, line, odds_type, start_time, raw_json)
            VALUES (:pid, :mid, :src, :stat, :line, :odds_type, :start, CAST(:raw AS jsonb))
        """),
        {
            "pid": player_id, "mid": match_id, "src": source, "stat": stat_type,
            "line": line, "odds_type": odds_type, "start": start_time,
            "raw": json.dumps(raw_json) if raw_json is not None else None,
        },
    )
