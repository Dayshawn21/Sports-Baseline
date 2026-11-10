"""NHL persistence on shared sport tables and NHL-only box-score tables."""
from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal, TypeVar, cast

from sqlalchemy import RowMapping, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nhl_odds import NHL_ODDS_BOOKS, NhlGameMarket
from app.core.nhl_player_values import NHL_FIRST_HISTORY_SEASON
from app.core.nhl_records import NhlResult
from app.core.nhl_projection_backtest import REFERENCE_GAMES, SERVED_GAME_TYPES, NhlHistoryRow
from app.core.nhl_prop_predictions import NhlFreezeLine, settle_frozen
from app.core.prop_ranking_check import FrozenLine
from app.ingest.nhl_api import NhlGame, NhlGoalieGame, NhlSkaterGame
from app.nhl.markets import NhlLineOnlyMarket

CHUNK_SIZE = 1000
_T = TypeVar("_T")
_COMMON_STAT_FIELDS = ("season", "is_home", "time_on_ice_seconds")
_SKATER_STAT_FIELDS = _COMMON_STAT_FIELDS + (
    "position", "goals", "assists", "points", "shots", "power_play_goals", "power_play_points",
    "shorthanded_points", "plus_minus", "hits", "blocked_shots", "faceoffs_won", "faceoffs_lost",
    "penalty_minutes", "giveaways", "takeaways", "ot_goals",
)
_GOALIE_STAT_FIELDS = _COMMON_STAT_FIELDS + ("started", "decision", "saves", "shots_against", "goals_against")


@dataclass(frozen=True)
class NhlPlayerRow:
    source_player_id: str
    name: str
    position: str | None
    team_id: int


def _chunks(rows: Sequence[_T], size: int = CHUNK_SIZE) -> Iterable[Sequence[_T]]:
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


async def upsert_team(db: AsyncSession, team_code: str, name: str) -> int:
    row = await db.execute(
        text("""
            INSERT INTO sport_teams (sport, team_code, name)
            VALUES ('nhl', :code, :name)
            ON CONFLICT (sport, team_code) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """),
        {"code": team_code, "name": name},
    )
    return row.scalar_one()


async def upsert_games(db: AsyncSession, games: Sequence[NhlGame], team_ids: dict[str, int]) -> dict[str, int]:
    """Refresh rescheduled games and return NHL game id to stored game id."""
    params = [
        {
            "game_id": game.game_id, "season": game.season, "week": game.week, "game_type": game.game_type,
            "game_date": game.game_date, "start_utc": game.start_utc,
            "home_team_id": team_ids[game.home_team], "away_team_id": team_ids[game.away_team],
            "home_score": game.home_score, "away_score": game.away_score,
            "status": game.status, "end_period": game.end_period,
        }
        for game in games
    ]
    statement = text("""
        INSERT INTO sport_games (
            sport, source_game_id, season, week, game_type, game_date, start_utc,
            home_team_id, away_team_id, home_score, away_score, status, end_period
        ) VALUES (
            'nhl', :game_id, :season, :week, :game_type, :game_date, :start_utc,
            :home_team_id, :away_team_id, :home_score, :away_score, :status, :end_period
        )
        ON CONFLICT (sport, source_game_id) DO UPDATE SET
            season = EXCLUDED.season,
            week = EXCLUDED.week,
            game_type = EXCLUDED.game_type,
            game_date = EXCLUDED.game_date,
            start_utc = EXCLUDED.start_utc,
            home_team_id = EXCLUDED.home_team_id,
            away_team_id = EXCLUDED.away_team_id,
            home_score = EXCLUDED.home_score,
            away_score = EXCLUDED.away_score,
            status = EXCLUDED.status,
            end_period = EXCLUDED.end_period,
            updated_at = now()
    """)
    for chunk in _chunks(params):
        await db.execute(statement, chunk)
    return await _ids_by_source(
        db, "SELECT source_game_id, id FROM sport_games WHERE sport = 'nhl' AND source_game_id IN :ids",
        [game.game_id for game in games],
    )


async def upsert_players(db: AsyncSession, players: Sequence[NhlPlayerRow]) -> dict[str, int]:
    """Team is the latest loaded game's team; historical teams belong to stat rows."""
    statement = text("""
        INSERT INTO sport_players (sport, source_player_id, name, position, team_id)
        VALUES ('nhl', :source_player_id, :name, :position, :team_id)
        ON CONFLICT (sport, source_player_id) DO UPDATE SET
            name = EXCLUDED.name,
            position = COALESCE(EXCLUDED.position, sport_players.position),
            team_id = EXCLUDED.team_id,
            updated_at = now()
    """)
    for chunk in _chunks([asdict(player) for player in players]):
        await db.execute(statement, chunk)
    return await _ids_by_source(
        db, "SELECT source_player_id, id FROM sport_players WHERE sport = 'nhl' AND source_player_id IN :ids",
        [player.source_player_id for player in players],
    )


