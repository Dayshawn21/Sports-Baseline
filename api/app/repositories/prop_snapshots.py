from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tennis.prop_snapshots import SNAPSHOT_ELIGIBILITY_POLICY, PropProjectionSnapshot

_COLUMNS = (
    "prop_id", "projection_version", "player_id", "match_id", "stat_type", "odds_type", "line",
    "start_time", "recommendation", "confidence", "hit_probability", "p_over", "p_under", "p_push",
    "stat_avg", "ev_pct", "break_even_pct", "matches_count", "market_total_games",
    "projection_status", "data_quality_flags", "projection_inputs", "snapshot_at",
)
_RECORD_TYPES = (
    "prop_id bigint, projection_version text, player_id bigint, match_id bigint, stat_type text, "
    "odds_type text, line numeric, start_time timestamptz, recommendation text, confidence text, "
    "hit_probability double precision, p_over double precision, p_under double precision, "
    "p_push double precision, stat_avg double precision, ev_pct double precision, "
    "break_even_pct double precision, matches_count integer, market_total_games double precision, "
    "projection_status text, data_quality_flags text[], projection_inputs jsonb, snapshot_at timestamptz"
)


@dataclass(frozen=True)
class SnapshotInsertCounts:
    inserted: int = 0
    already_stored: int = 0
    rejected_started: int = 0


def _captured_prestart_sql(alias: str, clock: str) -> str:
    # PostgreSQL LEAST ignores a missing start; two missing starts fail the comparison.
    return f"""
        {alias}.projection_inputs ->> 'snapshot_eligibility_policy' = :eligibility_policy
        AND COALESCE({alias}.projection_inputs ->> 'match_status_at_capture', '')
            NOT IN ('live', 'completed', 'cancelled')
        AND {clock} < LEAST(
            ({alias}.projection_inputs ->> 'source_start_time')::timestamptz,
            ({alias}.projection_inputs ->> 'match_start_time')::timestamptz
        )
    """


async def insert_prop_projection_snapshots(
    db: AsyncSession, snapshots: list[PropProjectionSnapshot],
) -> SnapshotInsertCounts:
    """Insert once per prop/version, counting start-boundary rejections separately.

    One statement for the whole batch: the database is remote, and a round trip
    per prop would turn a daily slate of several hundred into minutes.
    """
    if not snapshots:
        return SnapshotInsertCounts()
    columns = ", ".join(_COLUMNS)
    result = await db.execute(
        text(f"""
            WITH candidates AS (
                SELECT * FROM jsonb_to_recordset(CAST(:rows AS jsonb)) AS r({_RECORD_TYPES})
            ), eligible AS (
                SELECT * FROM candidates r
                WHERE r.snapshot_at < r.start_time
                  AND statement_timestamp() < r.start_time
                  AND {_captured_prestart_sql('r', 'GREATEST(r.snapshot_at, statement_timestamp())')}
            ), inserted AS (
                INSERT INTO prop_projection_snapshots ({columns})
                SELECT {columns} FROM eligible
                ON CONFLICT (prop_id, projection_version) DO NOTHING
                RETURNING id
            )
            SELECT (SELECT COUNT(*) FROM inserted) AS inserted,
                   (SELECT COUNT(*) FROM eligible) - (SELECT COUNT(*) FROM inserted) AS already_stored,
                   (SELECT COUNT(*) FROM candidates) - (SELECT COUNT(*) FROM eligible) AS rejected_started
        """),
        {
            "rows": json.dumps([asdict(s) for s in snapshots], default=str),
            "eligibility_policy": SNAPSHOT_ELIGIBILITY_POLICY,
        },
    )
    return SnapshotInsertCounts(**dict(result.mappings().one()))


@dataclass(frozen=True)
class GradedPropSnapshot:
    snapshot_id: int
    player_id: int
    match_id: int
    tour: str
    stat_type: str
    odds_type: str | None
    line: float
    recommendation: str | None
    confidence: str | None
    hit_probability: float | None
    player_is_p1: bool
    score: str | None
    best_of: int | None
    snapshot_at: datetime | None = None
    """The track record page groups picks by snapshot day (32b); the 26f report ignores it."""


def build_graded_prop_snapshot(row: dict) -> GradedPropSnapshot:
    return GradedPropSnapshot(**{**row, "line": float(row["line"])})


