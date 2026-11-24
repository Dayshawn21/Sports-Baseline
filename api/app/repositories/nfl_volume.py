"""Read-only history for the 49a volume x efficiency backtest.

Every regular-season player-game and team-game in a season range, with each
game's closing lines. Pre-week cutoffs are applied in pure code, so one load
serves every origin of the rolling backtest.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_projection_backtest import REPLAY_MARKETS_BY_POSITION
from app.core.nfl_volume_backtest import VOLUME_STATS, VolumeHistory, VolumePlayerGame, VolumeTeamGame
from app.core.nfl_volume_projection import VOLUME_FIRST_HISTORY_SEASON


_GAMES = """
    g.sport = 'nfl' AND g.game_type = 'REG' AND g.status = 'completed'
    AND g.season BETWEEN :first_season AND :last_season
"""

# The roster row for the game's own week names the team, unless it names a team
# not in the game (a trade reported a week late); the stat row's team then wins.
_PLAYER_GAMES = f"""
    SELECT s.player_id, s.game_id, g.season, g.week, p.position,
           CASE WHEN r.team_id IN (g.home_team_id, g.away_team_id) THEN r.team_id ELSE s.team_id END AS team_id,
           g.home_team_id,
           {", ".join(f"s.{stat}" for stat in VOLUME_STATS)},
           s.target_share, sc.offense_snaps
    FROM nfl_player_weekly_stats s
    JOIN sport_games g ON g.id = s.game_id
    JOIN sport_players p ON p.sport = 'nfl' AND p.id = s.player_id
    LEFT JOIN nfl_player_weekly_rosters r
        ON r.player_id = s.player_id AND r.season = g.season AND r.week = g.week
    LEFT JOIN nfl_player_snap_counts sc ON sc.player_id = s.player_id AND sc.game_id = s.game_id
    WHERE {_GAMES} AND p.position = ANY(CAST(:positions AS text[]))
    ORDER BY s.player_id, g.season, g.week
"""

_TEAM_GAMES = f"""
    SELECT s.game_id, s.team_id, g.season, g.week, s.team_id = g.home_team_id AS is_home,
           SUM(s.passing_attempts) AS pass_attempts, SUM(s.rushing_attempts) AS rush_attempts,
           MAX(e.plays) AS plays, g.spread_line, g.total_line
    FROM nfl_player_weekly_stats s
    JOIN sport_games g ON g.id = s.game_id
    LEFT JOIN nfl_team_game_efficiency e ON e.game_id = s.game_id AND e.team_id = s.team_id
    WHERE {_GAMES} AND s.team_id IN (g.home_team_id, g.away_team_id)
    GROUP BY s.game_id, s.team_id, g.season, g.week, g.home_team_id, g.spread_line, g.total_line
    ORDER BY g.season, g.week, s.game_id, s.team_id
"""


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None


async def get_volume_history(db: AsyncSession, first_season: int, last_season: int) -> VolumeHistory:
    if first_season < VOLUME_FIRST_HISTORY_SEASON:
        raise ValueError(f"first_season {first_season} is before the 49a history floor {VOLUME_FIRST_HISTORY_SEASON}")
    if last_season < first_season:
        raise ValueError(f"last_season {last_season} is before first_season {first_season}")
    seasons = {"first_season": first_season, "last_season": last_season}

    player_rows = await db.execute(text(_PLAYER_GAMES), seasons | {"positions": sorted(REPLAY_MARKETS_BY_POSITION)})
    player_games: list[VolumePlayerGame] = []
    seen: set[tuple[int, int]] = set()
    for row in player_rows.mappings():
        key = (row["player_id"], row["game_id"])
        if key in seen:
            raise ValueError(f"player {key[0]} has more than one row in game {key[1]}")
        seen.add(key)
        player_games.append(VolumePlayerGame(
            player_id=row["player_id"], game_id=row["game_id"], season=row["season"], week=row["week"],
            position=row["position"], team_id=row["team_id"], is_home=row["team_id"] == row["home_team_id"],
            stats={stat: _optional_float(row[stat]) for stat in VOLUME_STATS},
            target_share=_optional_float(row["target_share"]), offense_snaps=row["offense_snaps"],
        ))

    team_rows = await db.execute(text(_TEAM_GAMES), seasons)
    team_games = [
        VolumeTeamGame(
            game_id=row["game_id"], team_id=row["team_id"], season=row["season"], week=row["week"],
            is_home=row["is_home"], pass_attempts=_optional_float(row["pass_attempts"]),
            rush_attempts=_optional_float(row["rush_attempts"]), plays=row["plays"],
            home_spread_margin=_optional_float(row["spread_line"]), total=_optional_float(row["total_line"]),
        )
        for row in team_rows.mappings()
    ]
    return VolumeHistory(player_games, team_games)
