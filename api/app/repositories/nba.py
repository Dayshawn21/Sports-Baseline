"""NBA persistence on the shared `sport_*` tables plus `nba_player_game_stats` (item 20b).

Every statement on a `sport_*` table carries the literal `'nba'`, so NBA code
never reads or writes another sport's rows (the 17a/17b rule). Games, players
and box scores are written with executemany and their ids read back in one
query, so a season backfill is a few dozen round trips rather than tens of
thousands.
"""
from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from typing import cast

from sqlalchemy import RowMapping, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_line_only import LINE_ONLY_COLUMNS
from app.core.nba_projection_backtest import REFERENCE_GAMES, NbaHistoryRow
from app.core.nba_prop_predictions import NbaFreezeLine, settle_frozen
from app.core.nba_slate import NbaResult
from app.core.prop_ranking_check import FrozenLine
from app.ingest.hoopr_nba import NbaGame, NbaPlayerGame
from app.nba.markets import NbaLineOnlyMarket, NbaPropMarket

CHUNK_SIZE = 1000

_STAT_FIELDS = (
    "season", "is_home", "starter", "did_not_play", "dnp_reason", "minutes", "points", "rebounds",
    "offensive_rebounds", "defensive_rebounds", "assists", "steals", "blocks", "turnovers", "fouls",
    "field_goals_made", "field_goals_attempted", "three_pointers_made", "three_pointers_attempted",
    "free_throws_made", "free_throws_attempted", "plus_minus",
)


@dataclass(frozen=True)
class NbaPlayerRow:
    source_player_id: str
    name: str
    position: str | None
    team_id: int


def _chunks(rows: Sequence[dict], size: int = CHUNK_SIZE) -> Iterable[Sequence[dict]]:
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


async def upsert_team(db: AsyncSession, team_code: str, name: str) -> int:
    row = await db.execute(
        text("""
            INSERT INTO sport_teams (sport, team_code, name)
            VALUES ('nba', :code, :name)
            ON CONFLICT (sport, team_code) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """),
        {"code": team_code, "name": name},
    )
    return row.scalar_one()


async def upsert_games(db: AsyncSession, games: Sequence[NbaGame], team_ids: dict[str, int]) -> dict[str, int]:
    """Upsert games and return ESPN game id -> `sport_games.id`.

    A rescheduled game moves its date, start and week, so all three update.
    """
    params = [
        {
            "game_id": game.game_id, "season": game.season, "week": game.week, "game_type": game.game_type,
            "game_date": game.game_date, "start_utc": game.start_utc,
            "home_team_id": team_ids[game.home_team], "away_team_id": team_ids[game.away_team],
            "home_score": game.home_score, "away_score": game.away_score, "status": game.status,
        }
        for game in games
    ]
    statement = text("""
        INSERT INTO sport_games (
            sport, source_game_id, season, week, game_type, game_date, start_utc,
            home_team_id, away_team_id, home_score, away_score, status
        ) VALUES (
            'nba', :game_id, :season, :week, :game_type, :game_date, :start_utc,
            :home_team_id, :away_team_id, :home_score, :away_score, :status
        )
        ON CONFLICT (sport, source_game_id) DO UPDATE SET
            week = EXCLUDED.week,
            game_type = EXCLUDED.game_type,
            game_date = EXCLUDED.game_date,
            start_utc = COALESCE(EXCLUDED.start_utc, sport_games.start_utc),
            home_team_id = EXCLUDED.home_team_id,
            away_team_id = EXCLUDED.away_team_id,
            home_score = EXCLUDED.home_score,
            away_score = EXCLUDED.away_score,
            status = EXCLUDED.status,
            updated_at = now()
    """)
    for chunk in _chunks(params):
        await db.execute(statement, chunk)
    return await _ids_by_source(
        db, "SELECT source_game_id, id FROM sport_games WHERE sport = 'nba' AND source_game_id IN :ids",
        [game.game_id for game in games],
    )