async def upsert_skater_games(
    db: AsyncSession, rows: Sequence[NhlSkaterGame], player_ids: dict[str, int],
    game_ids: dict[str, int], team_ids: dict[str, int],
) -> int:
    return await _upsert_stat_rows(
        db, rows, player_ids, game_ids, team_ids, "nhl_skater_game_stats", _SKATER_STAT_FIELDS,
    )


async def upsert_goalie_games(
    db: AsyncSession, rows: Sequence[NhlGoalieGame], player_ids: dict[str, int],
    game_ids: dict[str, int], team_ids: dict[str, int],
) -> int:
    return await _upsert_stat_rows(
        db, rows, player_ids, game_ids, team_ids, "nhl_goalie_game_stats", _GOALIE_STAT_FIELDS,
    )


async def _upsert_stat_rows(
    db: AsyncSession, rows: Sequence[NhlSkaterGame | NhlGoalieGame], player_ids: dict[str, int],
    game_ids: dict[str, int], team_ids: dict[str, int],
    table: Literal["nhl_skater_game_stats", "nhl_goalie_game_stats"], fields: Sequence[str],
) -> int:
    params = []
    for row in rows:
        values = asdict(row)
        params.append({
            **{field: values[field] for field in fields},
            "player_id": player_ids[row.player_id], "game_id": game_ids[row.game_id],
            "team_id": team_ids[row.team], "opponent_team_id": team_ids[row.opponent],
        })
    statement = text(f"""
        INSERT INTO {table} (player_id, game_id, team_id, opponent_team_id, {", ".join(fields)})
        VALUES (:player_id, :game_id, :team_id, :opponent_team_id, {", ".join(f":{field}" for field in fields)})
        ON CONFLICT (player_id, game_id) DO UPDATE SET
            team_id = EXCLUDED.team_id,
            opponent_team_id = EXCLUDED.opponent_team_id,
            {", ".join(f"{field} = EXCLUDED.{field}" for field in fields)},
            fetched_at = now()
    """)
    for chunk in _chunks(params):
        await db.execute(statement, chunk)
    return len(params)


async def _ids_by_source(db: AsyncSession, sql: str, source_ids: Sequence[str]) -> dict[str, int]:
    if not source_ids:
        return {}
    statement = text(sql).bindparams(bindparam("ids", expanding=True))
    rows = await db.execute(statement, {"ids": list(set(source_ids))})
    return {source_id: row_id for source_id, row_id in rows.all()}


async def get_player_candidates(db: AsyncSession) -> list[tuple[int, str, str | None, str | None]]:
    rows = await db.execute(text("""
        SELECT p.id, p.name, t.team_code, p.position
        FROM sport_players p
        LEFT JOIN sport_teams t ON t.sport = 'nhl' AND t.id = p.team_id
        WHERE p.sport = 'nhl'
    """))
    return [(row[0], row[1], row[2], row[3]) for row in rows.fetchall()]


async def get_upcoming_games(
    db: AsyncSession, days_ahead: int = 2, *, now: datetime | None = None,
) -> list[dict[str, object]]:
    """Scheduled NHL REG/PST games in a rolling, aware UTC odds window."""
    reference = now if now is not None else datetime.now(timezone.utc)
    if reference.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if isinstance(days_ahead, bool) or not isinstance(days_ahead, int) or not 1 <= days_ahead <= 14:
        raise ValueError("days_ahead must be an integer from 1 to 14")
    reference = reference.astimezone(timezone.utc)
    rows = await db.execute(text("""
        SELECT g.id AS game_id, g.start_utc,
               home.team_code AS home_team, away.team_code AS away_team
        FROM sport_games g
        JOIN sport_teams home ON home.sport = 'nhl' AND home.id = g.home_team_id
        JOIN sport_teams away ON away.sport = 'nhl' AND away.id = g.away_team_id
        WHERE g.sport = 'nhl' AND g.game_type IN ('REG', 'PST')
          AND g.status = 'scheduled'
          AND g.start_utc > :now AND g.start_utc <= :until
        ORDER BY g.start_utc, g.id
    """), {"now": reference, "until": reference + timedelta(days=days_ahead)})
    return [dict(row) for row in rows.mappings()]


