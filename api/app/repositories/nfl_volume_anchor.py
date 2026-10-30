"""Read-only inputs for the 49b line anchor fit.

One row per player-game: the last standard full-game receptions line fetched
before kickoff (27a's convention), with the settled receptions once the game is
completed. A player with no stat row in a completed game (did not play) stays
null, which PrizePicks voids, so the caller never counts it as zero.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_volume_anchor import ANCHOR_FIT_SEASON, ANCHOR_MARKET
from app.core.nfl_volume_backtest import VolumeHistory
from app.core.nfl_volume_projection import VOLUME_FIRST_HISTORY_SEASON
from app.nfl.markets import STANDARD_ODDS_TYPE
from app.repositories.nfl_volume import get_volume_history


@dataclass(frozen=True)
class AnchorLine:
    line_id: int
    player_id: int
    game_id: int
    season: int
    week: int
    team_id: int | None
    is_home: bool | None
    position: str | None
    line: float
    fetched_at: datetime
    receptions: float | None


_ANCHOR_LINES = """
    SELECT DISTINCT ON (l.player_id, l.game_id)
           l.id AS line_id, l.player_id, l.game_id, g.season, g.week, p.position,
           CASE WHEN r.team_id IN (g.home_team_id, g.away_team_id) THEN r.team_id ELSE s.team_id END AS team_id,
           g.home_team_id, l.line, l.fetched_at,
           CASE WHEN g.status = 'completed' THEN s.receptions END AS receptions
    FROM sport_prop_lines l
    JOIN sport_games g ON g.sport = 'nfl' AND g.id = l.game_id
    JOIN sport_players p ON p.sport = 'nfl' AND p.id = l.player_id
    LEFT JOIN nfl_player_weekly_stats s ON s.player_id = l.player_id AND s.game_id = l.game_id
    LEFT JOIN nfl_player_weekly_rosters r
        ON r.player_id = l.player_id AND r.season = g.season AND r.week = g.week
    WHERE l.sport = 'nfl' AND l.market = :market AND l.segment = 'full_game' AND l.odds_type = :odds_type
      AND g.game_type = 'REG' AND g.season = :season AND g.week BETWEEN :first_week AND :last_week
      AND l.fetched_at < g.start_utc
    ORDER BY l.player_id, l.game_id, l.fetched_at DESC, l.id DESC
"""


def _check_season(season: int) -> None:
    if season < ANCHOR_FIT_SEASON:
        raise ValueError(
            f"season {season} is before {ANCHOR_FIT_SEASON}: no earlier season has stored lines, and 2025 is the holdout"
        )


async def get_anchor_lines(db: AsyncSession, season: int, first_week: int, last_week: int) -> list[AnchorLine]:
    _check_season(season)
    if last_week < first_week:
        raise ValueError(f"last_week {last_week} is before first_week {first_week}")
    rows = await db.execute(text(_ANCHOR_LINES), {
        "market": ANCHOR_MARKET, "odds_type": STANDARD_ODDS_TYPE, "season": season,
        "first_week": first_week, "last_week": last_week,
    })
    return [
        AnchorLine(
            line_id=row["line_id"], player_id=row["player_id"], game_id=row["game_id"], season=row["season"],
            week=row["week"], team_id=row["team_id"],
            is_home=None if row["team_id"] is None else row["team_id"] == row["home_team_id"],
            position=row["position"], line=float(row["line"]), fetched_at=row["fetched_at"],
            receptions=float(row["receptions"]) if row["receptions"] is not None else None,
        )
        for row in rows.mappings()
    ]


async def get_anchor_history(db: AsyncSession, season: int) -> VolumeHistory:
    """49a's history for the projections, bounded below by its own named floor, through the fit season."""
    _check_season(season)
    return await get_volume_history(db, VOLUME_FIRST_HISTORY_SEASON, season)
