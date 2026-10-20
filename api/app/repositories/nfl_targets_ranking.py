"""Read frozen Rec Targets and coverage without changing v4's grading inputs."""
from __future__ import annotations

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_targets_grading import TargetsSettlementInput, settle_targets
from app.core.nfl_targets_projection import NFL_TARGETS_MODEL_VERSION
from app.core.prop_ranking_check import FrozenLine


_ELIGIBLE_LINES = """
    eligible AS (
        SELECT l.id, l.provider, l.provider_prop_id, l.player_id, l.game_id,
               l.market, l.odds_type, l.line, l.fetched_at, g.week, g.start_utc
        FROM sport_prop_lines l
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = l.game_id
        JOIN sport_players pl ON pl.sport = 'nfl' AND pl.id = l.player_id
        WHERE l.sport = 'nfl' AND l.market = 'receiving_targets'
          AND l.segment = 'full_game' AND l.odds_type = 'standard'
          AND l.provider_prop_id IS NOT NULL AND pl.position IN ('RB', 'WR', 'TE')
          AND g.season = :season AND g.week BETWEEN 1 AND 18
          AND g.game_type = 'REG' AND g.status = 'completed'
          AND l.fetched_at < g.start_utc
    )
"""

_PREDICTION_FILTER = """
    p.sport = 'nfl' AND p.model_version = :model_version
    AND p.over_probability_version IS NULL AND p.generated_at < l.start_utc
"""

_FROZEN_SQL = f"""
    WITH {_ELIGIBLE_LINES}, frozen AS (
        SELECT DISTINCT ON (l.provider, l.provider_prop_id)
               l.*, p.p_over, p.p_under, p.model_version, p.over_probability_version
        FROM eligible l
        JOIN sport_prop_predictions p ON p.sport = 'nfl' AND p.prop_line_id = l.id
        WHERE {_PREDICTION_FILTER}
        ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC,
                 p.generated_at DESC, p.id DESC
    )
    SELECT frozen.*, s.targets, s.player_id IS NOT NULL AS player_has_stats,
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


def _frozen_line(row: RowMapping) -> FrozenLine:
    settled = settle_targets(TargetsSettlementInput(
        line=float(row["line"]) if row["line"] is not None else None,
        targets=float(row["targets"]) if row["targets"] is not None else None,
        player_has_stats=bool(row["player_has_stats"]), offense_snaps=row["offense_snaps"],
        game_has_stats=bool(row["game_has_stats"]),
    ))
    return FrozenLine(
        line_id=row["id"], period=row["week"], player_id=row["player_id"], game_id=row["game_id"],
        market=row["market"], odds_type=row["odds_type"], outcome=settled.outcome,
        p_over=row["p_over"], p_under=row["p_under"], model_version=row["model_version"],
        over_probability_version=row["over_probability_version"],
    )


async def get_frozen_gradeable_lines(db: AsyncSession, season: int) -> list[FrozenLine]:
    """Each prop's latest targets-version pre-kickoff frozen line, settled on targets."""
    rows = await db.execute(text(_FROZEN_SQL), {"season": season, "model_version": NFL_TARGETS_MODEL_VERSION})
    return [_frozen_line(row) for row in rows.mappings()]


async def get_frozen_coverage(db: AsyncSession, season: int) -> dict[int, tuple[int, int]]:
    """Eligible full-game standard props and those frozen under the targets/null-version identity."""
    rows = await db.execute(text(_COVERAGE_SQL), {"season": season, "model_version": NFL_TARGETS_MODEL_VERSION})
    return {row["week"]: (int(row["lines"]), int(row["frozen"])) for row in rows.mappings()}