async def insert_game_odds_snapshot(
    db: AsyncSession, game_id: int, book: str, market: NhlGameMarket, *, event_id: int,
) -> int | None:
    """Append an Odds-API.io snapshot, or skip a game no longer eligible."""
    if book not in NHL_ODDS_BOOKS:
        raise ValueError("NHL odds book must be draftkings, fanduel or bet365")
    row = await db.execute(text("""
        INSERT INTO sport_game_odds (
            sport, game_id, provider, book, market, line, first_side, second_side,
            first_odds, second_odds, first_market_prob, second_market_prob, raw_json, fetched_at
        )
        SELECT 'nhl', g.id, 'odds_api_io', :book, :market, :line, :first_side, :second_side,
               :first_odds, :second_odds, :first_market_prob, :second_market_prob,
               CAST(:raw_json AS jsonb), statement_timestamp()
        FROM sport_games g
        WHERE g.id = :game_id AND g.sport = 'nhl'
          AND g.game_type IN ('REG', 'PST') AND g.status = 'scheduled'
          AND g.start_utc > statement_timestamp()
        RETURNING id
    """), {
        "game_id": game_id, "book": book, "market": market.market, "line": market.line,
        "first_side": market.first_side, "second_side": market.second_side,
        "first_odds": market.first_odds, "second_odds": market.second_odds,
        "first_market_prob": market.first_market_prob, "second_market_prob": market.second_market_prob,
        "raw_json": json.dumps({**market.raw_market, "event_id": event_id}, allow_nan=False),
    })
    return row.scalar_one_or_none()


async def get_game_dates(db: AsyncSession) -> list[date]:
    rows = await db.execute(text("""
        SELECT DISTINCT g.game_date FROM sport_games g
        WHERE g.sport = 'nhl' AND g.game_type IN ('REG', 'PST')
        ORDER BY g.game_date
    """))
    return list(rows.scalars())


async def _served_games(db: AsyncSession, condition: str, params: dict[str, object]) -> list[dict[str, object]]:
    rows = await db.execute(text(f"""
        SELECT g.id AS game_id, g.season, g.week, g.game_type, g.game_date, g.start_utc,
               g.status, g.away_score, g.home_score, g.end_period,
               away.team_code AS away_team, home.team_code AS home_team,
               away.name AS away_team_name, home.name AS home_team_name
        FROM sport_games g
        JOIN sport_teams home ON home.sport = 'nhl' AND home.id = g.home_team_id
        JOIN sport_teams away ON away.sport = 'nhl' AND away.id = g.away_team_id
        WHERE g.sport = 'nhl' AND g.game_type IN ('REG', 'PST') AND {condition}
        ORDER BY g.start_utc NULLS LAST, g.id
    """), params)
    return [dict(row) for row in rows.mappings()]


async def get_games_on(db: AsyncSession, game_date: date) -> list[dict[str, object]]:
    return await _served_games(db, "g.game_date = :game_date", {"game_date": game_date})


async def get_game(db: AsyncSession, game_id: int) -> dict[str, object] | None:
    games = await _served_games(db, "g.id = :game_id", {"game_id": game_id})
    return games[0] if games else None


async def get_completed_results(db: AsyncSession, seasons: Sequence[int]) -> list[NhlResult]:
    """Completed regular-season results of the given seasons, for W-L-OT records."""
    if not seasons:
        return []
    statement = text("""
        SELECT g.season, g.game_type, g.game_date, g.status, g.end_period,
               home.team_code, away.team_code, g.home_score, g.away_score
        FROM sport_games g
        JOIN sport_teams home ON home.sport = 'nhl' AND home.id = g.home_team_id
        JOIN sport_teams away ON away.sport = 'nhl' AND away.id = g.away_team_id
        WHERE g.sport = 'nhl' AND g.game_type = 'REG' AND g.status = 'completed' AND g.season IN :seasons
    """).bindparams(bindparam("seasons", expanding=True))
    rows = await db.execute(statement, {"seasons": list(seasons)})
    return [NhlResult(*row) for row in rows.fetchall()]


# All market readers share the same eligibility and book choice, including history.
_CHOSEN_ODDS = """
    WITH eligible AS (
        SELECT o.id, o.game_id, o.book, o.market, o.line, o.first_side,
               o.first_odds, o.second_odds, o.first_market_prob, o.fetched_at, g.start_utc,
               DENSE_RANK() OVER (
                   PARTITION BY o.game_id, o.market ORDER BY (o.book = 'draftkings') DESC
               ) AS book_rank
        FROM sport_game_odds o
        JOIN sport_games g ON g.sport = 'nhl' AND g.id = o.game_id
        WHERE o.sport = 'nhl' AND o.provider = 'odds_api_io'
          AND o.book IN ('draftkings', 'fanduel', 'bet365') AND o.game_id IN :game_ids
          AND g.game_type IN ('REG', 'PST')
          AND o.market IN ('moneyline', 'spread', 'total')
          AND (g.start_utc IS NULL OR o.fetched_at < g.start_utc)
    ), chosen AS (
        SELECT * FROM eligible WHERE book_rank = 1
    )
"""