_LINE_KEY = "s.player_id, s.match_id, s.stat_type, COALESCE(s.odds_type, ''), s.line"
_LATEST_PRESTART_FINISHED_SQL = """s.projection_version = :version
              AND s.snapshot_at < s.start_time
              AND CASE WHEN s.projection_inputs ? 'snapshot_eligibility_policy' THEN (
                  """ + _captured_prestart_sql('s', 's.snapshot_at') + """
                  AND (m.start_utc IS NULL OR s.snapshot_at < m.start_utc)
              ) ELSE TRUE END
              AND s.player_id IN (m.p1_id, m.p2_id)
              AND m.status = 'completed' AND m.winner_id IS NOT NULL
              """


async def get_graded_prop_snapshots(
    db: AsyncSession, version: str, player_id: int | None = None,
) -> list[GradedPropSnapshot]:
    """The latest pre-start snapshot of each line, for matches that have finished.

    A line is snapshotted once per daily props fetch, so a prop listed two days
    running has two snapshots; the later one is the closer view and is the one
    graded, as 26b grades the closing line. `player_id` narrows it to one player
    for the player page (32c).
    """
    player_filter = "AND s.player_id = :player_id" if player_id is not None else ""
    params: dict[str, str | int] = {"version": version, "eligibility_policy": SNAPSHOT_ELIGIBILITY_POLICY}
    if player_id is not None:
        params["player_id"] = player_id
    rows = await db.execute(
        text("""
            SELECT DISTINCT ON (""" + _LINE_KEY + """)
                s.id AS snapshot_id, s.player_id, s.match_id, m.tour, s.stat_type, s.odds_type, s.line,
                s.recommendation, s.confidence, s.hit_probability,
                (s.player_id = m.p1_id) AS player_is_p1, m.score, m.best_of, s.snapshot_at
            FROM prop_projection_snapshots s
            JOIN matches m ON m.id = s.match_id
            WHERE """ + _LATEST_PRESTART_FINISHED_SQL + player_filter + """
            ORDER BY """ + _LINE_KEY + """, s.snapshot_at DESC, s.id DESC
        """),
        params,
    )
    return [build_graded_prop_snapshot(dict(r)) for r in rows.mappings().all()]


@dataclass(frozen=True)
class PropCheckSnapshot:
    """The latest pre-start snapshot of a line with what 48e's forward check slices and settles on."""

    snapshot_id: int
    player_id: int
    match_id: int
    match_tour: str | None
    p1_tour: str | None
    p2_tour: str | None
    stat_type: str
    odds_type: str | None
    line: float
    start_time: datetime
    p_over: float | None
    p_under: float | None
    p_push: float | None
    market_total_games: float | None
    data_quality_flags: tuple[str, ...]
    player_is_p1: bool
    score: str | None
    best_of: int | None


def build_prop_check_snapshot(row: dict) -> PropCheckSnapshot:
    return PropCheckSnapshot(**{
        **row, "line": float(row["line"]), "data_quality_flags": tuple(row["data_quality_flags"] or ()),
    })


async def get_prop_check_snapshots(db: AsyncSession, version: str) -> list[PropCheckSnapshot]:
    """The same latest pre-start snapshot per finished line that `get_graded_prop_snapshots` grades."""
    rows = await db.execute(
        text("""
            SELECT DISTINCT ON (""" + _LINE_KEY + """)
                s.id AS snapshot_id, s.player_id, s.match_id, m.tour AS match_tour,
                p1.tour AS p1_tour, p2.tour AS p2_tour, s.stat_type, s.odds_type, s.line, s.start_time,
                s.p_over, s.p_under, s.p_push, s.market_total_games, s.data_quality_flags,
                (s.player_id = m.p1_id) AS player_is_p1, m.score, m.best_of
            FROM prop_projection_snapshots s
            JOIN matches m ON m.id = s.match_id
            LEFT JOIN players p1 ON p1.id = m.p1_id
            LEFT JOIN players p2 ON p2.id = m.p2_id
            WHERE """ + _LATEST_PRESTART_FINISHED_SQL + """
            ORDER BY """ + _LINE_KEY + """, s.snapshot_at DESC, s.id DESC
        """),
        {"version": version, "eligibility_policy": SNAPSHOT_ELIGIBILITY_POLICY},
    )
    return [build_prop_check_snapshot(dict(r)) for r in rows.mappings().all()]
