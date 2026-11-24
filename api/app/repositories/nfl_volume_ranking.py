"""Read frozen `nfl-volume-v1` receptions rows and coverage without changing v4's grading inputs (49d).

Receptions is also a v4 market, so every predicate that picks the newest frozen
row is applied to the volume identity first; another model's row can neither
displace nor cover a volume row here, and (since 49c) a volume row cannot do
either to v4's.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_line_grading import GradeableLine, settle_line
from app.core.nfl_volume_anchor import ANCHOR_MARKET, NFL_VOLUME_ANCHOR_VERSION
from app.core.nfl_volume_projection import NFL_VOLUME_MODEL_VERSION
from app.core.prop_ranking_check import FrozenLine
from app.repositories.nfl_volume_serving import VOLUME_SERVING_ODDS_TYPES

Q_VOL_UNAVAILABLE = "q_vol_unavailable"
PROBABILITY_UNAVAILABLE = "probability_unavailable"


@dataclass(frozen=True)
class VolumeFrozenLine:
    """A frozen row settled on receptions, with the raw projection chance the log-loss clause compares to."""

    frozen: FrozenLine
    q_vol: float | None


_ELIGIBLE_LINES = """
    eligible AS (
        SELECT l.id, l.provider, l.provider_prop_id, l.player_id, l.game_id,
               l.market, l.segment, l.odds_type, l.line, l.fetched_at, g.season, g.week, g.start_utc
        FROM sport_prop_lines l
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = l.game_id
        JOIN sport_players pl ON pl.sport = 'nfl' AND pl.id = l.player_id
        WHERE l.sport = 'nfl' AND l.market = :market
          AND l.segment = 'full_game' AND l.odds_type = ANY(CAST(:odds_types AS text[]))
          AND l.provider_prop_id IS NOT NULL AND pl.position IN ('RB', 'WR', 'TE')
          AND g.season = :season AND g.week BETWEEN 1 AND 18
          AND g.game_type = 'REG' AND g.status = 'completed'
          AND l.fetched_at < g.start_utc
    )
"""

_PREDICTION_FILTER = """
    p.sport = 'nfl' AND p.model_version = :model_version
    AND p.over_probability_version = :over_probability_version AND p.generated_at < l.start_utc
"""

_FROZEN_SQL = f"""
    WITH {_ELIGIBLE_LINES}, frozen AS (
        SELECT DISTINCT ON (l.provider, l.provider_prop_id)
               l.*, p.p_over, p.p_under, p.model_version, p.over_probability_version,
               p.feature_snapshot ->> 'q_vol' AS q_vol
        FROM eligible l
        JOIN sport_prop_predictions p ON p.sport = 'nfl' AND p.prop_line_id = l.id
        WHERE {_PREDICTION_FILTER}
        ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC,
                 p.generated_at DESC, p.id DESC
    )
    SELECT frozen.*, s.receptions, s.player_id IS NOT NULL AS player_has_stats,
           sc.offense_snaps,
           EXISTS (SELECT 1 FROM nfl_player_weekly_stats gs WHERE gs.game_id = frozen.game_id) AS game_has_stats
    FROM frozen
    LEFT JOIN nfl_player_weekly_stats s ON s.player_id = frozen.player_id AND s.game_id = frozen.game_id
    LEFT JOIN nfl_player_snap_counts sc ON sc.player_id = frozen.player_id AND sc.game_id = frozen.game_id
    ORDER BY frozen.week, frozen.id
"""

_COVERAGE_SQL = f"""
    WITH {_ELIGIBLE_LINES}, latest AS (
        SELECT DISTINCT ON (l.provider, l.provider_prop_id) l.*
        FROM eligible l
        ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC
    )
    SELECT latest.week, COUNT(*) AS lines,
           COUNT(*) FILTER (WHERE EXISTS (
               SELECT 1 FROM eligible l
               JOIN sport_prop_predictions p ON p.sport = 'nfl' AND p.prop_line_id = l.id
               WHERE l.provider = latest.provider AND l.provider_prop_id = latest.provider_prop_id
                 AND l.player_id = latest.player_id AND l.game_id = latest.game_id AND l.market = latest.market
                 AND {_PREDICTION_FILTER}
           )) AS frozen
    FROM latest
    GROUP BY latest.week ORDER BY latest.week
"""

_PARAMS = {
    "market": ANCHOR_MARKET, "model_version": NFL_VOLUME_MODEL_VERSION,
    "over_probability_version": NFL_VOLUME_ANCHOR_VERSION, "odds_types": list(VOLUME_SERVING_ODDS_TYPES),
}


def _number(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _valid_probability(value: float | None) -> bool:
    return value is not None and 0.0 <= value <= 1.0


def _outcome(row: RowMapping, q_vol: float | None, p_over: float | None, p_under: float | None) -> str:
    if q_vol is None or not 0.0 < q_vol < 1.0:
        return Q_VOL_UNAVAILABLE
    if not (_valid_probability(p_over) and _valid_probability(p_under)) or (p_over or 0.0) + (p_under or 0.0) <= 0.0:
        return PROBABILITY_UNAVAILABLE
    stat = _number(row["receptions"])
    if row["receptions"] is not None and (stat is None or stat < 0):
        return "stat_unavailable"
    line = _number(row["line"])
    if line is None or line < 0:
        return "invalid_line"
    return settle_line(GradeableLine(
        line_id=row["id"], season=row["season"], week=row["week"], game_id=row["game_id"],
        player_id=row["player_id"], market=row["market"], segment=row["segment"], odds_type=row["odds_type"],
        line=line, fetched_at=row["fetched_at"], stat_value=stat, offense_snaps=row["offense_snaps"],
        game_has_stats=bool(row["game_has_stats"]),
    )).outcome


def _volume_line(row: RowMapping) -> VolumeFrozenLine:
    q_vol, p_over, p_under = _number(row["q_vol"]), _number(row["p_over"]), _number(row["p_under"])
    return VolumeFrozenLine(
        frozen=FrozenLine(
            line_id=row["id"], period=row["week"], player_id=row["player_id"], game_id=row["game_id"],
            market=row["market"], odds_type=row["odds_type"], outcome=_outcome(row, q_vol, p_over, p_under),
            p_over=p_over, p_under=p_under, model_version=row["model_version"],
            over_probability_version=row["over_probability_version"],
        ),
        q_vol=q_vol,
    )


async def get_frozen_volume_lines(db: AsyncSession, season: int) -> list[VolumeFrozenLine]:
    """Each prop's latest volume-identity pre-kickoff frozen line, settled on receptions."""
    rows = await db.execute(text(_FROZEN_SQL), {"season": season, **_PARAMS})
    return [_volume_line(row) for row in rows.mappings()]


async def get_frozen_gradeable_lines(db: AsyncSession, season: int) -> list[FrozenLine]:
    return [item.frozen for item in await get_frozen_volume_lines(db, season)]


async def get_frozen_coverage(db: AsyncSession, season: int) -> dict[int, tuple[int, int]]:
    """Eligible full-game standard, goblin and demon props and those frozen under the volume model and its probability version."""
    rows = await db.execute(text(_COVERAGE_SQL), {"season": season, **_PARAMS})
    return {row["week"]: (int(row["lines"]), int(row["frozen"])) for row in rows.mappings()}