async def _odds_read(db: AsyncSession, game_ids: Sequence[int], suffix: str) -> list[dict[str, object]]:
    if not game_ids:
        return []
    statement = text(_CHOSEN_ODDS + suffix).bindparams(bindparam("game_ids", expanding=True))
    rows = await db.execute(statement, {"game_ids": list(game_ids)})
    return [dict(row) for row in rows.mappings()]


async def get_latest_market_rows(db: AsyncSession, game_ids: Sequence[int]) -> list[dict[str, object]]:
    return await _odds_read(db, game_ids, """
        , ranked AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY game_id, market ORDER BY fetched_at DESC, id DESC
            ) AS recency FROM chosen
        )
        SELECT game_id, market, book, line, first_side, first_odds, second_odds,
               first_market_prob, fetched_at
        FROM ranked WHERE recency = 1 ORDER BY game_id, market
    """)


_MOVEMENT_ROWS = """
    , movement AS (
        SELECT id, game_id, market, book, fetched_at,
               CASE WHEN market = 'spread' AND first_side = 'away' THEN -line ELSE line END AS line
        FROM chosen WHERE market IN ('spread', 'total') AND line IS NOT NULL AND start_utc IS NOT NULL
    )
"""


async def get_line_movement(db: AsyncSession, game_ids: Sequence[int]) -> list[dict[str, object]]:
    return await _odds_read(db, game_ids, _MOVEMENT_ROWS + """
        , ranked AS (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY game_id, market ORDER BY fetched_at, id) AS from_open,
                   ROW_NUMBER() OVER (PARTITION BY game_id, market ORDER BY fetched_at DESC, id DESC) AS from_current
            FROM movement
        )
        SELECT game_id, market, book,
               MAX(line) FILTER (WHERE from_open = 1) AS open_line,
               MAX(line) FILTER (WHERE from_current = 1) AS current_line,
               MAX(fetched_at) FILTER (WHERE from_open = 1) AS open_fetched_at,
               MAX(fetched_at) FILTER (WHERE from_current = 1) AS current_fetched_at
        FROM ranked GROUP BY game_id, market, book ORDER BY game_id, market
    """)


async def get_game_line_history(db: AsyncSession, game_id: int) -> list[dict[str, object]]:
    return await _odds_read(db, [game_id], _MOVEMENT_ROWS + """
        SELECT market, book, line, fetched_at FROM movement ORDER BY market, fetched_at, id
    """)


def _latest_props(scope: str) -> str:
    return f"""
    WITH ranked AS (
        SELECT l.id AS line_id, l.game_id, l.provider, l.provider_prop_id, l.player_id, p.name AS player_name,
               p.position, l.raw_json ->> 'player_team' AS team, l.market, l.odds_type,
               l.line, l.fetched_at,
               ROW_NUMBER() OVER (
                   PARTITION BY l.game_id, l.provider, l.provider_prop_id ORDER BY l.fetched_at DESC, l.id DESC
               ) AS recency
        FROM sport_prop_lines l
        JOIN sport_games g ON g.sport = 'nhl' AND g.id = l.game_id
        JOIN sport_players p ON p.sport = 'nhl' AND p.id = l.player_id
        WHERE l.sport = 'nhl' AND l.provider = 'prizepicks' AND l.segment = 'full_game'
          AND l.provider_prop_id IS NOT NULL AND {scope}
          AND g.game_type IN ('REG', 'PST') AND l.market IN :markets
          AND (g.start_utc IS NULL OR l.fetched_at < g.start_utc)
    ), latest AS (SELECT * FROM ranked WHERE recency = 1)
"""


_LATEST_PROPS = _latest_props("l.game_id IN :game_ids")


async def _prop_read(db: AsyncSession, game_ids: Sequence[int], suffix: str) -> list[dict[str, object]]:
    if not game_ids:
        return []
    statement = text(_LATEST_PROPS + suffix).bindparams(
        bindparam("game_ids", expanding=True), bindparam("markets", expanding=True),
    )
    rows = await db.execute(statement, {"game_ids": list(game_ids), "markets": [m.value for m in NhlLineOnlyMarket]})
    return [dict(row) for row in rows.mappings()]


async def get_prop_line_counts(db: AsyncSession, game_ids: Sequence[int]) -> dict[int, int]:
    rows = await _prop_read(db, game_ids, "SELECT game_id, COUNT(*) AS count FROM latest GROUP BY game_id")
    return {int(str(row["game_id"])): int(str(row["count"])) for row in rows}


