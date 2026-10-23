"""NHL persistence on shared sport tables and NHL-only box-score tables."""
from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, TypeVar

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nhl_odds import NhlGameMarket
from app.ingest.nhl_api import NhlGame, NhlGoalieGame, NhlSkaterGame

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
    if book not in ("bet365", "draftkings"):
        raise ValueError("NHL odds book must be bet365 or draftkings")
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
