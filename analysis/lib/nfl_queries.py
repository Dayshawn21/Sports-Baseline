"""Read-only NFL queries for notebooks: regular-season games, team efficiency, giveaways."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import Engine, text

GAMES_SQL = text("""
SELECT g.id AS game_id, g.season, g.week, h.team_code AS home, a.team_code AS away,
       g.home_score, g.away_score, g.status
FROM sport_games g
JOIN sport_teams h ON h.id = g.home_team_id AND h.sport = 'nfl'
JOIN sport_teams a ON a.id = g.away_team_id AND a.sport = 'nfl'
WHERE g.sport = 'nfl' AND g.game_type = 'REG' AND g.season BETWEEN :first AND :last
ORDER BY g.season, g.week, g.id
""")

EFFICIENCY_SQL = text("""
SELECT e.game_id, t.team_code AS team, e.plays, e.epa, e.successes
FROM nfl_team_game_efficiency e
JOIN sport_games g ON g.id = e.game_id AND g.sport = 'nfl' AND g.game_type = 'REG'
JOIN sport_teams t ON t.id = e.team_id AND t.sport = 'nfl'
WHERE g.season BETWEEN :first AND :last
""")

# A NULL count in any player row makes the team-game sum NULL, read as not loaded.
GIVEAWAYS_SQL = text("""
SELECT s.game_id, t.team_code AS team, SUM(s.interceptions) + SUM(s.fumbles_lost) AS giveaways
FROM nfl_player_weekly_stats s
JOIN sport_games g ON g.id = s.game_id AND g.sport = 'nfl' AND g.game_type = 'REG'
JOIN sport_teams t ON t.id = s.team_id AND t.sport = 'nfl'
WHERE g.season BETWEEN :first AND :last
GROUP BY s.game_id, t.team_code
""")


def _read(engine: Engine, sql, first: int, last: int) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(sql, conn, params={"first": first, "last": last})


def games(engine: Engine, first: int, last: int) -> pd.DataFrame:
    return _read(engine, GAMES_SQL, first, last)


def efficiency(engine: Engine, first: int, last: int) -> pd.DataFrame:
    return _read(engine, EFFICIENCY_SQL, first, last)


def giveaways(engine: Engine, first: int, last: int) -> pd.DataFrame:
    return _read(engine, GIVEAWAYS_SQL, first, last)