async def get_line_only_lines(db: AsyncSession, game_id: int) -> list[dict[str, object]]:
    return await _prop_read(db, [game_id], """
        SELECT provider, provider_prop_id, player_id, player_name, position, team,
               market, odds_type, line, fetched_at
        FROM latest ORDER BY player_name, player_id, market, odds_type, line, provider_prop_id
    """)


_DATE_PROPS = _latest_props("g.game_date = :game_date")


async def get_date_line_only_lines(db: AsyncSession, game_date: date) -> dict[int, list[dict[str, object]]]:
    """The same latest-offering rows as `get_line_only_lines`, for every served game on one date, by game id."""
    rows = await _player_prop_read(db, _DATE_PROPS, """
        SELECT game_id, provider, provider_prop_id, player_id, player_name, position, team,
               market, odds_type, line, fetched_at
        FROM latest ORDER BY game_id, player_name, player_id, market, odds_type, line, provider_prop_id
    """, {"game_date": game_date})
    by_game: dict[int, list[dict[str, object]]] = {}
    for row in rows:
        by_game.setdefault(int(str(row["game_id"])), []).append(row)
    return by_game


_PLAYER_PROPS = _latest_props("l.player_id = :player_id AND g.game_date = :game_date")
_PLAYER_PROP_DATES = _latest_props("l.player_id = :player_id")


async def get_player(db: AsyncSession, player_id: int) -> dict[str, object] | None:
    row = await db.execute(text("""
        SELECT id AS player_id, name, position FROM sport_players WHERE sport = 'nhl' AND id = :player_id
    """), {"player_id": player_id})
    found = row.mappings().first()
    return dict(found) if found else None


async def _player_prop_read(db: AsyncSession, scoped: str, suffix: str, params: dict[str, object]) -> list[dict[str, object]]:
    statement = text(scoped + suffix).bindparams(bindparam("markets", expanding=True))
    markets = [market.value for market in NhlLineOnlyMarket]
    rows = await db.execute(statement, {**params, "markets": markets})
    return [dict(row) for row in rows.mappings()]


async def get_player_line_dates(db: AsyncSession, player_id: int) -> list[date]:
    rows = await _player_prop_read(db, _PLAYER_PROP_DATES, """
        SELECT DISTINCT g.game_date FROM latest JOIN sport_games g ON g.id = latest.game_id ORDER BY g.game_date
    """, {"player_id": player_id})
    return [cast(date, row["game_date"]) for row in rows]


async def get_player_lines(db: AsyncSession, player_id: int, game_date: date) -> list[dict[str, object]]:
    return await _player_prop_read(db, _PLAYER_PROPS, """
        SELECT game_id, provider, provider_prop_id, player_id, player_name, position, team,
               market, odds_type, line, fetched_at
        FROM latest ORDER BY market, line, odds_type, provider_prop_id
    """, {"player_id": player_id, "game_date": game_date})


_SKATER_VALUE_COLUMNS = (
    "shots", "points", "assists", "goals", "power_play_points", "blocked_shots", "plus_minus",
    "hits", "faceoffs_won", "time_on_ice_seconds",
)
_GOALIE_VALUE_COLUMNS = ("saves", "goals_against")


async def get_player_played_games(
    db: AsyncSession, player_id: int, *, goalie: bool, before: date, first_season: int,
    opponent: str | None = None, limit: int | None = None,
) -> list[dict[str, object]]:
    """Newest-first games the player has a box-score row for, strictly before a date; goalies only when they started."""
    table = "nhl_goalie_game_stats" if goalie else "nhl_skater_game_stats"
    columns = _GOALIE_VALUE_COLUMNS if goalie else _SKATER_VALUE_COLUMNS
    rows = await db.execute(text(f"""
        SELECT g.game_date, opp.team_code AS opponent, {", ".join(f"s.{column}" for column in columns)}
        FROM {table} s
        JOIN sport_games g ON g.sport = 'nhl' AND g.id = s.game_id
        JOIN sport_teams opp ON opp.sport = 'nhl' AND opp.id = s.opponent_team_id
        WHERE s.player_id = :player_id AND g.game_type IN ('REG', 'PST') AND s.season >= :first_season
          AND g.game_date < :before {"AND s.started" if goalie else ""}
          AND (CAST(:opponent AS text) IS NULL OR opp.team_code = :opponent)
        ORDER BY g.game_date DESC, g.id DESC LIMIT :limit
    """), {
        "player_id": player_id, "first_season": first_season, "before": before,
        "opponent": opponent, "limit": limit,
    })
    return [dict(row) for row in rows.mappings()]


