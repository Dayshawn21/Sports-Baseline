"""Prop-line and frozen-prediction SQL shared by every team sport (17c).

Only queries that touch nothing but the `sport_*` tables live here; anything
joining a sport's own stat, roster or snap tables stays in that sport's
repository. Every read and write is scoped by the `sport` argument, so one
sport never reaches another's rows.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prop_predictions import PropPredictionRow


async def insert_prop_line(
    db: AsyncSession,
    sport: str,
    *,
    provider: str,
    provider_prop_id: str,
    market: str,
    segment: str,
    line: Decimal,
    start_time: datetime | None,
    player_id: int | None,
    game_id: int | None,
    odds_type: str | None,
    raw: dict,
) -> None:
    await db.execute(text("""
        INSERT INTO sport_prop_lines (sport, provider, provider_prop_id, market, segment, line,
                                      start_time, player_id, game_id, odds_type, raw_json)
        VALUES (:sport, :provider, :provider_id, :market, :segment, :line,
                :start_time, :player_id, :game_id, :odds_type, CAST(:raw AS jsonb))
    """), {"sport": sport, "provider": provider, "provider_id": provider_prop_id, "market": market,
           "segment": segment, "line": line, "start_time": start_time, "player_id": player_id,
           "game_id": game_id, "odds_type": odds_type, "raw": json.dumps(raw, default=str)})


async def get_game_index(db: AsyncSession, sport: str) -> dict[tuple[str, date], int]:
    """(team code, game date) -> game id, for both sides of every game.

    Loaded whole rather than queried per line: a few thousand rows, and prop
    ingest resolves hundreds of lines in one pass.
    """
    rows = await db.execute(
        text("""
            SELECT home.team_code, away.team_code, g.game_date, g.id
            FROM sport_games g
            JOIN sport_teams home ON home.sport = :sport AND home.id = g.home_team_id
            JOIN sport_teams away ON away.sport = :sport AND away.id = g.away_team_id
            WHERE g.sport = :sport
        """),
        {"sport": sport},
    )
    index: dict[tuple[str, date], int] = {}
    for home_code, away_code, game_date, game_id in rows.fetchall():
        index[(home_code, game_date)] = game_id
        index[(away_code, game_date)] = game_id
    return index


async def get_lines_for_relink(db: AsyncSession, sport: str) -> list[dict]:
    """Stored prop lines with the provider details resolution needs, for backfill."""
    rows = await db.execute(
        text("""
            SELECT id, raw_json ->> 'player_name', raw_json ->> 'player_team',
                   raw_json ->> 'player_position', start_time, player_id, game_id,
                   odds_type, raw_json -> 'source' -> 'attributes' ->> 'odds_type'
            FROM sport_prop_lines
            WHERE sport = :sport
            ORDER BY id
        """),
        {"sport": sport},
    )
    return [
        {"id": r[0], "player_name": r[1], "player_team": r[2], "player_position": r[3],
         "start_time": r[4], "player_id": r[5], "game_id": r[6],
         # Rows written before the column existed still carry the value in the
         # stored provider payload, so backfill needs no provider request.
         "odds_type": r[7], "provider_odds_type": r[8]}
        for r in rows.fetchall()
    ]


async def set_line_linkage(
    db: AsyncSession,
    sport: str,
    line_id: int,
    player_id: int | None,
    game_id: int | None,
    odds_type: str | None = None,
) -> None:
    await db.execute(
        text("""
            UPDATE sport_prop_lines
            SET player_id = :player_id, game_id = :game_id, odds_type = :odds_type
            WHERE sport = :sport AND id = :id
        """),
        {"sport": sport, "id": line_id, "player_id": player_id, "game_id": game_id, "odds_type": odds_type},
    )


async def get_player_aliases(db: AsyncSession, sport: str) -> dict[str, int]:
    """Provider name key -> player id, for overriding or completing automatic matching."""
    rows = await db.execute(
        text("SELECT alias_name_norm, player_id FROM sport_player_aliases WHERE sport = :sport"),
        {"sport": sport},
    )
    return {row[0]: row[1] for row in rows.fetchall()}


_PREDICTION_COLUMNS = (
    "prop_line_id", "model_version", "over_probability_version", "projection", "p_over", "p_under", "edge",
    "quality_flags", "feature_snapshot", "generated_at",
)
_PREDICTION_RECORD_TYPES = (
    "prop_line_id bigint, model_version text, over_probability_version text, projection numeric, "
    "p_over double precision, p_under double precision, edge double precision, quality_flags text[], "
    "feature_snapshot jsonb, generated_at timestamptz"
)


async def insert_prop_predictions(db: AsyncSession, sport: str, rows: Sequence[PropPredictionRow]) -> int:
    """Store frozen predictions, never overwriting one already stored for that line and versions.

    One statement for the whole batch, as a slate week runs to thousands of
    lines. Returns how many rows were actually inserted.
    """
    if not rows:
        return 0
    columns = ", ".join(_PREDICTION_COLUMNS)
    result = await db.execute(
        text(f"""
            INSERT INTO sport_prop_predictions (sport, {columns})
            SELECT CAST(:sport AS text), {columns}
            FROM jsonb_to_recordset(CAST(:rows AS jsonb)) AS r({_PREDICTION_RECORD_TYPES})
            ON CONFLICT (prop_line_id, model_version, over_probability_version) DO NOTHING
            RETURNING id
        """),
        {"sport": sport, "rows": json.dumps([asdict(row) for row in rows], default=str)},
    )
    return len(result.fetchall())
