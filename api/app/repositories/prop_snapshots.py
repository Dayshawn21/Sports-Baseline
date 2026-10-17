from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tennis.prop_snapshots import PropProjectionSnapshot

_COLUMNS = (
    "prop_id", "projection_version", "player_id", "match_id", "stat_type", "odds_type", "line",
    "start_time", "recommendation", "confidence", "hit_probability", "p_over", "p_under", "p_push",
    "stat_avg", "ev_pct", "break_even_pct", "matches_count", "market_total_games",
    "projection_status", "data_quality_flags", "projection_inputs",
)
_RECORD_TYPES = (
    "prop_id bigint, projection_version text, player_id bigint, match_id bigint, stat_type text, "
    "odds_type text, line numeric, start_time timestamptz, recommendation text, confidence text, "
    "hit_probability double precision, p_over double precision, p_under double precision, "
    "p_push double precision, stat_avg double precision, ev_pct double precision, "
    "break_even_pct double precision, matches_count integer, market_total_games double precision, "
    "projection_status text, data_quality_flags text[], projection_inputs jsonb"
)


async def insert_prop_projection_snapshots(db: AsyncSession, snapshots: list[PropProjectionSnapshot]) -> int:
    """Store snapshots, skipping any already stored for that prop row and version.

    One statement for the whole batch: the database is remote, and a round trip
    per prop would turn a daily slate of several hundred into minutes.
    Returns how many rows were actually inserted.
    """
    if not snapshots:
        return 0
    columns = ", ".join(_COLUMNS)
    result = await db.execute(
        text(f"""
            INSERT INTO prop_projection_snapshots ({columns})
            SELECT {columns}
            FROM jsonb_to_recordset(CAST(:rows AS jsonb)) AS r({_RECORD_TYPES})
            ON CONFLICT (prop_id, projection_version) DO NOTHING
            RETURNING id
        """),
        {"rows": json.dumps([asdict(s) for s in snapshots], default=str)},
    )
    return len(result.fetchall())


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
    params: dict[str, str | int] = {"version": version}
    if player_id is not None:
        params["player_id"] = player_id
    rows = await db.execute(
        text("""
            SELECT DISTINCT ON (s.player_id, s.match_id, s.stat_type, COALESCE(s.odds_type, ''), s.line)
                s.id AS snapshot_id, s.player_id, s.match_id, m.tour, s.stat_type, s.odds_type, s.line,
                s.recommendation, s.confidence, s.hit_probability,
                (s.player_id = m.p1_id) AS player_is_p1, m.score, m.best_of, s.snapshot_at
            FROM prop_projection_snapshots s
            JOIN matches m ON m.id = s.match_id
            WHERE s.projection_version = :version
              AND s.snapshot_at < s.start_time
              AND s.player_id IN (m.p1_id, m.p2_id)
              AND m.status = 'completed' AND m.winner_id IS NOT NULL
              """ + player_filter + """
            ORDER BY s.player_id, s.match_id, s.stat_type, COALESCE(s.odds_type, ''), s.line,
                     s.snapshot_at DESC, s.id DESC
        """),
        params,
    )
    return [build_graded_prop_snapshot(dict(r)) for r in rows.mappings().all()]