_HISTORY_SKATER_COLUMNS = (
    "goals", "assists", "points", "shots", "power_play_points", "blocked_shots", "plus_minus", "hits",
    "faceoffs_won", "time_on_ice_seconds",
)
_HISTORY_GOALIE_COLUMNS = ("saves", "goals_against", "time_on_ice_seconds")
_HISTORY_GAME_TYPES = "g.game_type IN (" + ", ".join(f"'{game_type}'" for game_type in SERVED_GAME_TYPES) + ")"


async def _history_rows(
    db: AsyncSession, table: str, columns: Sequence[str], goalie: bool, seasons: Sequence[int],
) -> list[NhlHistoryRow]:
    started = "s.started" if goalie else "TRUE"
    rows = await db.execute(text(f"""
        SELECT s.player_id, s.game_id, g.season, g.game_date, g.game_type, p.position, {started} AS started,
               {", ".join(f"s.{column}" for column in columns)}
        FROM {table} s
        JOIN sport_games g ON g.sport = 'nhl' AND g.id = s.game_id
        JOIN sport_players p ON p.sport = 'nhl' AND p.id = s.player_id
        WHERE g.season = ANY(:seasons) AND {_HISTORY_GAME_TYPES}
        ORDER BY g.game_date, g.id, s.player_id
    """), {"seasons": list(seasons)})
    return [_history_row(row, columns, goalie) for row in rows.mappings()]


def _history_row(row: RowMapping, columns: Sequence[str], goalie: bool) -> NhlHistoryRow:
    return NhlHistoryRow(
        player_id=int(row["player_id"]), game_id=int(row["game_id"]), season=int(row["season"]),
        game_date=row["game_date"], game_type=str(row["game_type"]), position=row["position"],
        is_goalie=goalie, started=bool(row["started"]),
        stats={column: None if row[column] is None else int(row[column]) for column in columns},
    )


async def get_projection_history(db: AsyncSession, seasons: Sequence[int]) -> list[NhlHistoryRow]:
    """Every served skater and goalie box-score row of the seasons, oldest first, for the projection backtest.

    The seasons are always named by the caller: a default could read the 2025-26 holdout by accident.
    A row exists only if the player dressed or played, so no row means did not play.
    """
    skaters = await _history_rows(db, "nhl_skater_game_stats", _HISTORY_SKATER_COLUMNS, False, seasons)
    goalies = await _history_rows(db, "nhl_goalie_game_stats", _HISTORY_GOALIE_COLUMNS, True, seasons)
    return sorted(skaters + goalies, key=lambda row: (row.game_date, row.game_id, row.is_goalie, row.player_id))


async def _prior_rows(
    db: AsyncSession, table: str, columns: Sequence[str], goalie: bool, player_ids: Sequence[int], before: date,
) -> list[NhlHistoryRow]:
    started = "s.started" if goalie else "TRUE"
    rows = await db.execute(text(f"""
        SELECT * FROM (
            SELECT s.player_id, s.game_id, g.season, g.game_date, g.game_type, p.position, {started} AS started,
                   {", ".join(f"s.{column}" for column in columns)},
                   ROW_NUMBER() OVER (PARTITION BY s.player_id ORDER BY g.game_date DESC, g.id DESC) AS recency
            FROM {table} s
            JOIN sport_games g ON g.sport = 'nhl' AND g.id = s.game_id
            JOIN sport_players p ON p.sport = 'nhl' AND p.id = s.player_id
            WHERE s.player_id = ANY(:player_ids) AND {_HISTORY_GAME_TYPES}
              AND g.season >= :first_season AND g.game_date < :before {"AND s.started" if goalie else ""}
        ) recent WHERE recency <= :limit
        ORDER BY player_id, game_date, game_id
    """), {"player_ids": list(player_ids), "first_season": NHL_FIRST_HISTORY_SEASON, "before": before, "limit": REFERENCE_GAMES})
    return [_history_row(row, columns, goalie) for row in rows.mappings()]


async def get_prior_history(db: AsyncSession, player_ids: Sequence[int], before: date) -> dict[int, list[NhlHistoryRow]]:
    """Each player's last 20 played games strictly before a date, oldest first, for the served projection.

    A goalie's rows are his starts only. The season floor is the same named bound the player page uses,
    so a later backfill cannot change what a projection covers.
    """
    if not player_ids:
        return {}
    skaters = await _prior_rows(db, "nhl_skater_game_stats", _HISTORY_SKATER_COLUMNS, False, player_ids, before)
    goalies = await _prior_rows(db, "nhl_goalie_game_stats", _HISTORY_GOALIE_COLUMNS, True, player_ids, before)
    by_player: dict[int, list[NhlHistoryRow]] = {}
    for row in skaters + goalies:
        by_player.setdefault(row.player_id, []).append(row)
    return by_player


