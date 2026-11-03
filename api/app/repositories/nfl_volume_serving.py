"""Read-only pre-week inputs for serving the `nfl-volume-v1` receptions reference (49c).

Each eligible stored line comes with the player's completed history for the
current and previous season, which is all `prior_games` ever reads. History is
batched over the lines' players, never queried per player, and needs no
outcome from the line's own game, so it works for games not yet played.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_volume_anchor import ANCHOR_MARKET
from app.core.nfl_volume_backtest import VOLUME_STATS
from app.core.nfl_volume_projection import VOLUME_FIRST_HISTORY_SEASON, PlayerGame
from app.repositories.nfl import _player_teams_cte

VOLUME_SERVING_POSITIONS = ("RB", "WR", "TE")


@dataclass(frozen=True)
class VolumeServingLine:
    line_id: int
    game_id: int
    player_id: int
    player_name: str
    position: str
    season: int
    week: int
    player_team_id: int | None
    opponent_team_id: int | None
    is_home: bool | None
    start_utc: datetime | None
    market: str
    segment: str
    odds_type: str
    line: float | None
    provider: str
    fetched_at: datetime
    home_spread_margin: float | None
    total: float | None
    history: tuple[PlayerGame, ...]


_LATEST_LINES_CTE = """
    latest_volume_lines AS (
        SELECT DISTINCT ON (l.provider, l.provider_prop_id)
               l.id, l.game_id, l.player_id, p.name AS player_name, p.position,
               l.market, l.segment, l.odds_type, l.line, l.provider, l.fetched_at,
               g.season, g.week, g.start_utc, g.home_team_id, g.away_team_id, g.spread_line, g.total_line
        FROM sport_prop_lines l
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = l.game_id
        JOIN sport_players p ON p.sport = 'nfl' AND p.id = l.player_id
        WHERE l.sport = 'nfl' AND l.market = :market
          AND g.season = :season AND g.week = :week AND g.week BETWEEN 1 AND 18
          AND g.game_type = 'REG' AND l.segment = 'full_game' AND l.odds_type = 'standard'
          AND l.provider_prop_id IS NOT NULL AND l.player_id IS NOT NULL
          AND p.position = ANY(CAST(:positions AS text[]))
          AND (g.start_utc IS NULL OR l.fetched_at < g.start_utc)
        ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC
    )
"""

_SERVING_SQL = f"""
    WITH {_LATEST_LINES_CTE}, {_player_teams_cte()}
    SELECT l.*, pt.team_id AS player_team_id
    FROM latest_volume_lines l
    LEFT JOIN player_teams pt ON pt.player_id = l.player_id
    ORDER BY l.player_name, l.line, l.id
"""

# The roster row for the game's own week names the team, unless it names a team
# not in the game; the stat row's team then wins (the same rule as 49a's loader,
# so a served share reads the same attempts the backtest did).
_RESOLVED_TEAM = "CASE WHEN r.team_id IN (g.home_team_id, g.away_team_id) THEN r.team_id ELSE s.team_id END"

_HISTORY_SQL = f"""
    WITH team_attempts AS (
        SELECT s.game_id, s.team_id,
               SUM(s.passing_attempts) AS pass_attempts, SUM(s.rushing_attempts) AS rush_attempts
        FROM nfl_player_weekly_stats s
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
        WHERE g.game_type = 'REG' AND g.status = 'completed'
          AND g.season BETWEEN :first_history_season AND :season
          AND s.team_id IN (g.home_team_id, g.away_team_id)
        GROUP BY s.game_id, s.team_id
    )
    SELECT s.player_id, s.game_id, g.season, g.week,
           {", ".join(f"s.{stat}" for stat in VOLUME_STATS)},
           ta.pass_attempts, ta.rush_attempts
    FROM nfl_player_weekly_stats s
    JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
    LEFT JOIN nfl_player_weekly_rosters r
        ON r.player_id = s.player_id AND r.season = g.season AND r.week = g.week
    LEFT JOIN team_attempts ta ON ta.game_id = s.game_id AND ta.team_id = {_RESOLVED_TEAM}
    WHERE s.player_id = ANY(CAST(:player_ids AS bigint[]))
      AND g.game_type = 'REG' AND g.status = 'completed'
      AND g.season BETWEEN :first_history_season AND :season
      AND (g.season < :season OR g.week < :week)
    ORDER BY s.player_id, g.season, g.week
"""


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None  # type: ignore[arg-type]


async def _get_history(
    db: AsyncSession, season: int, week: int, player_ids: list[int],
) -> dict[int, tuple[PlayerGame, ...]]:
    """Prior games per player; a game with no team attempts is left out, as 49a's cases did."""
    result = await db.execute(text(_HISTORY_SQL), {
        "season": season, "week": week, "player_ids": player_ids,
        "first_history_season": max(season - 1, VOLUME_FIRST_HISTORY_SEASON),
    })
    by_player: dict[int, list[PlayerGame]] = {}
    seen: set[tuple[int, int]] = set()
    for row in result.mappings():
        key = (row["player_id"], row["game_id"])
        if key in seen:
            raise ValueError(f"player {key[0]} has more than one row in game {key[1]}")
        seen.add(key)
        if row["pass_attempts"] is None or row["rush_attempts"] is None:
            continue
        by_player.setdefault(row["player_id"], []).append(PlayerGame(
            season=row["season"], week=row["week"],
            stats={stat: _optional_float(row[stat]) for stat in VOLUME_STATS},
            team_pass_attempts=float(row["pass_attempts"]), team_rush_attempts=float(row["rush_attempts"]),
        ))
    return {player_id: tuple(games) for player_id, games in by_player.items()}


def _serving_row(row: RowMapping, history: tuple[PlayerGame, ...]) -> VolumeServingLine:
    team_id = row["player_team_id"]
    in_game = team_id is not None and team_id in (row["home_team_id"], row["away_team_id"])
    return VolumeServingLine(
        line_id=row["id"], game_id=row["game_id"], player_id=row["player_id"], player_name=row["player_name"],
        position=row["position"], season=row["season"], week=row["week"], player_team_id=team_id,
        opponent_team_id=(row["away_team_id"] if team_id == row["home_team_id"] else row["home_team_id"]) if in_game else None,
        is_home=team_id == row["home_team_id"] if in_game else None,
        start_utc=row["start_utc"], market=row["market"], segment=row["segment"], odds_type=row["odds_type"],
        line=_optional_float(row["line"]), provider=row["provider"], fetched_at=row["fetched_at"],
        home_spread_margin=_optional_float(row["spread_line"]), total=_optional_float(row["total_line"]),
        history=history,
    )


async def get_volume_serving_lines(db: AsyncSession, season: int, week: int) -> list[VolumeServingLine]:
    """Eligible stored receptions lines with batched pre-week history, independent of the game's outcome."""
    result = await db.execute(text(_SERVING_SQL), {
        "season": season, "week": week, "market": ANCHOR_MARKET, "positions": list(VOLUME_SERVING_POSITIONS),
    })
    rows = list(result.mappings())
    if not rows:
        return []
    history = await _get_history(db, season, week, sorted({row["player_id"] for row in rows}))
    return [_serving_row(row, history.get(row["player_id"], ())) for row in rows]