async def upsert_players(db: AsyncSession, players: Sequence[NbaPlayerRow]) -> dict[str, int]:
    """Upsert players and return ESPN athlete id -> `sport_players.id`.

    `team_id` is the last team loaded; a past game's team is the box-score row's.
    """
    statement = text("""
        INSERT INTO sport_players (sport, source_player_id, name, position, team_id)
        VALUES ('nba', :source_player_id, :name, :position, :team_id)
        ON CONFLICT (sport, source_player_id) DO UPDATE SET
            name = EXCLUDED.name,
            position = COALESCE(EXCLUDED.position, sport_players.position),
            team_id = EXCLUDED.team_id,
            updated_at = now()
    """)
    for chunk in _chunks([asdict(player) for player in players]):
        await db.execute(statement, chunk)
    return await _ids_by_source(
        db, "SELECT source_player_id, id FROM sport_players WHERE sport = 'nba' AND source_player_id IN :ids",
        [player.source_player_id for player in players],
    )


async def upsert_player_games(
    db: AsyncSession,
    rows: Sequence[NbaPlayerGame],
    player_ids: dict[str, int],
    game_ids: dict[str, int],
    team_ids: dict[str, int],
) -> int:
    params = []
    for row in rows:
        values = asdict(row)
        for key in ("game_id", "player_id", "player_name", "position", "team", "opponent"):
            values.pop(key)
        params.append({
            **values,
            "player_id": player_ids[row.player_id], "game_id": game_ids[row.game_id],
            "team_id": team_ids[row.team], "opponent_team_id": team_ids[row.opponent],
        })
    statement = text(f"""
        INSERT INTO nba_player_game_stats (player_id, game_id, team_id, opponent_team_id, {", ".join(_STAT_FIELDS)})
        VALUES (:player_id, :game_id, :team_id, :opponent_team_id, {", ".join(f":{field}" for field in _STAT_FIELDS)})
        ON CONFLICT (player_id, game_id) DO UPDATE SET
            team_id = EXCLUDED.team_id,
            opponent_team_id = EXCLUDED.opponent_team_id,
            {", ".join(f"{field} = EXCLUDED.{field}" for field in _STAT_FIELDS)},
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
    """Every NBA player with the team of their latest loaded game, for prop-line resolution."""
    rows = await db.execute(text("""
        SELECT p.id, p.name, t.team_code, p.position
        FROM sport_players p
        LEFT JOIN sport_teams t ON t.sport = 'nba' AND t.id = p.team_id
        WHERE p.sport = 'nba'
    """))
    return [(row[0], row[1], row[2], row[3]) for row in rows.fetchall()]


async def get_upcoming_odds_games(db: AsyncSession, days_ahead: int) -> list[dict[str, object]]:
    """Scheduled NBA games with a tip-off time, for matching The Odds API events (item 20d)."""
    rows = await db.execute(
        text("""
            SELECT g.id, g.start_utc, home.team_code, away.team_code
            FROM sport_games g
            JOIN sport_teams home ON home.sport = 'nba' AND home.id = g.home_team_id
            JOIN sport_teams away ON away.sport = 'nba' AND away.id = g.away_team_id
            WHERE g.sport = 'nba' AND g.game_type IN ('REG', 'PIN', 'PST') AND g.status = 'scheduled'
              AND g.start_utc IS NOT NULL
              AND g.game_date BETWEEN CURRENT_DATE - 1 AND CURRENT_DATE + :days_ahead
            ORDER BY g.start_utc, g.id
        """),
        {"days_ahead": days_ahead},
    )
    return [
        {"game_id": row[0], "start_utc": row[1], "home_team": row[2], "away_team": row[3]}
        for row in rows.fetchall()
    ]


async def insert_game_odds_snapshot(
    db: AsyncSession,
    game_id: int,
    book: str,
    market: str,
    line: float | None,
    first_side: str,
    second_side: str,
    first_odds: int,
    second_odds: int,
    first_market_prob: float,
    second_market_prob: float,
    raw_json: dict[str, object] | None,
    *,
    provider: str,
) -> int:
    """Append one NBA game-market snapshot and return its id."""
    row = await db.execute(
        text("""
            INSERT INTO sport_game_odds (
                sport, game_id, book, market, line, first_side, second_side,
                first_odds, second_odds, first_market_prob, second_market_prob, raw_json, provider
            ) VALUES (
                'nba', :game_id, :book, :market, :line, :first_side, :second_side,
                :first_odds, :second_odds, :first_market_prob, :second_market_prob,
                CAST(:raw_json AS jsonb), :provider
            )
            RETURNING id
        """),
        {
            "game_id": game_id,
            "book": book,
            "market": market,
            "line": line,
            "first_side": first_side,
            "second_side": second_side,
            "first_odds": first_odds,
            "second_odds": second_odds,
            "first_market_prob": first_market_prob,
            "second_market_prob": second_market_prob,
            "raw_json": json.dumps(raw_json) if raw_json is not None else None,
            "provider": provider,
        },
    )
    return row.scalar_one()


# Every game reader below serves these; preseason never reaches the slate or a game page.
_SERVED_GAME_TYPES = "g.game_type IN ('REG', 'PIN', 'PST')"


async def get_game_dates(db: AsyncSession) -> list[dt.date]:
    """Every Eastern date holding a served NBA game, ascending."""
    rows = await db.execute(text(f"""
        SELECT DISTINCT g.game_date FROM sport_games g
        WHERE g.sport = 'nba' AND {_SERVED_GAME_TYPES}
        ORDER BY g.game_date
    """))
    return [row[0] for row in rows.fetchall()]


_GAME_KEYS = ("game_id", "season", "week", "game_type", "game_date", "start_utc", "status",
              "away_team", "home_team", "away_team_name", "home_team_name", "away_score", "home_score")


async def _served_games(db: AsyncSession, condition: str, params: dict[str, object]) -> list[dict[str, object]]:
    """Served games matching `condition` (on alias `g`), with team codes, names and scores."""
    rows = await db.execute(text(f"""
        SELECT g.id, g.season, g.week, g.game_type, g.game_date, g.start_utc, g.status,
               away.team_code, home.team_code, away.name, home.name, g.away_score, g.home_score
        FROM sport_games g
        JOIN sport_teams home ON home.sport = 'nba' AND home.id = g.home_team_id
        JOIN sport_teams away ON away.sport = 'nba' AND away.id = g.away_team_id
        WHERE g.sport = 'nba' AND {_SERVED_GAME_TYPES} AND {condition}
        ORDER BY g.start_utc NULLS LAST, g.id
    """), params)
    return [dict(zip(_GAME_KEYS, row)) for row in rows.fetchall()]


async def get_games_on(db: AsyncSession, game_date: dt.date) -> list[dict[str, object]]:
    """The served games on one Eastern date."""
    return await _served_games(db, "g.game_date = :game_date", {"game_date": game_date})


async def get_game(db: AsyncSession, game_id: int) -> dict[str, object] | None:
    """One served game, or None for a preseason, other-sport or missing id."""
    games = await _served_games(db, "g.id = :game_id", {"game_id": game_id})
    return games[0] if games else None


async def get_game_line_history(db: AsyncSession, game_id: int) -> list[dict[str, object]]:
    """Every pre-tip spread and total row for one game, one book per market, by market then fetch time.

    The same book rule as `get_line_movement`, so the chart and the slate's
    open-to-current move read from one book.
    """
    rows = await db.execute(text("""
        WITH pre_tip AS (
            SELECT o.id, o.book, o.market, o.line, o.fetched_at
            FROM sport_game_odds o JOIN sport_games g ON g.sport = 'nba' AND g.id = o.game_id
            WHERE o.sport = 'nba' AND o.provider = 'the_odds_api_us' AND o.game_id = :game_id AND o.market IN ('spread', 'total') AND o.line IS NOT NULL
              AND o.book = lower(o.book) AND (g.start_utc IS NULL OR o.fetched_at < g.start_utc)
        ), chosen_book AS (
            SELECT DISTINCT ON (market) market, book
            FROM pre_tip GROUP BY market, book
            ORDER BY market, (book = 'draftkings') DESC, COUNT(*) DESC, book
        )
        SELECT p.market, p.book, p.line, p.fetched_at
        FROM pre_tip p JOIN chosen_book c USING (market, book)
        ORDER BY p.market, p.fetched_at, p.id
    """), {"game_id": game_id})
    return [{"market": row[0], "book": row[1], "line": float(row[2]), "fetched_at": row[3]} for row in rows.fetchall()]


async def get_completed_results(db: AsyncSession, seasons: Sequence[int]) -> list[NbaResult]:
    """Completed regular-season results of the given seasons, for records."""
    rows = await db.execute(text("""
        SELECT g.season, g.game_type, g.game_date, g.status, home.team_code, away.team_code, g.home_score, g.away_score
        FROM sport_games g
        JOIN sport_teams home ON home.sport = 'nba' AND home.id = g.home_team_id
        JOIN sport_teams away ON away.sport = 'nba' AND away.id = g.away_team_id
        WHERE g.sport = 'nba' AND g.game_type = 'REG' AND g.status = 'completed' AND g.season = ANY(:seasons)
    """), {"seasons": list(seasons)})
    return [NbaResult(*row) for row in rows.fetchall()]


async def get_latest_market_rows(db: AsyncSession, game_ids: Sequence[int]) -> list[dict[str, object]]:
    """Per game and market, DraftKings' latest row, else the latest lowercase book's."""
    rows = await db.execute(text("""
        SELECT DISTINCT ON (o.game_id, o.market)
               o.game_id, o.market, o.book, o.line, o.first_side, o.first_odds, o.second_odds,
               o.first_market_prob, o.fetched_at
        FROM sport_game_odds o
        WHERE o.sport = 'nba' AND o.provider = 'the_odds_api_us' AND o.game_id = ANY(:game_ids) AND o.book = lower(o.book)
        ORDER BY o.game_id, o.market, (o.book = 'draftkings') DESC, o.fetched_at DESC, o.id DESC
    """), {"game_ids": list(game_ids)})
    keys = ("game_id", "market", "book", "line", "first_side", "first_odds", "second_odds", "first_market_prob", "fetched_at")
    return [dict(zip(keys, row)) for row in rows.fetchall()]


async def get_line_movement(db: AsyncSession, game_ids: Sequence[int]) -> list[dict[str, object]]:
    """First and last pre-tip spread and total per game, both from one book.

    NFL's rule (`get_week_line_movement`): DraftKings when it has a row, else the
    book with the most rows, so a switch between books never reads as movement.
    """
    rows = await db.execute(text("""
        WITH pre_tip AS (
            SELECT o.id, o.game_id, o.book, o.market, o.line, o.fetched_at
            FROM sport_game_odds o JOIN sport_games g ON g.sport = 'nba' AND g.id = o.game_id
            WHERE o.sport = 'nba' AND o.provider = 'the_odds_api_us' AND o.game_id = ANY(:game_ids) AND o.market IN ('spread', 'total')
              AND o.line IS NOT NULL AND o.book = lower(o.book)
              AND (g.start_utc IS NULL OR o.fetched_at < g.start_utc)
        ), chosen_book AS (
            SELECT DISTINCT ON (game_id, market) game_id, market, book
            FROM pre_tip GROUP BY game_id, market, book
            ORDER BY game_id, market, (book = 'draftkings') DESC, COUNT(*) DESC, book
        ), ranked AS (
            SELECT p.game_id, p.market, p.book, p.line, p.fetched_at,
                   ROW_NUMBER() OVER (PARTITION BY p.game_id, p.market ORDER BY p.fetched_at, p.id) AS from_open,
                   ROW_NUMBER() OVER (PARTITION BY p.game_id, p.market ORDER BY p.fetched_at DESC, p.id DESC) AS from_current
            FROM pre_tip p JOIN chosen_book c USING (game_id, market, book)
        )
        SELECT game_id, market, book,
               MAX(line) FILTER (WHERE from_open = 1), MAX(fetched_at) FILTER (WHERE from_open = 1),
               MAX(line) FILTER (WHERE from_current = 1), MAX(fetched_at) FILTER (WHERE from_current = 1)
        FROM ranked GROUP BY game_id, market, book
        ORDER BY game_id, market
    """), {"game_ids": list(game_ids)})
    return [
        {"game_id": row[0], "market": row[1], "book": row[2], "open_line": float(row[3]), "open_fetched_at": row[4],
         "current_line": float(row[5]), "current_fetched_at": row[6]}
        for row in rows.fetchall()
    ]


async def get_prop_line_counts(db: AsyncSession, game_ids: Sequence[int]) -> dict[int, int]:
    """Distinct stored full-game PrizePicks props per game, linked to a player or not."""
    rows = await db.execute(text("""
        SELECT l.game_id, COUNT(DISTINCT (l.provider, l.provider_prop_id))
        FROM sport_prop_lines l
        WHERE l.sport = 'nba' AND l.game_id = ANY(:game_ids) AND l.segment = 'full_game'
        GROUP BY l.game_id
    """), {"game_ids": list(game_ids)})
    return {row[0]: row[1] for row in rows.fetchall()}


_LINE_ONLY_MARKET_FILTER = "l.market IN ({})".format(", ".join(f"'{market.value}'" for market in NbaLineOnlyMarket))
# Every reader that projects, freezes or grades NBA lines applies this (20g2), as NFL's MODELLED_MARKET_FILTER.
NBA_MODELLED_MARKET_FILTER = "l.market IN ({})".format(", ".join(f"'{market.value}'" for market in NbaPropMarket))


async def get_line_only_lines(db: AsyncSession, game_id: int) -> list[dict[str, object]]:
    """Each linked full-game line-only prop on one served game, at its last snapshot before tip-off."""
    rows = await _game_prop_lines(db, "l.game_id = :game_id", {"game_id": game_id}, _LINE_ONLY_MARKET_FILTER)
    return [{key: value for key, value in row.items() if key != "game_id"} for row in rows]


async def get_modelled_lines(db: AsyncSession, game_id: int) -> list[dict[str, object]]:
    """Each linked full-game modelled prop on one served game, at its last snapshot before tip-off (20g2)."""
    rows = await _game_prop_lines(db, "l.game_id = :game_id", {"game_id": game_id}, NBA_MODELLED_MARKET_FILTER)
    return [{key: value for key, value in row.items() if key != "game_id"} for row in rows]


async def get_date_modelled_lines(db: AsyncSession, game_date: dt.date) -> dict[int, list[dict[str, object]]]:
    """The date's modelled lines, grouped by served game."""
    rows = await _game_prop_lines(db, "g.game_date = :game_date", {"game_date": game_date}, NBA_MODELLED_MARKET_FILTER)
    return _group_game_prop_lines(rows)


async def get_date_line_only_lines(db: AsyncSession, game_date: dt.date) -> dict[int, list[dict[str, object]]]:
    """The date's line-only props, grouped by served game."""
    rows = await _game_prop_lines(db, "g.game_date = :game_date", {"game_date": game_date}, _LINE_ONLY_MARKET_FILTER)
    return _group_game_prop_lines(rows)


def _group_game_prop_lines(rows: list[dict[str, object]]) -> dict[int, list[dict[str, object]]]:
    grouped: dict[int, list[dict[str, object]]] = {}
    for row in rows:
        game_id = cast(int, row.pop("game_id"))
        grouped.setdefault(game_id, []).append(row)
    return grouped


async def _game_prop_lines(
    db: AsyncSession, condition: str, params: dict[str, object], market_filter: str,
) -> list[dict[str, object]]:
    rows = await db.execute(text(f"""
        SELECT DISTINCT ON (l.provider, l.provider_prop_id)
               l.player_id, p.name, p.position, l.raw_json ->> 'player_team', l.market, l.odds_type,
               l.line, l.fetched_at, l.game_id
        FROM sport_prop_lines l
        JOIN sport_games g ON g.sport = 'nba' AND g.id = l.game_id
        JOIN sport_players p ON p.sport = 'nba' AND p.id = l.player_id
        WHERE l.sport = 'nba' AND {condition} AND l.segment = 'full_game' AND {_SERVED_GAME_TYPES}
          AND (g.start_utc IS NULL OR l.fetched_at < g.start_utc) AND {market_filter}
        ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC
    """), params)
    keys = ("player_id", "player_name", "position", "team", "market", "odds_type", "line", "fetched_at", "game_id")
    return [{**dict(zip(keys, row)), "line": float(row[6])} for row in rows.fetchall()]


async def get_current_week(db: AsyncSession, now: dt.datetime) -> tuple[int, int] | None:
    """(season, week) of the next regular-season game not yet tipped, else the latest loaded week (20g3).

    No grace after tip-off, unlike NFL's: freezing skips started games anyway,
    and play-in and playoff games have no week, so only `REG` counts.
    """
    upcoming = await db.execute(text("""
        SELECT season, week FROM sport_games
        WHERE sport = 'nba' AND game_type = 'REG' AND week IS NOT NULL AND start_utc > :now
        ORDER BY start_utc, id
        LIMIT 1
    """), {"now": now})
    row = upcoming.fetchone()
    if row is None:
        latest = await db.execute(text("""
            SELECT season, week FROM sport_games
            WHERE sport = 'nba' AND game_type = 'REG' AND week IS NOT NULL
            ORDER BY season DESC, week DESC
            LIMIT 1
        """))
        row = latest.fetchone()
    return (row[0], row[1]) if row is not None else None


async def get_week_modelled_lines(db: AsyncSession, season: int, week: int) -> list[NbaFreezeLine]:
    """Each linked full-game modelled prop on the week's `REG` games, at its last snapshot before tip-off (20g3).

    The game page's line rule (`_game_prop_lines`), so a frozen row is what the page showed.
    """
    rows = await db.execute(text(f"""
        SELECT DISTINCT ON (l.provider, l.provider_prop_id)
               l.id, l.game_id, g.game_date, g.start_utc, l.player_id, l.market, l.odds_type, l.line, l.fetched_at
        FROM sport_prop_lines l
        JOIN sport_games g ON g.sport = 'nba' AND g.id = l.game_id
        WHERE l.sport = 'nba' AND g.season = :season AND g.week = :week AND g.game_type = 'REG'
          AND l.player_id IS NOT NULL AND l.segment = 'full_game'
          AND (g.start_utc IS NULL OR l.fetched_at < g.start_utc) AND {NBA_MODELLED_MARKET_FILTER}
        ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC
    """), {"season": season, "week": week})
    return [
        NbaFreezeLine(
            line_id=row["id"], game_id=row["game_id"], game_date=row["game_date"], start_utc=row["start_utc"],
            player_id=row["player_id"], market=row["market"], odds_type=row["odds_type"], line=float(row["line"]),
            fetched_at=row["fetched_at"],
        )
        for row in rows.mappings()
    ]


async def get_frozen_gradeable_lines(db: AsyncSession, season: int) -> list[FrozenLine]:
    """The latest frozen pre-tip prediction of every linked PrizePicks prop on a completed `REG` game (20g3).

    Graded at the line it was frozen on, NFL's 27j rule, and settled against the
    player's box score. A game with no box-score rows at all is not loaded yet.
    """
    columns = ", ".join(f"s.{column}" for column in LINE_ONLY_COLUMNS)
    rows = await db.execute(text(f"""
        WITH frozen AS (
            SELECT DISTINCT ON (l.provider, l.provider_prop_id)
                   l.id, l.market, l.odds_type, l.line, l.player_id, l.game_id, g.week,
                   p.p_over, p.p_under, p.model_version, p.over_probability_version
            FROM sport_prop_predictions p
            JOIN sport_prop_lines l ON l.sport = 'nba' AND l.id = p.prop_line_id
            JOIN sport_games g ON g.sport = 'nba' AND g.id = l.game_id
            WHERE p.sport = 'nba' AND g.season = :season AND g.game_type = 'REG' AND g.week IS NOT NULL
              AND g.status = 'completed' AND l.player_id IS NOT NULL AND l.provider_prop_id IS NOT NULL
              AND l.segment = 'full_game' AND {NBA_MODELLED_MARKET_FILTER}
              AND l.fetched_at < g.start_utc AND p.generated_at < g.start_utc
            ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC, p.generated_at DESC, p.id DESC
        ),
        loaded_games AS (
            SELECT DISTINCT s.game_id FROM nba_player_game_stats s WHERE s.game_id IN (SELECT game_id FROM frozen)
        )
        SELECT frozen.*, s.player_id IS NOT NULL AS has_box_row, s.did_not_play, {columns},
               lg.game_id IS NOT NULL AS game_has_box_scores
        FROM frozen
        LEFT JOIN nba_player_game_stats s ON s.player_id = frozen.player_id AND s.game_id = frozen.game_id
        LEFT JOIN loaded_games lg ON lg.game_id = frozen.game_id
        ORDER BY frozen.week, frozen.id
    """), {"season": season})
    return [_frozen_line(row) for row in rows.mappings()]


def _frozen_line(row: RowMapping) -> FrozenLine:
    box_row = (
        {"did_not_play": row["did_not_play"], **{column: row[column] for column in LINE_ONLY_COLUMNS}}
        if row["has_box_row"] else None
    )
    return FrozenLine(
        line_id=row["id"], period=row["week"], player_id=row["player_id"], game_id=row["game_id"],
        market=row["market"], odds_type=row["odds_type"],
        outcome=settle_frozen(row["market"], float(row["line"]), box_row, bool(row["game_has_box_scores"])),
        p_over=row["p_over"], p_under=row["p_under"], model_version=row["model_version"],
        over_probability_version=row["over_probability_version"],
    )


async def get_finished_weeks(db: AsyncSession, season: int) -> set[int]:
    """Weeks whose `REG` games are all completed, postponed or canceled, with every completed one's box scores loaded.

    A postponed game is replayed under a new id (20b), so it never holds a week
    open; a completed game without box scores does, until the next load.
    """
    rows = await db.execute(text("""
        SELECT g.week FROM sport_games g
        WHERE g.sport = 'nba' AND g.season = :season AND g.game_type = 'REG' AND g.week IS NOT NULL
        GROUP BY g.week
        HAVING bool_and(g.status IN ('completed', 'postponed', 'canceled'))
           AND bool_and(g.status <> 'completed' OR EXISTS (SELECT 1 FROM nba_player_game_stats s WHERE s.game_id = g.id))
    """), {"season": season})
    return {row[0] for row in rows.fetchall()}


async def get_frozen_coverage(db: AsyncSession, season: int) -> dict[int, tuple[int, int]]:
    """Per week: (gradeable full-game modelled lines on completed `REG` games, how many have any frozen pre-tip row)."""
    rows = await db.execute(text(f"""
        WITH latest AS (
            SELECT DISTINCT ON (l.provider, l.provider_prop_id) l.provider, l.provider_prop_id, g.week
            FROM sport_prop_lines l
            JOIN sport_games g ON g.sport = 'nba' AND g.id = l.game_id
            WHERE l.sport = 'nba' AND g.season = :season AND g.game_type = 'REG' AND g.week IS NOT NULL
              AND g.status = 'completed' AND l.player_id IS NOT NULL AND l.provider_prop_id IS NOT NULL
              AND l.fetched_at < g.start_utc AND l.segment = 'full_game' AND {NBA_MODELLED_MARKET_FILTER}
            ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC
        )
        SELECT latest.week, COUNT(*),
               COUNT(*) FILTER (WHERE EXISTS (
                   SELECT 1 FROM sport_prop_lines fl
                   JOIN sport_prop_predictions p ON p.sport = 'nba' AND p.prop_line_id = fl.id
                   JOIN sport_games g ON g.sport = 'nba' AND g.id = fl.game_id
                   WHERE fl.sport = 'nba' AND fl.provider = latest.provider AND fl.provider_prop_id = latest.provider_prop_id
                     AND fl.fetched_at < g.start_utc AND p.generated_at < g.start_utc
               ))
        FROM latest
        GROUP BY latest.week ORDER BY latest.week
    """), {"season": season})
    return {week: (int(lines), int(frozen)) for week, lines, frozen in rows.fetchall()}


async def get_recent_box_scores(
    db: AsyncSession, player_ids: Sequence[int], before: dt.date, limit: int = 5,
) -> list[dict[str, object]]:
    """Each player's last `limit` played served games dated before `before`, newest first.

    DNP rows are skipped so every recent value is a game the player played;
    preseason never counts (20b).
    """
    columns = ", ".join(f"s.{column}" for column in LINE_ONLY_COLUMNS)
    rows = await db.execute(text(f"""
        SELECT player_id, game_date, opponent, did_not_play, {", ".join(LINE_ONLY_COLUMNS)}
        FROM (
            SELECT s.player_id, g.game_date, opp.team_code AS opponent, s.did_not_play, {columns},
                   ROW_NUMBER() OVER (PARTITION BY s.player_id ORDER BY g.game_date DESC, g.start_utc DESC NULLS LAST, g.id DESC) AS recency
            FROM nba_player_game_stats s
            JOIN sport_games g ON g.sport = 'nba' AND g.id = s.game_id
            LEFT JOIN sport_teams opp ON opp.sport = 'nba' AND opp.id = s.opponent_team_id
            WHERE s.player_id = ANY(:player_ids) AND {_SERVED_GAME_TYPES} AND g.game_date < :before
              AND NOT s.did_not_play
        ) ranked
        WHERE recency <= :limit
        ORDER BY player_id, game_date DESC
    """), {"player_ids": list(player_ids), "before": before, "limit": limit})
    return [dict(row) for row in rows.mappings()]


async def get_projection_history(db: AsyncSession, seasons: Sequence[int]) -> list[NbaHistoryRow]:
    """Every served box-score row of the seasons, oldest first, for the projection backtest.

    DNP rows are kept: the replay needs them to know a player sat. Preseason never counts (20b).
    """
    columns = ", ".join(f"s.{column}" for column in LINE_ONLY_COLUMNS)
    rows = await db.execute(text(f"""
        SELECT s.player_id, s.game_id, g.season, g.game_date, g.game_type, s.did_not_play, s.minutes, {columns}
        FROM nba_player_game_stats s
        JOIN sport_games g ON g.sport = 'nba' AND g.id = s.game_id
        WHERE g.season = ANY(:seasons) AND {_SERVED_GAME_TYPES}
        ORDER BY g.game_date, g.id, s.player_id
    """), {"seasons": list(seasons)})
    return [_history_row(row) for row in rows.mappings()]


async def get_prior_games(
    db: AsyncSession, player_ids: Sequence[int], before: dt.date, limit: int = REFERENCE_GAMES,
) -> dict[int, list[NbaHistoryRow]]:
    """Each player's last `limit` played served games dated before `before`, oldest first (20g2).

    Every stored season counts, the history depth 20g1's holdout was scored on.
    Box scores load the next morning, so a game earlier on the same Eastern date
    is never an input.
    """
    columns = ", ".join(f"s.{column}" for column in LINE_ONLY_COLUMNS)
    rows = await db.execute(text(f"""
        SELECT player_id, game_id, season, game_date, game_type, did_not_play, minutes, {", ".join(LINE_ONLY_COLUMNS)}
        FROM (
            SELECT s.player_id, s.game_id, g.season, g.game_date, g.game_type, s.did_not_play, s.minutes, {columns},
                   ROW_NUMBER() OVER (PARTITION BY s.player_id ORDER BY g.game_date DESC, g.start_utc DESC NULLS LAST, g.id DESC) AS recency
            FROM nba_player_game_stats s
            JOIN sport_games g ON g.sport = 'nba' AND g.id = s.game_id
            WHERE s.player_id = ANY(:player_ids) AND {_SERVED_GAME_TYPES} AND g.game_date < :before
              AND NOT s.did_not_play
        ) ranked
        WHERE recency <= :limit
        ORDER BY player_id, recency DESC
    """), {"player_ids": list(player_ids), "before": before, "limit": limit})
    prior: dict[int, list[NbaHistoryRow]] = {}
    for row in rows.mappings():
        prior.setdefault(row["player_id"], []).append(_history_row(row))
    return prior


def _history_row(row: RowMapping) -> NbaHistoryRow:
    return NbaHistoryRow(
        player_id=row["player_id"], game_id=row["game_id"], season=row["season"],
        game_date=row["game_date"], game_type=row["game_type"], did_not_play=row["did_not_play"],
        minutes=None if row["minutes"] is None else float(row["minutes"]),
        stats={"did_not_play": row["did_not_play"], **{column: row[column] for column in LINE_ONLY_COLUMNS}},
    )