async def get_current_week(db: AsyncSession, now: datetime) -> tuple[int, int] | None:
    """(season, week) of the next regular-season game not yet started, else the latest loaded week (56c4).

    Playoff games have no week, so only `REG` counts; freezing skips started games anyway.
    """
    upcoming = await db.execute(text("""
        SELECT season, week FROM sport_games
        WHERE sport = 'nhl' AND game_type = 'REG' AND week IS NOT NULL AND start_utc > :now
        ORDER BY start_utc, id
        LIMIT 1
    """), {"now": now})
    row = upcoming.fetchone()
    if row is None:
        latest = await db.execute(text("""
            SELECT season, week FROM sport_games
            WHERE sport = 'nhl' AND game_type = 'REG' AND week IS NOT NULL
            ORDER BY season DESC, week DESC
            LIMIT 1
        """))
        row = latest.fetchone()
    return (row[0], row[1]) if row is not None else None


_WEEK_SCOPE = "g.season = :season AND g.week = :week AND g.game_type = 'REG'"
_WEEK_PROPS = _latest_props(_WEEK_SCOPE)


async def get_week_freeze_lines(db: AsyncSession, season: int, week: int) -> list[NhlFreezeLine]:
    """Each linked full-game line of the week's `REG` games at its last snapshot before puck drop (56c4).

    The board's line rule (`_latest_props`), so a frozen row is what the board showed.
    """
    rows = await _player_prop_read(db, _WEEK_PROPS, """
        SELECT latest.line_id, latest.game_id, g.game_date, g.start_utc, latest.player_id, latest.team,
               latest.position, latest.market, latest.odds_type, latest.line, latest.fetched_at
        FROM latest JOIN sport_games g ON g.sport = 'nhl' AND g.id = latest.game_id
        ORDER BY g.start_utc NULLS LAST, latest.game_id, latest.line_id
    """, {"season": season, "week": week})
    return [
        NhlFreezeLine(
            line_id=int(str(row["line_id"])), game_id=int(str(row["game_id"])), game_date=cast(date, row["game_date"]),
            start_utc=cast("datetime | None", row["start_utc"]), player_id=int(str(row["player_id"])),
            team=cast("str | None", row["team"]), position=cast("str | None", row["position"]),
            market=str(row["market"]), odds_type=cast("str | None", row["odds_type"]),
            line=float(str(row["line"])), fetched_at=cast(datetime, row["fetched_at"]),
        )
        for row in rows
    ]


async def get_week_games(db: AsyncSession, season: int, week: int) -> list[dict[str, object]]:
    """The week's `REG` games in the shape the slate builders take, for loading their stored context."""
    return await _served_games(db, _WEEK_SCOPE, {"season": season, "week": week})


_MARKET_VALUES = [market.value for market in NhlLineOnlyMarket]
_SKATER_SETTLE_COLUMNS = ", ".join(f"sk.{column} AS s_{column}" for column in _SKATER_VALUE_COLUMNS)
_GOALIE_SETTLE_COLUMNS = ", ".join(
    f"gk.{column} AS g_{column}" for column in (*_GOALIE_VALUE_COLUMNS, "started", "time_on_ice_seconds")
)


async def get_frozen_gradeable_lines(db: AsyncSession, season: int) -> list[FrozenLine]:
    """The latest frozen pre-puck-drop prediction of every linked PrizePicks prop on a completed `REG` game (56c4).

    Graded at the line it was frozen on, NFL's 27j rule, and settled against the player's
    skater or goalie box score. A game with no box-score rows in either table is not loaded yet.
    """
    statement = text(f"""
        WITH frozen AS (
            SELECT DISTINCT ON (l.provider, l.provider_prop_id)
                   l.id, l.market, l.odds_type, l.line, l.player_id, l.game_id, g.week,
                   p.p_over, p.p_under, p.model_version, p.over_probability_version
            FROM sport_prop_predictions p
            JOIN sport_prop_lines l ON l.sport = 'nhl' AND l.id = p.prop_line_id
            JOIN sport_games g ON g.sport = 'nhl' AND g.id = l.game_id
            WHERE p.sport = 'nhl' AND g.season = :season AND g.game_type = 'REG' AND g.week IS NOT NULL
              AND g.status = 'completed' AND l.player_id IS NOT NULL AND l.provider_prop_id IS NOT NULL
              AND l.segment = 'full_game' AND l.market IN :markets
              AND l.fetched_at < g.start_utc AND p.generated_at < g.start_utc
            ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC, p.generated_at DESC, p.id DESC
        ),
        loaded_games AS (
            SELECT game_id FROM nhl_skater_game_stats WHERE game_id IN (SELECT game_id FROM frozen)
            UNION
            SELECT game_id FROM nhl_goalie_game_stats WHERE game_id IN (SELECT game_id FROM frozen)
        )
        SELECT frozen.*, sk.player_id IS NOT NULL AS has_skater_row, {_SKATER_SETTLE_COLUMNS},
               gk.player_id IS NOT NULL AS has_goalie_row, {_GOALIE_SETTLE_COLUMNS},
               lg.game_id IS NOT NULL AS game_has_box_scores
        FROM frozen
        LEFT JOIN nhl_skater_game_stats sk ON sk.player_id = frozen.player_id AND sk.game_id = frozen.game_id
        LEFT JOIN nhl_goalie_game_stats gk ON gk.player_id = frozen.player_id AND gk.game_id = frozen.game_id
        LEFT JOIN loaded_games lg ON lg.game_id = frozen.game_id
        ORDER BY frozen.week, frozen.id
    """).bindparams(bindparam("markets", expanding=True))
    rows = await db.execute(statement, {"season": season, "markets": _MARKET_VALUES})
    return [_frozen_line(row) for row in rows.mappings()]


def _frozen_line(row: RowMapping) -> FrozenLine:
    skater = {column: row[f"s_{column}"] for column in _SKATER_VALUE_COLUMNS} if row["has_skater_row"] else None
    goalie = (
        {column: row[f"g_{column}"] for column in (*_GOALIE_VALUE_COLUMNS, "started", "time_on_ice_seconds")}
        if row["has_goalie_row"] else None
    )
    return FrozenLine(
        line_id=row["id"], period=row["week"], player_id=row["player_id"], game_id=row["game_id"],
        market=row["market"], odds_type=row["odds_type"],
        outcome=settle_frozen(row["market"], float(row["line"]), skater, goalie, bool(row["game_has_box_scores"])),
        p_over=row["p_over"], p_under=row["p_under"], model_version=row["model_version"],
        over_probability_version=row["over_probability_version"],
    )


async def get_finished_weeks(db: AsyncSession, season: int) -> set[int]:
    """Weeks whose `REG` games are all completed, postponed or canceled, with every completed one's box scores loaded.

    A completed game without box scores holds its week open until the next load.
    """
    rows = await db.execute(text("""
        SELECT g.week FROM sport_games g
        WHERE g.sport = 'nhl' AND g.season = :season AND g.game_type = 'REG' AND g.week IS NOT NULL
        GROUP BY g.week
        HAVING bool_and(g.status IN ('completed', 'postponed', 'canceled'))
           AND bool_and(
                   g.status <> 'completed'
                   OR EXISTS (SELECT 1 FROM nhl_skater_game_stats s WHERE s.game_id = g.id)
                   OR EXISTS (SELECT 1 FROM nhl_goalie_game_stats s WHERE s.game_id = g.id)
               )
    """), {"season": season})
    return {row[0] for row in rows.fetchall()}


async def get_frozen_coverage(db: AsyncSession, season: int) -> dict[int, tuple[int, int]]:
    """Per week: (gradeable full-game lines on completed `REG` games, how many have any frozen pre-start row)."""
    statement = text("""
        WITH latest AS (
            SELECT DISTINCT ON (l.provider, l.provider_prop_id) l.provider, l.provider_prop_id, g.week
            FROM sport_prop_lines l
            JOIN sport_games g ON g.sport = 'nhl' AND g.id = l.game_id
            WHERE l.sport = 'nhl' AND g.season = :season AND g.game_type = 'REG' AND g.week IS NOT NULL
              AND g.status = 'completed' AND l.player_id IS NOT NULL AND l.provider_prop_id IS NOT NULL
              AND l.fetched_at < g.start_utc AND l.segment = 'full_game' AND l.market IN :markets
            ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC
        )
        SELECT latest.week, COUNT(*),
               COUNT(*) FILTER (WHERE EXISTS (
                   SELECT 1 FROM sport_prop_lines fl
                   JOIN sport_prop_predictions p ON p.sport = 'nhl' AND p.prop_line_id = fl.id
                   JOIN sport_games fg ON fg.sport = 'nhl' AND fg.id = fl.game_id
                   WHERE fl.sport = 'nhl' AND fl.provider = latest.provider
                     AND fl.provider_prop_id = latest.provider_prop_id
                     AND fl.fetched_at < fg.start_utc AND p.generated_at < fg.start_utc
               ))
        FROM latest
        GROUP BY latest.week ORDER BY latest.week
    """).bindparams(bindparam("markets", expanding=True))
    rows = await db.execute(statement, {"season": season, "markets": _MARKET_VALUES})
    return {week: (int(lines), int(frozen)) for week, lines, frozen in rows.fetchall()}
