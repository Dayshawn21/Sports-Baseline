"""SQL access for normalized NFL teams, games, players, and weekly stats."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.core.nfl_baseline import SeasonGames, choose_baseline_season
from app.core.nfl_elo import NFL_ELO_MODEL_VERSION, NflEloGame, NflTeamEloRow
from app.core.nfl_game_line_clv import ClvGame, Market, OddsCandidate
from app.core.nfl_game_lines import NflGameLineGame, market_home_probability
from app.core.nfl_line_grading import STAT_COLUMN_BY_MARKET, GradeableLine, settle_line
from app.core.nfl_line_only import LINE_ONLY_COLUMNS
from app.core.nfl_best_line import Quote
from app.core.nfl_player import PlayerGameRow
from app.core.nfl_qb_change import Qb, QbGame, QbInjury
from app.core.prop_ranking_check import FrozenLine
from app.core.nfl_game_environment import NflEnvironmentGame
from app.core.nfl_projection_backtest import REPLAY_MARKETS_BY_POSITION, ReplayRow
from app.core.nfl_prop_market import SettledPropRow
from app.core.nfl_prop_odds import consensus
from app.core.nfl_td_backtest import NflSnapRow, NflWeeklyTdRow
from app.core.nfl_team_game_dvp import NflTeamGameTotals, league_averages, team_game_inputs
from app.core.nfl_team_stats import TeamGame
from app.ingest.nflverse import NflverseGame, NflversePlayerWeek
from app.ingest.nflverse_pbp import NflverseRedZoneSeason
from app.ingest.nflverse_depth_charts import NflverseDepthWeek
from app.ingest.nflverse_injuries import NflverseInjuryWeek
from app.ingest.nflverse_rosters import NflverseRosterWeek
from app.ingest.nflverse_snap_counts import NflverseSnapGame
from app.ingest.nflverse_team_efficiency import NflverseTeamEfficiency
from app.nfl.markets import NflLineOnlyMarket, NflPropMarket
from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class RedZoneWriteResult:
    rows_reset: int
    rows_applied: int
    # Counted plays whose player or game has no weekly-stat row; never created here.
    players_skipped: int
    games_skipped: int


@dataclass(frozen=True)
class RosterWriteResult:
    rows_deleted: int
    rows_inserted: int
    # Roster rows whose player (no stats yet) or team is not stored; never created here.
    rows_skipped: int
    unknown_teams: list[str]


@dataclass(frozen=True)
class SnapCountWriteResult:
    rows_deleted: int
    rows_inserted: int
    # Resolved rows whose player or game is not stored; never created here.
    rows_skipped_player: int
    rows_skipped_game: int
    unknown_teams: list[str]


@dataclass(frozen=True)
class TeamEfficiencyWriteResult:
    rows_deleted: int
    rows_inserted: int
    # Parsed games not stored in sport_games, or stored but not a final regular-season game.
    games_unknown: int
    games_not_final: int


@dataclass(frozen=True)
class PlayerWeekWriteResult:
    rows_deleted: int
    rows_inserted: int
    # Rows whose player (no stats yet) or team is not stored; never created here.
    rows_skipped: int
    unknown_teams: list[str]


async def insert_player_prop_odds_snapshot(
    db: AsyncSession,
    game_id: int,
    player_id: int | None,
    provider_player_name: str,
    provider_event_id: str,
    market: str,
    book: str,
    line: float | None,
    yes_odds: int,
    no_odds: int | None,
    market_prob: float,
    includes_margin: bool,
    raw_json: dict[str, object] | None,
) -> None:
    """Append one book's price for one player prop."""
    await db.execute(
        text("""
            INSERT INTO nfl_player_prop_odds (
                game_id, player_id, provider_player_name, provider_event_id, market, book,
                line, yes_odds, no_odds, market_prob, includes_margin, raw_json
            ) VALUES (
                :game_id, :player_id, :provider_player_name, :provider_event_id, :market, :book,
                :line, :yes_odds, :no_odds, :market_prob, :includes_margin, CAST(:raw_json AS jsonb)
            )
        """),
        {
            "game_id": game_id, "player_id": player_id,
            "provider_player_name": provider_player_name, "provider_event_id": provider_event_id,
            "market": market, "book": book, "line": line, "yes_odds": yes_odds, "no_odds": no_odds,
            "market_prob": market_prob, "includes_margin": includes_margin,
            "raw_json": json.dumps(raw_json) if raw_json is not None else None,
        },
    )


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
    """Append one accepted NFL game-market snapshot and return its id."""
    row = await db.execute(
        text("""
            INSERT INTO sport_game_odds (
                sport, game_id, book, market, line, first_side, second_side,
                first_odds, second_odds, first_market_prob, second_market_prob, raw_json, provider
            ) VALUES (
                'nfl', :game_id, :book, :market, :line, :first_side, :second_side,
                :first_odds, :second_odds, :first_market_prob, :second_market_prob,
                CAST(:raw_json AS jsonb), :provider
            )
            RETURNING id
        """),
        {
            "provider": provider,
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
        },
    )
    return row.scalar_one()


async def get_latest_game_odds(
    db: AsyncSession, game_id: int, book: str, market: str
) -> dict | None:
    """Return the most recent stored snapshot for one NFL game market."""
    row = await db.execute(
        text("""
            SELECT id, game_id, book, market, line, first_side, second_side,
                   first_odds, second_odds, first_market_prob, second_market_prob, fetched_at
            FROM sport_game_odds
            WHERE sport = 'nfl' AND provider = 'the_odds_api_us' AND game_id = :game_id AND book = :book AND market = :market
            ORDER BY fetched_at DESC, id DESC
            LIMIT 1
        """),
        {"game_id": game_id, "book": book, "market": market},
    )
    result = row.mappings().first()
    return dict(result) if result is not None else None


async def insert_game_weather_snapshot(
    db: AsyncSession,
    game_id: int,
    venue_type: str,
    provider: str,
    forecast_for: datetime | None,
    temperature_f: float | None,
    wind_mph: float | None,
    wind_gust_mph: float | None,
    precipitation_probability: float | None,
    raw_json: dict[str, object] | None,
) -> int:
    """Append one weather observation so later decisions retain its forecast time."""
    row = await db.execute(
        text("""
            INSERT INTO nfl_game_weather_snapshots (
                game_id, venue_type, provider, forecast_for, temperature_f,
                wind_mph, wind_gust_mph, precipitation_probability, raw_json
            ) VALUES (
                :game_id, :venue_type, :provider, :forecast_for, :temperature_f,
                :wind_mph, :wind_gust_mph, :precipitation_probability,
                CAST(:raw_json AS jsonb)
            )
            RETURNING id
        """),
        {
            "game_id": game_id, "venue_type": venue_type, "provider": provider,
            "forecast_for": forecast_for, "temperature_f": temperature_f, "wind_mph": wind_mph,
            "wind_gust_mph": wind_gust_mph, "precipitation_probability": precipitation_probability,
            "raw_json": json.dumps(raw_json) if raw_json is not None else None,
        },
    )
    return row.scalar_one()


async def upsert_team(db: AsyncSession, team_code: str, name: str | None = None) -> int:
    row = await db.execute(
        text("""
            INSERT INTO sport_teams (sport, team_code, name)
            VALUES ('nfl', :code, :name)
            ON CONFLICT (sport, team_code) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """),
        {"code": team_code, "name": name or team_code},
    )
    return row.scalar_one()


async def upsert_game(
    db: AsyncSession,
    game: NflverseGame,
    home_team_id: int,
    away_team_id: int,
) -> int:
    status = "completed" if game.home_score is not None and game.away_score is not None else "scheduled"
    row = await db.execute(
        text("""
            INSERT INTO sport_games (
                sport, source_game_id, season, week, game_type, game_date, start_utc,
                home_team_id, away_team_id, home_score, away_score, status,
                spread_line, total_line, home_moneyline, away_moneyline, roof,
                home_rest, away_rest, temp, wind
            ) VALUES (
                'nfl', :game_id, :season, :week, :game_type, :game_date, :start_utc,
                :home_team_id, :away_team_id, :home_score, :away_score, :status,
                :spread_line, :total_line, :home_moneyline, :away_moneyline, :roof,
                :home_rest, :away_rest, :temp, :wind
            )
            ON CONFLICT (sport, source_game_id) DO UPDATE SET
                game_date = EXCLUDED.game_date,
                start_utc = COALESCE(EXCLUDED.start_utc, sport_games.start_utc),
                home_score = EXCLUDED.home_score,
                away_score = EXCLUDED.away_score,
                status = EXCLUDED.status,
                spread_line = EXCLUDED.spread_line,
                total_line = EXCLUDED.total_line,
                home_moneyline = EXCLUDED.home_moneyline,
                away_moneyline = EXCLUDED.away_moneyline,
                roof = EXCLUDED.roof,
                home_rest = EXCLUDED.home_rest,
                away_rest = EXCLUDED.away_rest,
                temp = EXCLUDED.temp,
                wind = EXCLUDED.wind,
                updated_at = now()
            RETURNING id
        """),
        {
            "game_id": game.game_id, "season": game.season, "week": game.week,
            "game_type": game.game_type, "game_date": game.game_date, "start_utc": game.start_utc,
            "home_team_id": home_team_id, "away_team_id": away_team_id,
            "home_score": game.home_score, "away_score": game.away_score, "status": status,
            "spread_line": game.spread_line, "total_line": game.total_line,
            "home_moneyline": game.home_moneyline, "away_moneyline": game.away_moneyline,
            "roof": game.roof, "home_rest": game.home_rest, "away_rest": game.away_rest,
            "temp": game.temp, "wind": game.wind,
        },
    )
    return row.scalar_one()


async def upsert_player(
    db: AsyncSession,
    nflverse_id: str,
    name: str,
    position: str | None,
    team_id: int,
) -> int:
    row = await db.execute(
        text("""
            INSERT INTO sport_players (sport, source_player_id, name, position, team_id)
            VALUES ('nfl', :nflverse_id, :name, :position, :team_id)
            ON CONFLICT (sport, source_player_id) DO UPDATE SET
                name = EXCLUDED.name,
                position = COALESCE(EXCLUDED.position, sport_players.position),
                team_id = EXCLUDED.team_id,
                updated_at = now()
            RETURNING id
        """),
        {"nflverse_id": nflverse_id, "name": name, "position": position, "team_id": team_id},
    )
    return row.scalar_one()


async def upsert_weekly_stat(
    db: AsyncSession,
    stat: NflversePlayerWeek,
    player_id: int,
    game_id: int,
    team_id: int,
    opponent_team_id: int | None,
) -> None:
    await db.execute(
        text("""
            INSERT INTO nfl_player_weekly_stats (
                player_id, game_id, team_id, opponent_team_id, season, week,
                passing_yards, passing_attempts, passing_completions, rushing_yards,
                rushing_attempts, receiving_yards, receptions, targets, target_share,
                air_yards_share, wopr, touchdowns, fantasy_points,
                passing_tds, interceptions, fumbles_lost, two_point_conversions,
                return_tds, fumble_recovery_tds, prizepicks_fantasy_points, fg_made, pat_made
            ) VALUES (
                :player_id, :game_id, :team_id, :opponent_team_id, :season, :week,
                :passing_yards, :passing_attempts, :passing_completions, :rushing_yards,
                :rushing_attempts, :receiving_yards, :receptions, :targets, :target_share,
                :air_yards_share, :wopr, :touchdowns, :fantasy_points,
                :passing_tds, :interceptions, :fumbles_lost, :two_point_conversions,
                :return_tds, :fumble_recovery_tds, :prizepicks_fantasy_points, :fg_made, :pat_made
            )
            ON CONFLICT (player_id, game_id) DO UPDATE SET
                team_id = EXCLUDED.team_id,
                opponent_team_id = EXCLUDED.opponent_team_id,
                passing_yards = EXCLUDED.passing_yards,
                passing_attempts = EXCLUDED.passing_attempts,
                passing_completions = EXCLUDED.passing_completions,
                rushing_yards = EXCLUDED.rushing_yards,
                rushing_attempts = EXCLUDED.rushing_attempts,
                receiving_yards = EXCLUDED.receiving_yards,
                receptions = EXCLUDED.receptions,
                targets = EXCLUDED.targets,
                target_share = EXCLUDED.target_share,
                air_yards_share = EXCLUDED.air_yards_share,
                wopr = EXCLUDED.wopr,
                touchdowns = EXCLUDED.touchdowns,
                fantasy_points = EXCLUDED.fantasy_points,
                passing_tds = EXCLUDED.passing_tds,
                interceptions = EXCLUDED.interceptions,
                fumbles_lost = EXCLUDED.fumbles_lost,
                two_point_conversions = EXCLUDED.two_point_conversions,
                return_tds = EXCLUDED.return_tds,
                fumble_recovery_tds = EXCLUDED.fumble_recovery_tds,
                prizepicks_fantasy_points = EXCLUDED.prizepicks_fantasy_points,
                fg_made = EXCLUDED.fg_made,
                pat_made = EXCLUDED.pat_made,
                updated_at = now()
        """),
        {
            "player_id": player_id, "game_id": game_id, "team_id": team_id,
            "opponent_team_id": opponent_team_id, "season": stat.season, "week": stat.week,
            "passing_yards": stat.passing_yards, "passing_attempts": stat.passing_attempts,
            "passing_completions": stat.passing_completions, "rushing_yards": stat.rushing_yards,
            "rushing_attempts": stat.rushing_attempts, "receiving_yards": stat.receiving_yards,
            "receptions": stat.receptions, "targets": stat.targets,
            "target_share": stat.target_share, "air_yards_share": stat.air_yards_share,
            "wopr": stat.wopr, "touchdowns": stat.touchdowns,
            "fantasy_points": stat.fantasy_points,
            "passing_tds": stat.passing_tds, "interceptions": stat.interceptions,
            "fumbles_lost": stat.fumbles_lost, "two_point_conversions": stat.two_point_conversions,
            "return_tds": stat.return_tds, "fumble_recovery_tds": stat.fumble_recovery_tds,
            "prizepicks_fantasy_points": stat.prizepicks_fantasy_points,
            "fg_made": stat.fg_made, "pat_made": stat.pat_made,
        },
    )


async def write_red_zone_usage(db: AsyncSession, usage: NflverseRedZoneSeason) -> RedZoneWriteResult:
    """Zero every weekly row in the file's games, then apply the counted plays.

    Zeroing first is what separates "no red-zone plays" (0) from "play-by-play
    not loaded" (NULL), and makes a rerun converge on the same values.
    """
    game_keys = sorted(usage.game_ids)
    known = await db.execute(
        text("SELECT source_game_id FROM sport_games WHERE sport = 'nfl' AND source_game_id = ANY(:game_keys)"),
        {"game_keys": game_keys},
    )
    known_keys = {row[0] for row in known.fetchall()}
    reset = await db.execute(
        text("""
            UPDATE nfl_player_weekly_stats s
            SET rz20_carries = 0, rz20_targets = 0, rz5_carries = 0, rz5_targets = 0,
                end_zone_targets = 0, punts = 0, updated_at = now()
            FROM sport_games g
            WHERE g.sport = 'nfl' AND g.id = s.game_id AND g.source_game_id = ANY(:game_keys)
            RETURNING s.id
        """),
        {"game_keys": game_keys},
    )
    applied = await db.execute(
        text("""
            UPDATE nfl_player_weekly_stats s
            SET rz20_carries = v.rz20_carries, rz20_targets = v.rz20_targets,
                rz5_carries = v.rz5_carries, rz5_targets = v.rz5_targets,
                end_zone_targets = v.end_zone_targets, punts = v.punts
            FROM unnest(
                CAST(:player_keys AS text[]), CAST(:game_keys AS text[]),
                CAST(:rz20_carries AS smallint[]), CAST(:rz20_targets AS smallint[]),
                CAST(:rz5_carries AS smallint[]), CAST(:rz5_targets AS smallint[]),
                CAST(:end_zone_targets AS smallint[]), CAST(:punts AS smallint[])
            ) AS v(player_key, game_key, rz20_carries, rz20_targets, rz5_carries, rz5_targets, end_zone_targets, punts)
            JOIN sport_players p ON p.sport = 'nfl' AND p.source_player_id = v.player_key
            JOIN sport_games g ON g.sport = 'nfl' AND g.source_game_id = v.game_key
            WHERE s.player_id = p.id AND s.game_id = g.id
            RETURNING s.id
        """),
        {
            "player_keys": [item.player_id for item in usage.games],
            "game_keys": [item.game_id for item in usage.games],
            "rz20_carries": [item.rz20_carries for item in usage.games],
            "rz20_targets": [item.rz20_targets for item in usage.games],
            "rz5_carries": [item.rz5_carries for item in usage.games],
            "rz5_targets": [item.rz5_targets for item in usage.games],
            "end_zone_targets": [item.end_zone_targets for item in usage.games],
            "punts": [item.punts for item in usage.games],
        },
    )
    applied_count = len(applied.fetchall())
    return RedZoneWriteResult(
        rows_reset=len(reset.fetchall()),
        rows_applied=applied_count,
        players_skipped=len(usage.games) - applied_count,
        games_skipped=len(usage.game_ids - known_keys),
    )


async def replace_weekly_rosters(db: AsyncSession, season: int, rosters: list[NflverseRosterWeek]) -> RosterWriteResult:
    """Replace the stored rows for every season-week present in the parsed file.

    Replacing rather than upserting drops a player who left a week's roster in a
    later republish; players and teams are matched, never created.
    """
    weeks = sorted({item.week for item in rosters})
    deleted = await db.execute(
        text("DELETE FROM nfl_player_weekly_rosters WHERE season = :season AND week = ANY(:weeks) RETURNING id"),
        {"season": season, "weeks": weeks},
    )
    inserted = await db.execute(
        text("""
            INSERT INTO nfl_player_weekly_rosters (player_id, season, week, team_id, status)
            SELECT p.id, :season, v.week, t.id, v.status
            FROM unnest(
                CAST(:player_keys AS text[]), CAST(:weeks AS smallint[]),
                CAST(:teams AS text[]), CAST(:statuses AS text[])
            ) AS v(player_key, week, team, status)
            JOIN sport_players p ON p.sport = 'nfl' AND p.source_player_id = v.player_key
            JOIN sport_teams t ON t.sport = 'nfl' AND t.team_code = v.team
            RETURNING id
        """),
        {
            "season": season,
            "player_keys": [item.player_id for item in rosters],
            "weeks": [item.week for item in rosters],
            "teams": [item.team for item in rosters],
            "statuses": [item.status for item in rosters],
        },
    )
    known_teams = await db.execute(
        text("SELECT team_code FROM sport_teams WHERE sport = 'nfl' AND team_code = ANY(:teams)"),
        {"teams": sorted({item.team for item in rosters})},
    )
    inserted_count = len(inserted.fetchall())
    return RosterWriteResult(
        rows_deleted=len(deleted.fetchall()),
        rows_inserted=inserted_count,
        rows_skipped=len(rosters) - inserted_count,
        unknown_teams=sorted({item.team for item in rosters} - {row[0] for row in known_teams.fetchall()}),
    )


async def _replace_player_weeks(
    db: AsyncSession,
    table: str,
    season: int,
    keys: list[tuple[str, int, str]],
    columns: dict[str, tuple[str, list[object]]],
) -> PlayerWeekWriteResult:
    """Replace `table`'s rows for the season-weeks in `keys`, matching players and teams.

    `keys` are (gsis id, week, team code) per row; `columns` maps each extra column
    to its SQL array type and values. Table and column names are fixed by callers
    in this module, never user input.
    """
    weeks = sorted({week for _, week, _ in keys})
    deleted = await db.execute(
        text(f"DELETE FROM {table} WHERE season = :season AND week = ANY(:weeks) RETURNING id"),
        {"season": season, "weeks": weeks},
    )
    names = list(columns)
    unnest = ", ".join(f"CAST(:{name} AS {sql_type}[])" for name, (sql_type, _) in columns.items())
    inserted = await db.execute(
        text(f"""
            INSERT INTO {table} (player_id, season, week, team_id, {", ".join(names)})
            SELECT p.id, :season, v.week, t.id, {", ".join(f"v.{name}" for name in names)}
            FROM unnest(
                CAST(:player_keys AS text[]), CAST(:row_weeks AS smallint[]), CAST(:teams AS text[]), {unnest}
            ) AS v(player_key, week, team, {", ".join(names)})
            JOIN sport_players p ON p.sport = 'nfl' AND p.source_player_id = v.player_key
            JOIN sport_teams t ON t.sport = 'nfl' AND t.team_code = v.team
            RETURNING id
        """),
        {
            "season": season,
            "player_keys": [key for key, _, _ in keys],
            "row_weeks": [week for _, week, _ in keys],
            "teams": [team for _, _, team in keys],
            **{name: values for name, (_, values) in columns.items()},
        },
    )
    known_teams = await db.execute(
        text("SELECT team_code FROM sport_teams WHERE sport = 'nfl' AND team_code = ANY(:teams)"),
        {"teams": sorted({team for _, _, team in keys})},
    )
    inserted_count = len(inserted.fetchall())
    return PlayerWeekWriteResult(
        rows_deleted=len(deleted.fetchall()),
        rows_inserted=inserted_count,
        rows_skipped=len(keys) - inserted_count,
        unknown_teams=sorted({team for _, _, team in keys} - {row[0] for row in known_teams.fetchall()}),
    )


async def replace_weekly_injuries(
    db: AsyncSession, season: int, injuries: list[NflverseInjuryWeek],
) -> PlayerWeekWriteResult:
    return await _replace_player_weeks(
        db, "nfl_player_injuries", season,
        [(item.player_id, item.week, item.team) for item in injuries],
        {
            "report_status": ("text", [item.report_status for item in injuries]),
            "practice_status": ("text", [item.practice_status for item in injuries]),
            "primary_injury": ("text", [item.primary_injury for item in injuries]),
        },
    )


async def replace_weekly_depth_charts(
    db: AsyncSession, season: int, depth: list[NflverseDepthWeek],
) -> PlayerWeekWriteResult:
    return await _replace_player_weeks(
        db, "nfl_player_depth_charts", season,
        [(item.player_id, item.week, item.team) for item in depth],
        {
            "position": ("text", [item.position for item in depth]),
            "depth_rank": ("smallint", [item.depth_rank for item in depth]),
            "snapshot_at": ("timestamptz", [item.snapshot_at for item in depth]),
        },
    )


async def replace_snap_counts(
    db: AsyncSession, game_ids: frozenset[str], rows: list[tuple[str, NflverseSnapGame]],
) -> SnapCountWriteResult:
    """Replace the stored snap rows for every game in the file, matching players, games, and teams.

    Replacing by game rather than upserting drops a row that a republished file no
    longer lists. Season and week come from the stored game, not the file.
    """
    game_keys = sorted(game_ids)
    deleted = await db.execute(
        text("""
            DELETE FROM nfl_player_snap_counts s
            USING sport_games g
            WHERE g.sport = 'nfl' AND g.id = s.game_id AND g.source_game_id = ANY(:game_keys)
            RETURNING s.id
        """),
        {"game_keys": game_keys},
    )
    inserted = await db.execute(
        text("""
            INSERT INTO nfl_player_snap_counts (player_id, game_id, season, week, team_id, offense_snaps, offense_pct)
            SELECT p.id, g.id, g.season, g.week, t.id, v.offense_snaps, v.offense_pct
            FROM unnest(
                CAST(:player_keys AS text[]), CAST(:row_games AS text[]), CAST(:teams AS text[]),
                CAST(:offense_snaps AS smallint[]), CAST(:offense_pct AS real[])
            ) AS v(player_key, game_key, team, offense_snaps, offense_pct)
            JOIN sport_players p ON p.sport = 'nfl' AND p.source_player_id = v.player_key
            JOIN sport_games g ON g.sport = 'nfl' AND g.source_game_id = v.game_key
            JOIN sport_teams t ON t.sport = 'nfl' AND t.team_code = v.team
            RETURNING id
        """),
        {
            "player_keys": [gsis_id for gsis_id, _ in rows],
            "row_games": [game.game_id for _, game in rows],
            "teams": [game.team for _, game in rows],
            "offense_snaps": [game.offense_snaps for _, game in rows],
            "offense_pct": [game.offense_pct for _, game in rows],
        },
    )
    known_games = await db.execute(
        text("SELECT source_game_id FROM sport_games WHERE sport = 'nfl' AND source_game_id = ANY(:game_keys)"),
        {"game_keys": game_keys},
    )
    teams = sorted({game.team for _, game in rows})
    known_teams = await db.execute(
        text("SELECT team_code FROM sport_teams WHERE sport = 'nfl' AND team_code = ANY(:teams)"), {"teams": teams},
    )
    stored_games = {row[0] for row in known_games.fetchall()}
    inserted_count = len(inserted.fetchall())
    game_skipped = sum(game.game_id not in stored_games for _, game in rows)
    return SnapCountWriteResult(
        rows_deleted=len(deleted.fetchall()),
        rows_inserted=inserted_count,
        rows_skipped_player=len(rows) - inserted_count - game_skipped,
        rows_skipped_game=game_skipped,
        unknown_teams=sorted(set(teams) - {row[0] for row in known_teams.fetchall()}),
    )


async def get_elo_games(db: AsyncSession) -> list[NflEloGame]:
    """Every regular-season game in the order played, unfinished games included.

    Game date, not week, is the order: a postponed game keeps its original week.
    """
    rows = await db.execute(text("""
        SELECT g.source_game_id, g.season, g.week, h.team_code, a.team_code, g.home_score, g.away_score
        FROM sport_games g
        JOIN sport_teams h ON h.sport = 'nfl' AND h.id = g.home_team_id
        JOIN sport_teams a ON a.sport = 'nfl' AND a.id = g.away_team_id
        WHERE g.sport = 'nfl' AND g.game_type = 'REG'
        ORDER BY g.game_date, g.start_utc NULLS LAST, g.source_game_id
    """))
    return [NflEloGame(*row) for row in rows.fetchall()]


async def get_game_line_games(db: AsyncSession) -> list[NflGameLineGame]:
    """`get_elo_games` plus each game's NFLverse closing lines and context, in the same order."""
    rows = await db.execute(text("""
        SELECT g.source_game_id, g.season, g.week, h.team_code, a.team_code, g.home_score, g.away_score,
               g.spread_line::double precision, g.total_line::double precision,
               g.home_moneyline, g.away_moneyline,
               g.roof, g.temp, g.wind, g.home_rest, g.away_rest
        FROM sport_games g
        JOIN sport_teams h ON h.sport = 'nfl' AND h.id = g.home_team_id
        JOIN sport_teams a ON a.sport = 'nfl' AND a.id = g.away_team_id
        WHERE g.sport = 'nfl' AND g.game_type = 'REG'
        ORDER BY g.game_date, g.start_utc NULLS LAST, g.source_game_id
    """))
    return [NflGameLineGame(NflEloGame(*row[:7]), *row[7:]) for row in rows.fetchall()]


async def get_game_line_clv_games(db: AsyncSession, season: int) -> list[ClvGame]:
    """Every regular-season game of `season` with its closing lines and pre-kickoff spread and total rows."""
    games = await db.execute(text("""
        WITH week_last AS (
            SELECT week, MAX(start_utc) last_kickoff FROM sport_games
            WHERE sport = 'nfl' AND season = :season AND game_type = 'REG' GROUP BY week
        )
        SELECT g.id, g.source_game_id, g.week, g.start_utc, g.status = 'completed', g.home_score, g.away_score,
               g.spread_line::double precision, g.total_line::double precision, prev.last_kickoff
        FROM sport_games g
        LEFT JOIN week_last prev ON prev.week = g.week - 1
        WHERE g.sport = 'nfl' AND g.season = :season AND g.game_type = 'REG'
        ORDER BY g.week, g.start_utc NULLS LAST, g.source_game_id
    """), {"season": season})
    odds = await db.execute(text("""
        SELECT o.game_id, o.market, o.id, o.book, o.line::double precision, o.fetched_at
        FROM sport_game_odds o
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = o.game_id
        WHERE o.sport = 'nfl' AND o.provider = 'the_odds_api_us' AND g.season = :season AND g.game_type = 'REG' AND o.market IN ('spread', 'total')
          AND o.line IS NOT NULL AND o.fetched_at < g.start_utc
        ORDER BY o.game_id, o.market, o.fetched_at, o.id
    """), {"season": season})
    candidates: dict[int, dict[Market, list[OddsCandidate]]] = {}
    for game_id, market, odds_id, book, line, fetched_at in odds.fetchall():
        candidates.setdefault(game_id, {"spread": [], "total": []})[market].append(
            OddsCandidate(odds_id, book, line, fetched_at)
        )
    return [
        ClvGame(*row[1:], candidates=candidates.get(row[0], {"spread": [], "total": []}))
        for row in games.fetchall()
    ]


async def replace_team_elo(db: AsyncSession, rows: list[NflTeamEloRow], model_version: str) -> tuple[int, int]:
    """Replace every rating for one model version, as (deleted, inserted).

    The whole history is recomputed each run, so replacing beats upserting: a
    game dropped from the schedule cannot leave a stale rating behind.
    """
    deleted = await db.execute(
        text("DELETE FROM nfl_team_elo WHERE model_version = :model_version RETURNING id"),
        {"model_version": model_version},
    )
    inserted = await db.execute(
        text("""
            INSERT INTO nfl_team_elo (team_id, game_id, season, week, is_home, elo_pre, elo_post, model_version)
            SELECT t.id, g.id, g.season, g.week, v.is_home, v.elo_pre, v.elo_post, :model_version
            FROM unnest(
                CAST(:teams AS text[]), CAST(:game_keys AS text[]), CAST(:is_home AS boolean[]),
                CAST(:elo_pre AS double precision[]), CAST(:elo_post AS double precision[])
            ) AS v(team, game_key, is_home, elo_pre, elo_post)
            JOIN sport_teams t ON t.sport = 'nfl' AND t.team_code = v.team
            JOIN sport_games g ON g.sport = 'nfl' AND g.source_game_id = v.game_key
            RETURNING id
        """),
        {
            "model_version": model_version,
            "teams": [row.team_code for row in rows],
            "game_keys": [row.game_key for row in rows],
            "is_home": [row.is_home for row in rows],
            "elo_pre": [row.elo_pre for row in rows],
            "elo_post": [row.elo_post for row in rows],
        },
    )
    return len(deleted.fetchall()), len(inserted.fetchall())


async def get_team_efficiency(db: AsyncSession) -> dict[tuple[str, bool], NflverseTeamEfficiency]:
    """Every stored regular-season offense row, keyed by (game key, is home)."""
    rows = await db.execute(text("""
        SELECT g.source_game_id, e.is_home, e.plays, e.epa, e.successes
        FROM nfl_team_game_efficiency e
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = e.game_id
        WHERE g.game_type = 'REG'
    """))
    return {(row[0], row[1]): NflverseTeamEfficiency(*row) for row in rows.fetchall()}


async def replace_team_efficiency(
    db: AsyncSession, rows: list[NflverseTeamEfficiency],
) -> TeamEfficiencyWriteResult:
    """Replace the efficiency rows of every game in the parsed file.

    The team comes from the game's home or away side, never from a team code.
    Only final regular-season games are written: a row for a game still in
    progress would feed partial plays into the ratings.
    """
    game_keys = sorted({row.game_id for row in rows})
    known = await db.execute(
        text("""
            SELECT source_game_id,
                   game_type = 'REG' AND home_score IS NOT NULL AND away_score IS NOT NULL
            FROM sport_games WHERE sport = 'nfl' AND source_game_id = ANY(:game_keys)
        """),
        {"game_keys": game_keys},
    )
    writable = dict(known.fetchall())
    deleted = await db.execute(
        text("""
            DELETE FROM nfl_team_game_efficiency e
            USING sport_games g
            WHERE g.sport = 'nfl' AND g.id = e.game_id AND g.source_game_id = ANY(:game_keys)
            RETURNING e.id
        """),
        {"game_keys": game_keys},
    )
    inserted = await db.execute(
        text("""
            INSERT INTO nfl_team_game_efficiency (game_id, team_id, season, week, is_home, plays, epa, successes)
            SELECT g.id, CASE WHEN v.is_home THEN g.home_team_id ELSE g.away_team_id END,
                   g.season, g.week, v.is_home, v.plays, v.epa, v.successes
            FROM unnest(
                CAST(:game_keys AS text[]), CAST(:is_home AS boolean[]), CAST(:plays AS smallint[]),
                CAST(:epa AS double precision[]), CAST(:successes AS smallint[])
            ) AS v(game_key, is_home, plays, epa, successes)
            JOIN sport_games g ON g.sport = 'nfl' AND g.source_game_id = v.game_key
            WHERE g.game_type = 'REG' AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL
            RETURNING id
        """),
        {
            "game_keys": [row.game_id for row in rows],
            "is_home": [row.is_home for row in rows],
            "plays": [row.plays for row in rows],
            "epa": [row.epa for row in rows],
            "successes": [row.successes for row in rows],
        },
    )
    return TeamEfficiencyWriteResult(
        rows_deleted=len(deleted.fetchall()),
        rows_inserted=len(inserted.fetchall()),
        games_unknown=len(set(game_keys) - writable.keys()),
        games_not_final=sum(not is_final for is_final in writable.values()),
    )


async def get_team_schedule(db: AsyncSession, season: int) -> dict[str, list[tuple[int, date]]]:
    """Each team's regular-season (week, game date) pairs, in date order."""
    rows = await db.execute(
        text("""
            SELECT t.team_code, g.week, g.game_date
            FROM sport_games g
            JOIN sport_teams t ON t.sport = 'nfl' AND t.id IN (g.home_team_id, g.away_team_id)
            WHERE g.sport = 'nfl' AND g.season = :season AND g.game_type = 'REG'
            ORDER BY t.team_code, g.game_date
        """),
        {"season": season},
    )
    schedule: dict[str, list[tuple[int, date]]] = {}
    for team_code, week, game_date in rows.fetchall():
        schedule.setdefault(team_code, []).append((week, game_date))
    return schedule


async def get_weekly_td_rows(db: AsyncSession) -> list[NflWeeklyTdRow]:
    """Every regular-season player-game with TD, role, and historical game-line inputs."""
    rows = await db.execute(text("""
        SELECT s.player_id, p.position, s.season, s.week, s.touchdowns,
               s.rz20_carries, s.rz20_targets, s.rz5_carries, s.rz5_targets,
               s.end_zone_targets,
               g.total_line::double precision, g.spread_line::double precision,
               g.home_moneyline, g.away_moneyline,
               s.team_id = g.home_team_id
        FROM nfl_player_weekly_stats s
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
        JOIN sport_players p ON p.sport = 'nfl' AND p.id = s.player_id
        WHERE g.game_type = 'REG'
    """))
    return [NflWeeklyTdRow(*row) for row in rows.fetchall()]


async def get_snap_rows(db: AsyncSession) -> list[NflSnapRow]:
    """Every regular-season snap row, including games with no weekly-stat row, for the backtest."""
    rows = await db.execute(text("""
        SELECT s.player_id, p.position, s.season, s.week, s.offense_pct
        FROM nfl_player_snap_counts s
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
        JOIN sport_players p ON p.sport = 'nfl' AND p.id = s.player_id
        WHERE g.game_type = 'REG'
    """))
    return [NflSnapRow(*row) for row in rows.fetchall()]


async def get_player_candidates(db: AsyncSession) -> list[tuple[int, str, str | None, str | None]]:
    """Every player with the current team and position resolution matches against.

    The team is the latest roster team, so the tiebreak compares a provider's
    current team against the player's current team rather than import order.
    """
    rows = await db.execute(
        text(f"""
            WITH {_player_teams_cte(week_bound=False)}
            SELECT p.id, p.name, t.team_code, p.position
            FROM sport_players p
            JOIN player_teams pt ON pt.player_id = p.id
            LEFT JOIN sport_teams t ON t.sport = 'nfl' AND t.id = pt.team_id
            WHERE p.sport = 'nfl'
        """)
    )
    return [(row[0], row[1], row[2], row[3]) for row in rows.fetchall()]


async def get_upcoming_games(db: AsyncSession, days_ahead: int) -> list[dict]:
    """Scheduled regular-season games eligible for a bounded odds refresh."""
    rows = await db.execute(
        text("""
            SELECT g.id, g.game_date, g.start_utc, home.team_code, away.team_code
            FROM sport_games g
            JOIN sport_teams home ON home.sport = 'nfl' AND home.id = g.home_team_id
            JOIN sport_teams away ON away.sport = 'nfl' AND away.id = g.away_team_id
            WHERE g.sport = 'nfl' AND g.game_type = 'REG' AND g.status = 'scheduled'
              AND g.game_date BETWEEN CURRENT_DATE - 1 AND CURRENT_DATE + :days_ahead
            ORDER BY g.game_date, g.id
        """),
        {"days_ahead": days_ahead},
    )
    return [
        {"game_id": row[0], "game_date": row[1], "start_utc": row[2], "home_team": row[3], "away_team": row[4]}
        for row in rows.fetchall()
    ]


async def get_upcoming_games_needing_weather(db: AsyncSession, days_ahead: int) -> list[dict]:
    """Upcoming games without a weather snapshot fetched in the last three hours."""
    rows = await db.execute(
        text("""
            SELECT g.id, g.game_date, g.start_utc, home.team_code, away.team_code
            FROM sport_games g
            JOIN sport_teams home ON home.sport = 'nfl' AND home.id = g.home_team_id
            JOIN sport_teams away ON away.sport = 'nfl' AND away.id = g.away_team_id
            WHERE g.sport = 'nfl' AND g.game_type = 'REG' AND g.status = 'scheduled'
              AND g.game_date BETWEEN CURRENT_DATE - 1 AND CURRENT_DATE + :days_ahead
              AND NOT EXISTS (
                  SELECT 1 FROM nfl_game_weather_snapshots w
                  WHERE w.game_id = g.id AND w.fetched_at >= now() - INTERVAL '3 hours'
              )
            ORDER BY g.game_date, g.id
        """),
        {"days_ahead": days_ahead},
    )
    return [
        {"game_id": row[0], "game_date": row[1], "start_utc": row[2], "home_team": row[3], "away_team": row[4]}
        for row in rows.fetchall()
    ]


async def upsert_player_alias(
    db: AsyncSession,
    alias_name: str,
    alias_name_norm: str,
    player_id: int,
    source: str = "manual",
) -> None:
    await db.execute(
        text("""
            INSERT INTO sport_player_aliases (sport, player_id, alias_name, alias_name_norm, source)
            VALUES ('nfl', :player_id, :alias_name, :alias_norm, :source)
            ON CONFLICT (sport, alias_name_norm) DO UPDATE SET
                player_id = EXCLUDED.player_id,
                alias_name = EXCLUDED.alias_name,
                source = EXCLUDED.source
        """),
        {"player_id": player_id, "alias_name": alias_name,
         "alias_norm": alias_name_norm, "source": source},
    )


async def get_games(db: AsyncSession, season: int, week: int) -> list[dict]:
    rows = await db.execute(
        text("""
            SELECT g.id, g.season, g.week, g.game_date, g.start_utc,
                   away.team_code, home.team_code, g.status
            FROM sport_games g
            JOIN sport_teams home ON home.sport = 'nfl' AND home.id = g.home_team_id
            JOIN sport_teams away ON away.sport = 'nfl' AND away.id = g.away_team_id
            WHERE g.sport = 'nfl' AND g.season = :season AND g.week = :week AND g.game_type = 'REG'
            ORDER BY g.start_utc NULLS LAST, g.id
        """),
        {"season": season, "week": week},
    )
    return [
        {"game_id": r[0], "season": r[1], "week": r[2], "game_date": r[3], "start_utc": r[4],
         "away_team": r[5], "home_team": r[6], "status": r[7]}
        for r in rows.fetchall()
    ]


CURRENT_WEEK_GRACE = timedelta(hours=12)


async def get_current_week(db: AsyncSession, now: datetime) -> tuple[int, int] | None:
    """(season, week) of the next regular-season game, or the latest loaded week.

    A game stays current for 12 hours after kickoff, so the week does not roll
    over while its Monday night game is still being played.
    """
    upcoming = await db.execute(
        text("""
            SELECT season, week FROM sport_games
            WHERE sport = 'nfl' AND game_type = 'REG' AND start_utc >= :cutoff
            ORDER BY start_utc, id
            LIMIT 1
        """),
        {"cutoff": now - CURRENT_WEEK_GRACE},
    )
    row = upcoming.fetchone()
    if row is None:
        latest = await db.execute(
            text("""
                SELECT season, week FROM sport_games
                WHERE sport = 'nfl' AND game_type = 'REG'
                ORDER BY season DESC, week DESC
                LIMIT 1
            """),
            {},
        )
        row = latest.fetchone()
    return (row[0], row[1]) if row is not None else None


async def get_historical_player_baselines(db: AsyncSession, season: int, week: int) -> list[dict]:
    """Return upcoming-game players with transparent pre-week career-season averages."""
    rows = await db.execute(
        text(f"""
            WITH {_player_teams_cte()},
            slate_players AS (
                SELECT g.id AS game_id, p.id AS player_id, p.name AS player_name, p.position
                FROM sport_games g
                JOIN player_teams pt ON pt.team_id IN (g.home_team_id, g.away_team_id)
                JOIN sport_players p ON p.sport = 'nfl' AND p.id = pt.player_id
                WHERE g.sport = 'nfl' AND g.season = :season AND g.week = :week AND g.game_type = 'REG'
            )
            SELECT sp.game_id, sp.player_id, sp.player_name, sp.position,
                   COUNT(s.id),
                   COALESCE(AVG(s.passing_yards), 0), COALESCE(AVG(s.passing_attempts), 0),
                   COALESCE(AVG(s.passing_completions), 0), COALESCE(AVG(s.rushing_yards), 0),
                   COALESCE(AVG(s.rushing_attempts), 0), COALESCE(AVG(s.receiving_yards), 0),
                   COALESCE(AVG(s.receptions), 0), COALESCE(AVG(s.touchdowns), 0), AVG(s.fantasy_points)
            FROM slate_players sp
            LEFT JOIN nfl_player_weekly_stats s ON s.player_id = sp.player_id
                AND (s.season < :season OR (s.season = :season AND s.week < :week))
            GROUP BY sp.game_id, sp.player_id, sp.player_name, sp.position
            HAVING COUNT(s.id) > 0
            ORDER BY sp.game_id, sp.player_name
        """),
        {"season": season, "week": week},
    )
    baselines = [
        {
            "game_id": r[0], "player_id": r[1], "player_name": r[2], "position": r[3],
            "averages": {
                "games": r[4], "passing_yards": float(r[5]), "passing_attempts": float(r[6]),
                "passing_completions": float(r[7]), "rushing_yards": float(r[8]),
                "rushing_attempts": float(r[9]), "receiving_yards": float(r[10]),
                "receptions": float(r[11]), "touchdowns": float(r[12]),
                "fantasy_points": float(r[13]) if r[13] is not None else None,
            },
        }
        for r in rows.fetchall()
    ]
    td_seasons, position_rates = await _td_history(db, season, week, sorted({b["player_id"] for b in baselines}))
    for baseline in baselines:
        seasons = td_seasons.get(baseline["player_id"], [])
        choice = choose_baseline_season(season, [SeasonGames(item["season"], item["games"]) for item in seasons])
        baseline["td_seasons"] = seasons
        baseline["position_td_rate"] = position_rates.get((baseline["position"], choice.season), 0.0)
        baseline["baseline_season"] = choice.season
    await _attach_snap_history(db, season, week, baselines)
    return baselines


async def _attach_snap_history(db: AsyncSession, season: int, week: int, rows: list[dict]) -> None:
    """Add pre-week `snap_seasons` and `position_snap_share` to each row, in place.

    Same cutoff as the TD history, and the position share comes from the row's
    `baseline_season`, the season its position TD rate uses, as in the backtest.
    Snap-only games (no weekly-stat row) count, so a blocking role is evidence.
    """
    player_ids = sorted({row["player_id"] for row in rows})
    if not player_ids:
        return
    params = {"player_ids": player_ids, "season": season, "week": week}
    player_rows = await db.execute(text("""
        SELECT player_id, season, COUNT(offense_pct), AVG(offense_pct)
        FROM nfl_player_snap_counts
        WHERE player_id = ANY(:player_ids) AND offense_pct IS NOT NULL
          AND (season < :season OR (season = :season AND week < :week))
        GROUP BY player_id, season ORDER BY player_id, season
    """), params)
    snap_seasons: dict[int, list[dict]] = {}
    for player_id, year, games, share in player_rows.fetchall():
        snap_seasons.setdefault(player_id, []).append({"season": year, "games": games, "share": float(share)})
    position_rows = await db.execute(text("""
        SELECT p.position, s.season, AVG(s.offense_pct)
        FROM nfl_player_snap_counts s JOIN sport_players p ON p.sport = 'nfl' AND p.id = s.player_id
        WHERE s.offense_pct IS NOT NULL AND (s.season < :season OR (s.season = :season AND s.week < :week))
        GROUP BY p.position, s.season
    """), params)
    position_shares = {(position, year): float(share) for position, year, share in position_rows.fetchall()}
    for row in rows:
        row["snap_seasons"] = snap_seasons.get(row["player_id"], [])
        row["position_snap_share"] = position_shares.get((row["position"], row["baseline_season"]), 0.0)


async def _td_history(
    db: AsyncSession, season: int, week: int, player_ids: list[int],
) -> tuple[dict[int, list[dict]], dict[tuple[str | None, int], float]]:
    """Pre-week regular-season TD history per player and TD rate per position-season.

    Same cutoff and filters as the slate's baselines, so /projections and the
    slate compute the same anytime-TD baseline for a player.
    """
    if not player_ids:
        return {}, {}
    player_rows = await db.execute(text("""
        SELECT s.player_id, s.season, COUNT(*), AVG(s.touchdowns)
        FROM nfl_player_weekly_stats s JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
        WHERE g.game_type = 'REG' AND s.player_id = ANY(:player_ids)
          AND (s.season < :season OR (s.season = :season AND s.week < :week))
        GROUP BY s.player_id, s.season ORDER BY s.player_id, s.season
    """), {"player_ids": player_ids, "season": season, "week": week})
    td_seasons: dict[int, list[dict]] = {}
    for player_id, year, games, touchdowns in player_rows.fetchall():
        td_seasons.setdefault(player_id, []).append({"season": year, "games": games, "touchdowns": float(touchdowns or 0)})
    position_rows = await db.execute(text("""
        SELECT p.position, s.season, AVG(s.touchdowns)
        FROM nfl_player_weekly_stats s JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
        JOIN sport_players p ON p.sport = 'nfl' AND p.id = s.player_id
        WHERE g.game_type = 'REG' AND (s.season < :season OR (s.season = :season AND s.week < :week))
        GROUP BY p.position, s.season
    """), {"season": season, "week": week})
    return td_seasons, {(position, year): float(rate or 0) for position, year, rate in position_rows.fetchall()}


def _player_teams_cte(week_bound: bool = True) -> str:
    """`player_teams(player_id, team_id)`: each player's team as of the slate week.

    The latest roster row at or before `:season`/`:week` wins (or the latest row
    at all when unbounded); `CUT` or `RET` there means no team. Only a player who
    never appears on a roster falls back to `sport_players.team_id`, which is
    last-write-wins by import order.
    """
    bound = "WHERE r.season < :season OR (r.season = :season AND r.week <= :week)" if week_bound else ""
    return f"""
    roster_latest AS (
        SELECT DISTINCT ON (r.player_id) r.player_id, r.team_id, r.status
        FROM nfl_player_weekly_rosters r
        {bound}
        ORDER BY r.player_id, r.season DESC, r.week DESC
    ),
    player_teams AS (
        SELECT p.id AS player_id,
               CASE
                   WHEN rl.player_id IS NULL THEN p.team_id
                   WHEN rl.status IN ('CUT', 'RET') THEN NULL
                   ELSE rl.team_id
               END AS team_id
        FROM sport_players p
        LEFT JOIN roster_latest rl ON rl.player_id = p.id
        WHERE p.sport = 'nfl'
    )
"""


# The slate week's injury and depth rows, plus each player's most recent depth row
# from an earlier week (any team), so a role change can be shown against it. Each
# is at most one row per player, so joining them does not multiply slate lines.
_AVAILABILITY_CTE = """
    week_injuries AS (
        SELECT player_id, report_status, practice_status, primary_injury
        FROM nfl_player_injuries WHERE season = :season AND week = :week
    ),
    week_depth AS (
        SELECT player_id, team_id, position, depth_rank
        FROM nfl_player_depth_charts WHERE season = :season AND week = :week
    ),
    previous_depth AS (
        SELECT DISTINCT ON (player_id) player_id, team_id, position, depth_rank
        FROM nfl_player_depth_charts
        WHERE season < :season OR (season = :season AND week < :week)
        ORDER BY player_id, season DESC, week DESC
    )
"""

_AVAILABILITY_COLUMNS = """
    wi.report_status AS injury_status, wi.practice_status, wi.primary_injury AS injury,
    wd.team_id AS depth_team_id, wd.position AS depth_position, wd.depth_rank,
    pd.team_id AS previous_depth_team_id, pd.position AS previous_depth_position,
    pd.depth_rank AS previous_depth_rank
"""

_AVAILABILITY_FIELDS = (
    "injury_status", "practice_status", "injury", "depth_team_id", "depth_position", "depth_rank",
    "previous_depth_team_id", "previous_depth_position", "previous_depth_rank",
)


def _availability(row) -> dict:
    return {field: row[field] for field in _AVAILABILITY_FIELDS}


# Item 34 stores lines for markets the model does not project, so a stored line is
# not necessarily a modelled one. Every reader that projects, grades or freezes
# lines keeps to these; the values are code constants, never request input.
MODELLED_MARKET_FILTER = "l.market IN ({})".format(", ".join(f"'{market.value}'" for market in NflPropMarket))

_LATEST_LINES_CTE = f"""
    latest_lines AS (
        SELECT DISTINCT ON (l.provider, l.provider_prop_id)
               l.id, l.provider, l.market, l.segment, l.line, l.start_time,
               l.fetched_at, l.player_id, l.game_id, l.odds_type, l.raw_json
        FROM sport_prop_lines l
        WHERE l.sport = 'nfl' AND {MODELLED_MARKET_FILTER}
        ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC
    )
"""

# Rows imported before migration 0021 carry NULL usage. Only rows with both
# values count as usage evidence, so unbackfilled history never reads as zero.
_USAGE_FILTER = "s.targets IS NOT NULL AND s.target_share IS NOT NULL"
_USAGE_AGGREGATES = (
    f"COUNT(*) FILTER (WHERE {_USAGE_FILTER}) AS usage_games, "
    f"AVG(s.targets) FILTER (WHERE {_USAGE_FILTER}) AS targets, "
    f"AVG(s.target_share) FILTER (WHERE {_USAGE_FILTER}) AS target_share"
)
_LINES_FILTER = "g.spread_line IS NOT NULL AND g.total_line IS NOT NULL"
# The player's own expected margin: NFLverse spread_line is the home margin.
_TEAM_MARGIN = "CASE WHEN s.team_id = g.home_team_id THEN g.spread_line ELSE -g.spread_line END"
_ENVIRONMENT_AGGREGATES = (
    f"COUNT(*) FILTER (WHERE {_LINES_FILTER}) AS environment_games, "
    f"AVG((g.total_line + {_TEAM_MARGIN}) / 2) FILTER (WHERE {_LINES_FILTER}) AS team_total, "
    f"AVG({_TEAM_MARGIN}) FILTER (WHERE {_LINES_FILTER}) AS team_margin"
)

# Every model aggregate is limited to information available before the slate
# week. The same cutoff protects player form, position fallback, and DVP from
# target-week leakage.
_BASELINES_CTE = f"""
    baselines AS (
        SELECT s.player_id, s.season, COUNT(*) AS games,
               AVG(s.passing_yards) AS passing_yards, AVG(s.passing_attempts) AS passing_attempts,
               AVG(s.passing_completions) AS passing_completions, AVG(s.rushing_yards) AS rushing_yards,
               AVG(s.rushing_attempts) AS rushing_attempts, AVG(s.receiving_yards) AS receiving_yards,
               AVG(s.receptions) AS receptions, AVG(s.touchdowns) AS touchdowns,
               AVG(s.fantasy_points) AS fantasy_points,
               AVG(s.prizepicks_fantasy_points) AS prizepicks_fantasy_points,
               {_USAGE_AGGREGATES},
               {_ENVIRONMENT_AGGREGATES}
        FROM nfl_player_weekly_stats s
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
        WHERE g.game_type = 'REG'
          AND (s.season < :season OR (s.season = :season AND s.week < :week))
        GROUP BY s.player_id, s.season
    ),
    position_baselines AS (
        SELECT p.position, s.season, COUNT(*) AS games,
               AVG(s.passing_yards) AS passing_yards, AVG(s.passing_attempts) AS passing_attempts,
               AVG(s.passing_completions) AS passing_completions, AVG(s.rushing_yards) AS rushing_yards,
               AVG(s.rushing_attempts) AS rushing_attempts, AVG(s.receiving_yards) AS receiving_yards,
               AVG(s.receptions) AS receptions, AVG(s.touchdowns) AS touchdowns,
               AVG(s.fantasy_points) AS fantasy_points,
               AVG(s.prizepicks_fantasy_points) AS prizepicks_fantasy_points,
               {_USAGE_AGGREGATES}
        FROM nfl_player_weekly_stats s
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
        JOIN sport_players p ON p.sport = 'nfl' AND p.id = s.player_id
        WHERE g.game_type = 'REG'
          AND (s.season < :season OR (s.season = :season AND s.week < :week))
        GROUP BY p.position, s.season
    ),
    opponent_position_baselines AS (
        SELECT s.opponent_team_id AS defense_team_id, p.position, COUNT(*) AS games,
               AVG(s.passing_yards) AS passing_yards, AVG(s.passing_attempts) AS passing_attempts,
               AVG(s.passing_completions) AS passing_completions, AVG(s.rushing_yards) AS rushing_yards,
               AVG(s.rushing_attempts) AS rushing_attempts, AVG(s.receiving_yards) AS receiving_yards,
               AVG(s.receptions) AS receptions, AVG(s.touchdowns) AS touchdowns,
               AVG(s.fantasy_points) AS fantasy_points,
               AVG(s.prizepicks_fantasy_points) AS prizepicks_fantasy_points
        FROM nfl_player_weekly_stats s
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
        JOIN sport_players p ON p.sport = 'nfl' AND p.id = s.player_id
        WHERE g.game_type = 'REG' AND s.opponent_team_id IS NOT NULL
          AND (s.season < :season OR (s.season = :season AND s.week < :week))
        GROUP BY s.opponent_team_id, p.position
    ),
    league_position_baselines AS (
        SELECT p.position, COUNT(*) AS games,
               AVG(s.passing_yards) AS passing_yards, AVG(s.passing_attempts) AS passing_attempts,
               AVG(s.passing_completions) AS passing_completions, AVG(s.rushing_yards) AS rushing_yards,
               AVG(s.rushing_attempts) AS rushing_attempts, AVG(s.receiving_yards) AS receiving_yards,
               AVG(s.receptions) AS receptions, AVG(s.touchdowns) AS touchdowns,
               AVG(s.fantasy_points) AS fantasy_points,
               AVG(s.prizepicks_fantasy_points) AS prizepicks_fantasy_points
        FROM nfl_player_weekly_stats s
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
        JOIN sport_players p ON p.sport = 'nfl' AND p.id = s.player_id
        WHERE g.game_type = 'REG'
          AND (s.season < :season OR (s.season = :season AND s.week < :week))
        GROUP BY p.position
    )
"""

_EMPTY_AVERAGES = {
    "games": 0, "passing_yards": 0.0, "passing_attempts": 0.0, "passing_completions": 0.0,
    "rushing_yards": 0.0, "rushing_attempts": 0.0, "receiving_yards": 0.0,
    "receptions": 0.0, "touchdowns": 0.0, "fantasy_points": None, "prizepicks_fantasy_points": None,
}


def _optional_float(value) -> float | None:
    return float(value) if value is not None else None


def _averages(row, prefix: str = "") -> dict:
    return {
        "games": row[f"{prefix}games"] or 0,
        "passing_yards": float(row[f"{prefix}passing_yards"] or 0),
        "passing_attempts": float(row[f"{prefix}passing_attempts"] or 0),
        "passing_completions": float(row[f"{prefix}passing_completions"] or 0),
        "rushing_yards": float(row[f"{prefix}rushing_yards"] or 0),
        "rushing_attempts": float(row[f"{prefix}rushing_attempts"] or 0),
        "receiving_yards": float(row[f"{prefix}receiving_yards"] or 0),
        "receptions": float(row[f"{prefix}receptions"] or 0),
        "touchdowns": float(row[f"{prefix}touchdowns"] or 0),
        "fantasy_points": _optional_float(row[f"{prefix}fantasy_points"]),
        "prizepicks_fantasy_points": _optional_float(row[f"{prefix}prizepicks_fantasy_points"]),
    }


def _optional_averages(row, prefix: str) -> dict | None:
    return _averages(row, prefix) if row[f"{prefix}games"] is not None else None


def _usage(row, prefix: str) -> dict | None:
    games = row.get(f"{prefix}usage_games") or 0
    if games == 0:
        return None
    return {
        "games": games,
        "targets": float(row[f"{prefix}targets"]),
        "target_share": float(row[f"{prefix}target_share"]),
    }


def _environment(row, prefix: str) -> dict | None:
    games = row.get(f"{prefix}environment_games") or 0
    if games == 0:
        return None
    return {
        "games": games,
        "team_total": float(row[f"{prefix}team_total"]),
        "team_margin": float(row[f"{prefix}team_margin"]),
    }


async def get_slate_games(db: AsyncSession, season: int, week: int) -> list[dict]:
    rows = await db.execute(
        text("""
            SELECT g.id, g.game_date, g.start_utc, g.status, away.team_code, home.team_code
            FROM sport_games g
            JOIN sport_teams home ON home.sport = 'nfl' AND home.id = g.home_team_id
            JOIN sport_teams away ON away.sport = 'nfl' AND away.id = g.away_team_id
            WHERE g.sport = 'nfl' AND g.season = :season AND g.week = :week AND g.game_type = 'REG'
            ORDER BY g.start_utc NULLS LAST, g.id
        """),
        {"season": season, "week": week},
    )
    return [
        {"game_id": r[0], "game_date": r[1], "start_utc": r[2], "status": r[3],
         "away_team": r[4], "home_team": r[5]}
        for r in rows.fetchall()
    ]


async def get_slate_team_elo(
    db: AsyncSession, season: int, week: int, model_version: str = NFL_ELO_MODEL_VERSION,
) -> dict[int, tuple[str, float, float]]:
    """(NFLverse game key, home pre-game ELO, away pre-game ELO) per slate game with both ratings."""
    rows = await db.execute(
        text("""
            SELECT g.id, g.source_game_id, h.elo_pre, a.elo_pre
            FROM sport_games g
            JOIN nfl_team_elo h ON h.game_id = g.id AND h.is_home AND h.model_version = :model_version
            JOIN nfl_team_elo a ON a.game_id = g.id AND NOT a.is_home AND a.model_version = :model_version
            WHERE g.sport = 'nfl' AND g.season = :season AND g.week = :week AND g.game_type = 'REG'
        """),
        {"season": season, "week": week, "model_version": model_version},
    )
    return {row[0]: (row[1], float(row[2]), float(row[3])) for row in rows.fetchall()}


async def get_slate_weather(db: AsyncSession, season: int, week: int) -> dict[int, dict]:
    """Newest stored weather snapshot per selected slate game."""
    rows = await db.execute(text("""
        SELECT DISTINCT ON (g.id) g.id, home.team_code, w.venue_type, w.forecast_for,
               w.temperature_f, w.wind_mph, w.wind_gust_mph, w.precipitation_probability, w.fetched_at
        FROM sport_games g JOIN sport_teams home ON home.sport = 'nfl' AND home.id = g.home_team_id
        LEFT JOIN nfl_game_weather_snapshots w ON w.game_id = g.id
        WHERE g.sport = 'nfl' AND g.season = :season AND g.week = :week AND g.game_type = 'REG'
        ORDER BY g.id, w.fetched_at DESC NULLS LAST, w.id DESC
    """), {"season": season, "week": week})
    return {row[0]: {"home_team": row[1], "venue_type": row[2], "forecast_for": row[3], "temperature_f": float(row[4]) if row[4] is not None else None, "wind_mph": float(row[5]) if row[5] is not None else None, "wind_gust_mph": float(row[6]) if row[6] is not None else None, "precipitation_probability": float(row[7]) if row[7] is not None else None, "fetched_at": row[8]} for row in rows.fetchall()}


async def get_week_skill_injuries(db: AsyncSession, season: int, week: int) -> list[dict]:
    """The week's QB/RB/WR/TE injury report, including players with no prop line.

    The team is the one that filed the report, not the player's last-write team.
    """
    rows = await db.execute(text("""
        SELECT i.team_id, t.team_code, p.name, p.position,
               i.report_status, i.practice_status, i.primary_injury, p.id
        FROM nfl_player_injuries i
        JOIN sport_players p ON p.sport = 'nfl' AND p.id = i.player_id
        JOIN sport_teams t ON t.sport = 'nfl' AND t.id = i.team_id
        WHERE i.season = :season AND i.week = :week
          AND p.position IN ('QB', 'RB', 'WR', 'TE')
          AND (i.report_status IS NOT NULL OR i.practice_status IS NOT NULL)
    """), {"season": season, "week": week})
    return [
        {"team_id": row[0], "team": row[1], "player_name": row[2], "position": row[3],
         "injury_status": row[4], "practice_status": row[5], "injury": row[6], "player_id": row[7]}
        for row in rows.fetchall()
    ]


async def get_week_depth_rows(db: AsyncSession, season: int, week: int) -> list[dict]:
    """The week's depth chart, each row paired with the player's previous chart row.

    Uses the slate's availability CTE so the panel and the line tags apply one rule.
    """
    rows = await db.execute(text(f"""
        WITH {_AVAILABILITY_CTE}
        SELECT wd.team_id, t.team_code, p.name, wd.position, wd.depth_rank,
               pd.team_id, pd.position, pd.depth_rank, p.id
        FROM week_depth wd
        JOIN sport_players p ON p.sport = 'nfl' AND p.id = wd.player_id
        JOIN sport_teams t ON t.sport = 'nfl' AND t.id = wd.team_id
        LEFT JOIN previous_depth pd ON pd.player_id = wd.player_id
    """), {"season": season, "week": week})
    return [
        {"team_id": row[0], "team": row[1], "player_name": row[2], "depth_team_id": row[0],
         "depth_position": row[3], "depth_rank": row[4], "previous_depth_team_id": row[5],
         "previous_depth_position": row[6], "previous_depth_rank": row[7], "player_id": row[8]}
        for row in rows.fetchall()
    ]


async def get_week_line_movement(db: AsyncSession, season: int, week: int) -> list[dict]:
    """First and last pre-kickoff spread and total per game, both from one book.

    One book per game and market, so a switch between books never reads as
    movement: DraftKings when it has a row, else the book with the most rows.
    Capitalized keys are the 2026-09-17 run's mislabeled rows and are skipped.
    This is not item 28's pre-registered entry line.
    """
    rows = await db.execute(text("""
        WITH week_games AS (
            SELECT id, start_utc FROM sport_games
            WHERE sport = 'nfl' AND season = :season AND week = :week AND game_type = 'REG'
        ), pre_kickoff AS (
            SELECT o.id, o.game_id, o.book, o.market, o.line, o.fetched_at
            FROM sport_game_odds o JOIN week_games g ON g.id = o.game_id
            WHERE o.sport = 'nfl' AND o.provider = 'the_odds_api_us' AND o.market IN ('spread', 'total') AND o.line IS NOT NULL AND o.book = lower(o.book)
              AND (g.start_utc IS NULL OR o.fetched_at < g.start_utc)
        ), chosen_book AS (
            SELECT DISTINCT ON (game_id, market) game_id, market, book
            FROM pre_kickoff GROUP BY game_id, market, book
            ORDER BY game_id, market, (book = 'draftkings') DESC, COUNT(*) DESC, book
        ), ranked AS (
            SELECT p.game_id, p.market, p.book, p.line, p.fetched_at,
                   ROW_NUMBER() OVER (PARTITION BY p.game_id, p.market ORDER BY p.fetched_at, p.id) AS from_open,
                   ROW_NUMBER() OVER (PARTITION BY p.game_id, p.market ORDER BY p.fetched_at DESC, p.id DESC) AS from_current
            FROM pre_kickoff p JOIN chosen_book c USING (game_id, market, book)
        )
        SELECT game_id, market, book,
               MAX(line) FILTER (WHERE from_open = 1), MAX(fetched_at) FILTER (WHERE from_open = 1),
               MAX(line) FILTER (WHERE from_current = 1), MAX(fetched_at) FILTER (WHERE from_current = 1)
        FROM ranked GROUP BY game_id, market, book
        ORDER BY game_id, market
    """), {"season": season, "week": week})
    return [
        {"game_id": row[0], "market": row[1], "book": row[2],
         "open_line": float(row[3]), "open_fetched_at": row[4],
         "current_line": float(row[5]), "current_fetched_at": row[6]}
        for row in rows.fetchall()
    ]


async def get_game(db: AsyncSession, game_id: int) -> dict | None:
    """One regular-season game in `get_games`' shape, or None."""
    row = (await db.execute(text("""
        SELECT g.id, g.season, g.week, g.game_date, g.start_utc, away.team_code, home.team_code, g.status
        FROM sport_games g
        JOIN sport_teams home ON home.sport = 'nfl' AND home.id = g.home_team_id
        JOIN sport_teams away ON away.sport = 'nfl' AND away.id = g.away_team_id
        WHERE g.sport = 'nfl' AND g.id = :game_id AND g.game_type = 'REG'
    """), {"game_id": game_id})).first()
    if row is None:
        return None
    return {"game_id": row[0], "season": row[1], "week": row[2], "game_date": row[3], "start_utc": row[4],
            "away_team": row[5], "home_team": row[6], "status": row[7]}


async def get_game_line_history(db: AsyncSession, game_id: int) -> list[dict]:
    """Every pre-kickoff spread and total row for one game, from one book per market.

    Same book rule as `get_week_line_movement`, so the game page's chart and the
    notes' open-to-current move read from one book. A spread line is the home
    spread in book sign, as the slate reads it.
    """
    rows = await db.execute(text("""
        WITH pre_kickoff AS (
            SELECT o.id, o.book, o.market, o.line, o.fetched_at
            FROM sport_game_odds o JOIN sport_games g ON g.sport = 'nfl' AND g.id = o.game_id
            WHERE o.sport = 'nfl' AND o.provider = 'the_odds_api_us' AND o.game_id = :game_id AND o.market IN ('spread', 'total') AND o.line IS NOT NULL
              AND o.book = lower(o.book) AND (g.start_utc IS NULL OR o.fetched_at < g.start_utc)
        ), chosen_book AS (
            SELECT DISTINCT ON (market) market, book
            FROM pre_kickoff GROUP BY market, book
            ORDER BY market, (book = 'draftkings') DESC, COUNT(*) DESC, book
        )
        SELECT p.market, p.book, p.line, p.fetched_at
        FROM pre_kickoff p JOIN chosen_book c USING (market, book)
        ORDER BY p.market, p.fetched_at, p.id
    """), {"game_id": game_id})
    return [{"market": row[0], "book": row[1], "line": float(row[2]), "fetched_at": row[3]} for row in rows.fetchall()]


async def get_week_game_rest(db: AsyncSession, season: int, week: int) -> dict[int, dict]:
    """Each week game's two teams, NFLverse rest days, and final score (all NULL when unpublished)."""
    rows = await db.execute(text("""
        SELECT g.id, g.away_team_id, away.team_code, g.away_rest, g.home_team_id, home.team_code, g.home_rest,
               g.away_score, g.home_score
        FROM sport_games g
        JOIN sport_teams away ON away.sport = 'nfl' AND away.id = g.away_team_id
        JOIN sport_teams home ON home.sport = 'nfl' AND home.id = g.home_team_id
        WHERE g.sport = 'nfl' AND g.season = :season AND g.week = :week AND g.game_type = 'REG'
    """), {"season": season, "week": week})
    return {
        row[0]: {"away_team_id": row[1], "away_team": row[2], "away_rest": row[3],
                 "home_team_id": row[4], "home_team": row[5], "home_rest": row[6],
                 "away_score": row[7], "home_score": row[8]}
        for row in rows.fetchall()
    }


async def get_week_team_recent_results(
    db: AsyncSession, season: int, week: int, limit: int = 3,
) -> dict[int, list[dict]]:
    """Each team's latest completed regular-season games this season before the week, newest first."""
    rows = await db.execute(text("""
        WITH team_games AS (
            SELECT g.week, g.home_team_id team_id, g.away_team_id opponent_id, TRUE is_home,
                   g.home_score points_for, g.away_score points_against
            FROM sport_games g WHERE g.sport = 'nfl' AND g.season = :season AND g.week < :week AND g.game_type = 'REG' AND g.status = 'completed'
            UNION ALL
            SELECT g.week, g.away_team_id, g.home_team_id, FALSE, g.away_score, g.home_score
            FROM sport_games g WHERE g.sport = 'nfl' AND g.season = :season AND g.week < :week AND g.game_type = 'REG' AND g.status = 'completed'
        ), ranked AS (
            SELECT tg.*, ROW_NUMBER() OVER (PARTITION BY tg.team_id ORDER BY tg.week DESC) AS recency
            FROM team_games tg
        )
        SELECT r.team_id, r.week, t.team_code, r.is_home, r.points_for, r.points_against
        FROM ranked r JOIN sport_teams t ON t.sport = 'nfl' AND t.id = r.opponent_id
        WHERE r.recency <= :limit
        ORDER BY r.team_id, r.week DESC
    """), {"season": season, "week": week, "limit": limit})
    results: dict[int, list[dict]] = {}
    for row in rows.fetchall():
        results.setdefault(row[0], []).append(
            {"week": row[1], "opponent": row[2], "is_home": row[3], "points_for": row[4], "points_against": row[5]},
        )
    return results


async def get_week_team_qb_games(
    db: AsyncSession, season: int, week: int, games: int,
) -> dict[int, list[QbGame]]:
    """Each week team's QB passing attempts in its latest completed REG games before the week.

    Crosses into last season, so week 1 compares against the team's previous
    games. Only `QB` players count, so a trick-play pass never makes a starter.
    """
    rows = await db.execute(text("""
        WITH week_teams AS (
            SELECT home_team_id AS team_id FROM sport_games
            WHERE sport = 'nfl' AND season = :season AND week = :week AND game_type = 'REG'
            UNION
            SELECT away_team_id FROM sport_games
            WHERE sport = 'nfl' AND season = :season AND week = :week AND game_type = 'REG'
        ), team_games AS (
            SELECT g.id AS game_id, g.season, g.week, side.team_id,
                   ROW_NUMBER() OVER (PARTITION BY side.team_id ORDER BY g.season DESC, g.week DESC) AS recency
            FROM sport_games g
            CROSS JOIN LATERAL (VALUES (g.home_team_id), (g.away_team_id)) AS side(team_id)
            WHERE g.sport = 'nfl' AND g.game_type = 'REG' AND g.status = 'completed'
              AND g.season >= :season - 1 AND (g.season < :season OR g.week < :week)
              AND side.team_id IN (SELECT team_id FROM week_teams)
        )
        SELECT tg.team_id, tg.season, tg.week, tg.recency, p.id, p.name, s.passing_attempts
        FROM team_games tg
        JOIN nfl_player_weekly_stats s ON s.game_id = tg.game_id AND s.team_id = tg.team_id
        JOIN sport_players p ON p.sport = 'nfl' AND p.id = s.player_id
        WHERE tg.recency <= :games AND p.position = 'QB' AND s.passing_attempts > 0
    """), {"season": season, "week": week, "games": games})
    qb_games: dict[int, list[QbGame]] = {}
    for row in rows.fetchall():
        qb_games.setdefault(row[0], []).append(
            QbGame(season=row[1], week=row[2], recency=row[3], qb=Qb(player_id=row[4], name=row[5]), attempts=row[6]),
        )
    return qb_games


async def get_week_team_qb1_charts(
    db: AsyncSession, season: int, week: int,
) -> dict[int, tuple[Qb | None, Qb | None]]:
    """Each team's depth-chart QB1 on its latest and previous stored charts at or before the week.

    The latest chart may be last week's: charts are snapshotted days before a game.
    """
    rows = await db.execute(text("""
        WITH charts AS (
            SELECT d.team_id, d.season, d.week, d.player_id,
                   DENSE_RANK() OVER (PARTITION BY d.team_id ORDER BY d.season DESC, d.week DESC) AS chart_recency
            FROM nfl_player_depth_charts d
            WHERE d.position = 'QB' AND d.season >= :season - 1 AND (d.season < :season OR d.week <= :week)
        )
        SELECT DISTINCT ON (c.team_id, c.chart_recency) c.team_id, c.chart_recency, p.id, p.name
        FROM charts c
        JOIN nfl_player_depth_charts d ON d.team_id = c.team_id AND d.season = c.season AND d.week = c.week
             AND d.player_id = c.player_id AND d.depth_rank = 1
        JOIN sport_players p ON p.sport = 'nfl' AND p.id = c.player_id
        WHERE c.chart_recency <= 2
        ORDER BY c.team_id, c.chart_recency, p.name
    """), {"season": season, "week": week})
    qb1: dict[tuple[int, int], Qb] = {(row[0], row[1]): Qb(player_id=row[2], name=row[3]) for row in rows.fetchall()}
    return {team_id: (qb1.get((team_id, 1)), qb1.get((team_id, 2))) for team_id, _ in qb1}


async def get_week_game_quotes(
    db: AsyncSession, season: int, week: int,
) -> dict[int, tuple[datetime | None, list[Quote]]]:
    """Each week game's kickoff and its newest pre-kickoff row per provider, book and market.

    Every feed is read (item 36b), so a book stored by two providers arrives
    twice and the best-line rule keeps the newer. First side is home, or over.
    """
    rows = await db.execute(text("""
        SELECT DISTINCT ON (o.game_id, o.provider, o.book, o.market)
               o.game_id, g.start_utc, o.book, o.provider, o.market, o.line,
               o.first_odds, o.second_odds, o.first_market_prob, o.fetched_at
        FROM sport_game_odds o
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = o.game_id
        WHERE o.sport = 'nfl' AND o.provider IN ('the_odds_api_us', 'the_odds_api_eu', 'odds_api_io')
          AND g.season = :season AND g.week = :week AND g.game_type = 'REG'
          AND o.book = lower(o.book) AND (g.start_utc IS NULL OR o.fetched_at < g.start_utc)
        ORDER BY o.game_id, o.provider, o.book, o.market, o.fetched_at DESC, o.id DESC
    """), {"season": season, "week": week})
    games: dict[int, tuple[datetime | None, list[Quote]]] = {}
    for row in rows.fetchall():
        line = float(row[5]) if row[5] is not None else None
        quote = Quote(book=row[2], provider=row[3], market=row[4], line=line, first_odds=row[6],
                      second_odds=row[7], first_probability=row[8], fetched_at=row[9])
        games.setdefault(row[0], (row[1], []))[1].append(quote)
    return games


async def get_week_team_qb_injuries(db: AsyncSession, season: int, week: int) -> dict[int, dict[int, QbInjury]]:
    """Each team's QBs in its latest stored injury report this season, at or before the week.

    Healthy players are absent from a report, so only the team's latest report
    week counts; an older Out never outlives the report that dropped it.
    """
    rows = await db.execute(text("""
        WITH latest AS (
            SELECT team_id, MAX(week) AS week FROM nfl_player_injuries
            WHERE season = :season AND week <= :week GROUP BY team_id
        )
        SELECT i.team_id, i.player_id, i.week, i.report_status
        FROM nfl_player_injuries i
        JOIN latest l ON l.team_id = i.team_id AND l.week = i.week
        JOIN sport_players p ON p.sport = 'nfl' AND p.id = i.player_id
        WHERE i.season = :season AND p.position = 'QB'
    """), {"season": season, "week": week})
    injuries: dict[int, dict[int, QbInjury]] = {}
    for row in rows.fetchall():
        injuries.setdefault(row[0], {})[row[1]] = QbInjury(week=row[2], status=row[3])
    return injuries


async def get_week_team_games(db: AsyncSession, season: int, week: int) -> list[TeamGame]:
    """Both sides of every completed regular-season game this season before the week.

    Allowed stats come from the other side of the game, not `opponent_team_id`,
    which can be NULL. Unloaded stats stay NULL rather than zero.
    """
    rows = await db.execute(text("""
        WITH team_games AS (
            SELECT g.id AS game_id, g.home_team_id AS team_id, g.away_team_id AS opponent_id,
                   g.home_score AS points_for, g.away_score AS points_against
            FROM sport_games g
            WHERE g.sport = 'nfl' AND g.season = :season AND g.week < :week AND g.game_type = 'REG' AND g.status = 'completed'
            UNION ALL
            SELECT g.id, g.away_team_id, g.home_team_id, g.away_score, g.home_score
            FROM sport_games g
            WHERE g.sport = 'nfl' AND g.season = :season AND g.week < :week AND g.game_type = 'REG' AND g.status = 'completed'
        ), yards AS (
            SELECT s.game_id, s.team_id, SUM(s.passing_yards) AS pass_yards, SUM(s.rushing_yards) AS rush_yards
            FROM nfl_player_weekly_stats s
            WHERE s.season = :season AND s.week < :week
            GROUP BY s.game_id, s.team_id
        )
        SELECT tg.team_id, tg.points_for, tg.points_against,
               yo.pass_yards, yd.pass_yards, yo.rush_yards, yd.rush_yards,
               eo.plays, ed.plays, eo.epa, ed.epa, eo.successes, ed.successes
        FROM team_games tg
        LEFT JOIN yards yo ON yo.game_id = tg.game_id AND yo.team_id = tg.team_id
        LEFT JOIN yards yd ON yd.game_id = tg.game_id AND yd.team_id = tg.opponent_id
        LEFT JOIN nfl_team_game_efficiency eo ON eo.game_id = tg.game_id AND eo.team_id = tg.team_id
        LEFT JOIN nfl_team_game_efficiency ed ON ed.game_id = tg.game_id AND ed.team_id = tg.opponent_id
        WHERE tg.points_for IS NOT NULL AND tg.points_against IS NOT NULL
    """), {"season": season, "week": week})
    return [
        TeamGame(
            team_id=row[0], points_for=row[1], points_against=row[2],
            pass_yards_for=_float_or_none(row[3]), pass_yards_against=_float_or_none(row[4]),
            rush_yards_for=_float_or_none(row[5]), rush_yards_against=_float_or_none(row[6]),
            plays_for=row[7], plays_against=row[8], epa_for=row[9], epa_against=row[10],
            successes_for=row[11], successes_against=row[12],
        )
        for row in rows.fetchall()
    ]


def _float_or_none(value: object) -> float | None:
    return None if value is None else float(value)


async def get_slate_lines(db: AsyncSession, season: int, week: int) -> list[dict]:
    """Latest linked prop lines with pre-week player, position, and DVP inputs."""
    return await _slate_line_rows(db, season, week, _LATEST_LINES_CTE, {})


async def _slate_line_rows(
    db: AsyncSession, season: int, week: int, lines_cte: str, params: dict[str, object],
) -> list[dict]:
    """Pre-week model inputs for every row of `lines_cte`, which must define `latest_lines`.

    The slate passes stored PrizePicks lines; the projection backtest passes
    player-games, so both run through exactly the same baseline query.

    The join fans out to one row per line per season the player has played, then
    `choose_baseline_season` collapses that back to the single season the
    baseline should come from. Opponent and league position aggregates are shared
    across those season rows, so the query remains batched.
    """
    rows = await db.execute(
        text(f"""
            WITH {lines_cte}, {_BASELINES_CTE}, {_player_teams_cte()}, {_AVAILABILITY_CTE}
            SELECT l.id, l.game_id, l.player_id, p.name AS player_name, p.position,
                   {_AVAILABILITY_COLUMNS},
                   pt.team_id AS player_team_id, g.home_team_id,
                   CASE
                       WHEN pt.team_id = g.home_team_id THEN away.team_code
                       WHEN pt.team_id = g.away_team_id THEN home.team_code
                   END AS opponent_team,
                   CASE
                       WHEN pt.team_id = g.home_team_id THEN g.away_team_id
                       WHEN pt.team_id = g.away_team_id THEN g.home_team_id
                   END AS opponent_team_id,
                   l.market, l.segment, l.line, l.provider, l.fetched_at, l.odds_type,
                   b.season AS baseline_season, b.games AS player_games,
                   b.passing_yards AS player_passing_yards, b.passing_attempts AS player_passing_attempts,
                   b.passing_completions AS player_passing_completions, b.rushing_yards AS player_rushing_yards,
                   b.rushing_attempts AS player_rushing_attempts, b.receiving_yards AS player_receiving_yards,
                   b.receptions AS player_receptions, b.touchdowns AS player_touchdowns,
                   b.fantasy_points AS player_fantasy_points,
                   b.prizepicks_fantasy_points AS player_prizepicks_fantasy_points,
                   b.usage_games AS player_usage_games, b.targets AS player_targets,
                   b.target_share AS player_target_share,
                   b.environment_games AS player_environment_games, b.team_total AS player_team_total,
                   b.team_margin AS player_team_margin,
                   pb.usage_games AS position_usage_games, pb.targets AS position_targets,
                   pb.target_share AS position_target_share,
                   pb.games AS position_games, pb.passing_yards AS position_passing_yards,
                   pb.passing_attempts AS position_passing_attempts,
                   pb.passing_completions AS position_passing_completions,
                   pb.rushing_yards AS position_rushing_yards,
                   pb.rushing_attempts AS position_rushing_attempts,
                   pb.receiving_yards AS position_receiving_yards, pb.receptions AS position_receptions,
                   pb.touchdowns AS position_touchdowns, pb.fantasy_points AS position_fantasy_points,
                   pb.prizepicks_fantasy_points AS position_prizepicks_fantasy_points,
                   op.games AS opponent_games, op.passing_yards AS opponent_passing_yards,
                   op.passing_attempts AS opponent_passing_attempts,
                   op.passing_completions AS opponent_passing_completions,
                   op.rushing_yards AS opponent_rushing_yards,
                   op.rushing_attempts AS opponent_rushing_attempts,
                   op.receiving_yards AS opponent_receiving_yards, op.receptions AS opponent_receptions,
                   op.touchdowns AS opponent_touchdowns, op.fantasy_points AS opponent_fantasy_points,
                   op.prizepicks_fantasy_points AS opponent_prizepicks_fantasy_points,
                   lp.games AS league_games, lp.passing_yards AS league_passing_yards,
                   lp.passing_attempts AS league_passing_attempts,
                   lp.passing_completions AS league_passing_completions,
                   lp.rushing_yards AS league_rushing_yards,
                   lp.rushing_attempts AS league_rushing_attempts,
                   lp.receiving_yards AS league_receiving_yards, lp.receptions AS league_receptions,
                   lp.touchdowns AS league_touchdowns, lp.fantasy_points AS league_fantasy_points,
                   lp.prizepicks_fantasy_points AS league_prizepicks_fantasy_points
            FROM latest_lines l
            JOIN sport_games g ON g.sport = 'nfl' AND g.id = l.game_id
            JOIN sport_players p ON p.sport = 'nfl' AND p.id = l.player_id
            JOIN player_teams pt ON pt.player_id = p.id
            JOIN sport_teams home ON home.sport = 'nfl' AND home.id = g.home_team_id
            JOIN sport_teams away ON away.sport = 'nfl' AND away.id = g.away_team_id
            LEFT JOIN baselines b ON b.player_id = l.player_id
            LEFT JOIN position_baselines pb ON pb.position IS NOT DISTINCT FROM p.position
                AND pb.season = b.season
            LEFT JOIN opponent_position_baselines op ON op.defense_team_id = CASE
                WHEN pt.team_id = g.home_team_id THEN g.away_team_id
                WHEN pt.team_id = g.away_team_id THEN g.home_team_id
            END
                AND op.position IS NOT DISTINCT FROM p.position
            LEFT JOIN league_position_baselines lp ON lp.position IS NOT DISTINCT FROM p.position
            LEFT JOIN week_injuries wi ON wi.player_id = p.id
            LEFT JOIN week_depth wd ON wd.player_id = p.id
            LEFT JOIN previous_depth pd ON pd.player_id = p.id
            WHERE g.season = :season AND g.week = :week AND g.game_type = 'REG'
            ORDER BY p.name, l.market, l.line, l.id, b.season
        """),
        {"season": season, "week": week, **params},
    )

    by_line: dict[int, dict] = {}
    seasons_by_line: dict[int, dict[int, dict]] = {}
    for row in rows.mappings():
        line_id = row["id"]
        if line_id not in by_line:
            by_line[line_id] = {
                "id": line_id, "game_id": row["game_id"], "player_id": row["player_id"],
                "player_name": row["player_name"], "position": row["position"],
                "player_team_id": row["player_team_id"], "home_team_id": row["home_team_id"],
                "opponent_team": row["opponent_team"],
                "opponent_team_id": row["opponent_team_id"],
                "market": row["market"], "segment": row["segment"], "line": float(row["line"]),
                "provider": row["provider"], "fetched_at": row["fetched_at"],
                "odds_type": row["odds_type"],
                "opponent_averages": _optional_averages(row, "opponent_"),
                "league_position_averages": _optional_averages(row, "league_"),
                **_availability(row),
            }
            seasons_by_line[line_id] = {}
        # A LEFT JOIN miss is a player with no stats at all, not a season row.
        if row["baseline_season"] is not None:
            seasons_by_line[line_id][row["baseline_season"]] = {
                "averages": _averages(row, "player_"),
                "position_averages": _optional_averages(row, "position_") or dict(_EMPTY_AVERAGES),
                "usage": _usage(row, "player_"),
                "position_usage": _usage(row, "position_"),
                "environment": _environment(row, "player_"),
            }

    lines = []
    for line_id, line in by_line.items():
        per_season = seasons_by_line[line_id]
        choice = choose_baseline_season(
            season,
            [SeasonGames(year, values["averages"]["games"]) for year, values in per_season.items()],
        )
        line["baseline_season"] = choice.season
        line["baseline_reason"] = choice.reason
        # Anytime TD blends every season instead of trusting the one selected above.
        line["td_seasons"] = [
            {"season": year, "games": values["averages"]["games"], "touchdowns": values["averages"]["touchdowns"]}
            for year, values in sorted(per_season.items())
        ]
        selected = per_season.get(choice.season)
        line["averages"] = selected["averages"] if selected is not None else dict(_EMPTY_AVERAGES)
        line["position_averages"] = selected["position_averages"] if selected is not None else dict(_EMPTY_AVERAGES)
        line["usage"] = selected["usage"] if selected is not None else None
        line["position_usage"] = selected["position_usage"] if selected is not None else None
        line["environment"] = selected["environment"] if selected is not None else None
        line["baseline_seasons"] = per_season
        lines.append(line)
    await _attach_snap_history(db, season, week, lines)
    return lines


async def get_slate_player_history(
    db: AsyncSession, season: int, week: int, player_ids: list[int],
) -> dict[int, list[dict]]:
    """Completed pre-week stat lines for every player on the slate, newest first."""
    if not player_ids:
        return {}
    rows = await db.execute(
        text("""
            SELECT s.player_id, s.opponent_team_id, opponent.team_code AS opponent_team,
                   g.season, g.week, g.start_utc,
                   s.passing_yards, s.passing_attempts, s.passing_completions,
                   s.rushing_yards, s.rushing_attempts, s.receiving_yards,
                   s.receptions, s.touchdowns, s.fantasy_points
            FROM nfl_player_weekly_stats s
            JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
            LEFT JOIN sport_teams opponent ON opponent.sport = 'nfl' AND opponent.id = s.opponent_team_id
            WHERE s.player_id = ANY(CAST(:player_ids AS bigint[]))
              AND g.game_type = 'REG' AND g.status = 'completed'
              AND (g.season < :season OR (g.season = :season AND g.week < :week))
            ORDER BY s.player_id, g.season DESC, g.week DESC, g.start_utc DESC NULLS LAST, g.id DESC
        """),
        {"season": season, "week": week, "player_ids": player_ids},
    )
    history: dict[int, list[dict]] = {}
    for row in rows.mappings():
        history.setdefault(row["player_id"], []).append({
            "opponent_team_id": row["opponent_team_id"],
            "opponent_team": row["opponent_team"],
            "passing_yards": float(row["passing_yards"] or 0),
            "passing_attempts": float(row["passing_attempts"] or 0),
            "passing_completions": float(row["passing_completions"] or 0),
            "rushing_yards": float(row["rushing_yards"] or 0),
            "rushing_attempts": float(row["rushing_attempts"] or 0),
            "receiving_yards": float(row["receiving_yards"] or 0),
            "receptions": float(row["receptions"] or 0),
            "touchdowns": float(row["touchdowns"] or 0),
            "fantasy_points": float(row["fantasy_points"]) if row["fantasy_points"] is not None else None,
        })
    return history


async def get_slate_opponent_position_history(db: AsyncSession, season: int, week: int) -> dict[tuple[int, str], list[dict]]:
    rows = await db.execute(text("""SELECT s.opponent_team_id defense_team_id, p.position, offense.team_code opponent_team, g.season, g.week, SUM(s.passing_yards) passing_yards, SUM(s.passing_attempts) passing_attempts, SUM(s.passing_completions) passing_completions, SUM(s.rushing_yards) rushing_yards, SUM(s.rushing_attempts) rushing_attempts, SUM(s.receiving_yards) receiving_yards, SUM(s.receptions) receptions, SUM(s.touchdowns) touchdowns, SUM(s.fantasy_points) fantasy_points FROM nfl_player_weekly_stats s JOIN sport_players p ON p.sport = 'nfl' AND p.id = s.player_id JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id LEFT JOIN sport_teams offense ON offense.sport = 'nfl' AND offense.id = s.team_id WHERE s.opponent_team_id IS NOT NULL AND g.game_type = 'REG' AND g.status = 'completed' AND (g.season < :season OR (g.season = :season AND g.week < :week)) GROUP BY s.opponent_team_id, p.position, offense.team_code, g.id, g.season, g.week ORDER BY s.opponent_team_id, p.position, g.season DESC, g.week DESC"""), {"season": season, "week": week})
    history: dict[tuple[int, str], list[dict]] = {}
    fields = ("passing_yards", "passing_attempts", "passing_completions", "rushing_yards", "rushing_attempts", "receiving_yards", "receptions", "touchdowns", "fantasy_points")
    for row in rows.mappings():
        bucket = history.setdefault((row["defense_team_id"], row["position"]), [])
        if len(bucket) < 5:
            bucket.append({field: float(row[field] or 0) for field in fields} | {"opponent_team": row["opponent_team"], "opponent_team_id": None})
    return history


async def get_team_game_position_totals(
    db: AsyncSession, season: int, week: int,
) -> dict[tuple[int, str], list[NflTeamGameTotals]]:
    """Each defense's pre-week position totals per completed team-game, newest first.

    Grouped by game only, not by the offense's team code, so a player with a
    stale team never splits one game into two.
    """
    rows = await db.execute(
        text("""
            SELECT s.opponent_team_id AS defense_team_id, p.position, g.id AS game_id, g.season, g.week,
                   SUM(s.passing_yards) AS passing_yards, SUM(s.passing_attempts) AS passing_attempts,
                   SUM(s.passing_completions) AS passing_completions, SUM(s.rushing_yards) AS rushing_yards,
                   SUM(s.rushing_attempts) AS rushing_attempts, SUM(s.receiving_yards) AS receiving_yards,
                   SUM(s.receptions) AS receptions, SUM(s.touchdowns) AS touchdowns,
                   SUM(s.fantasy_points) AS fantasy_points
            FROM nfl_player_weekly_stats s
            JOIN sport_players p ON p.sport = 'nfl' AND p.id = s.player_id
            JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
            WHERE g.game_type = 'REG' AND g.status = 'completed'
              AND s.opponent_team_id IS NOT NULL AND p.position IS NOT NULL
              AND (s.season < :season OR (s.season = :season AND s.week < :week))
            GROUP BY s.opponent_team_id, p.position, g.id, g.season, g.week
            ORDER BY s.opponent_team_id, p.position, g.season DESC, g.week DESC, g.id DESC
        """),
        {"season": season, "week": week},
    )
    totals: dict[tuple[int, str], list[NflTeamGameTotals]] = {}
    for row in rows.mappings():
        totals.setdefault((row["defense_team_id"], row["position"]), []).append(NflTeamGameTotals(
            game_id=row["game_id"], season=row["season"], week=row["week"],
            passing_yards=float(row["passing_yards"] or 0),
            passing_attempts=float(row["passing_attempts"] or 0),
            passing_completions=float(row["passing_completions"] or 0),
            rushing_yards=float(row["rushing_yards"] or 0),
            rushing_attempts=float(row["rushing_attempts"] or 0),
            receiving_yards=float(row["receiving_yards"] or 0),
            receptions=float(row["receptions"] or 0),
            touchdowns=float(row["touchdowns"] or 0),
            fantasy_points=float(row["fantasy_points"]) if row["fantasy_points"] is not None else None,
        ))
    return totals


async def get_slate_market_probabilities(
    db: AsyncSession, season: int, week: int,
) -> dict[int, tuple[float | None, datetime | None]]:
    """Latest home moneyline probability and its fetch time per slate game, in one query."""
    rows = await db.execute(
        text("""
            SELECT DISTINCT ON (g.id) g.id, o.first_market_prob, o.fetched_at
            FROM sport_games g
            LEFT JOIN sport_game_odds o ON o.sport = 'nfl' AND o.provider = 'the_odds_api_us' AND o.game_id = g.id
                AND o.market = 'moneyline' AND o.first_side = 'home'
            WHERE g.sport = 'nfl' AND g.season = :season AND g.week = :week AND g.game_type = 'REG'
            ORDER BY g.id, o.fetched_at DESC NULLS LAST, o.id DESC
        """),
        {"season": season, "week": week},
    )
    return {row[0]: (float(row[1]) if row[1] is not None else None, row[2]) for row in rows.fetchall()}


async def get_slate_prop_odds(db: AsyncSession, season: int, week: int) -> dict[tuple[int, int], list[tuple[float, bool, datetime]]]:
    """Latest anytime-TD price per book for each resolved player in the week's games."""
    rows = await db.execute(
        text("""
            SELECT DISTINCT ON (o.game_id, o.player_id, o.book)
                   o.game_id, o.player_id, o.market_prob, o.includes_margin, o.fetched_at
            FROM nfl_player_prop_odds o
            JOIN sport_games g ON g.sport = 'nfl' AND g.id = o.game_id
            WHERE g.season = :season AND g.week = :week AND g.game_type = 'REG'
              AND o.market = 'anytime_touchdown' AND o.player_id IS NOT NULL
            ORDER BY o.game_id, o.player_id, o.book, o.fetched_at DESC, o.id DESC
        """),
        {"season": season, "week": week},
    )
    prices: dict[tuple[int, int], list[tuple[float, bool, datetime]]] = {}
    for game_id, player_id, market_prob, includes_margin, fetched_at in rows.fetchall():
        prices.setdefault((game_id, player_id), []).append((float(market_prob), bool(includes_margin), fetched_at))
    return prices


async def get_slate_matchup_context(db: AsyncSession, season: int, week: int) -> dict[int, dict]:
    """Latest game markets plus only completed pre-week team scoring context."""
    rows = await db.execute(text("""
        WITH team_games AS (
            SELECT g.id, g.home_team_id team_id, g.home_score points_for, g.away_score points_allowed
            FROM sport_games g WHERE g.sport = 'nfl' AND g.season = :season AND g.week < :week AND g.game_type = 'REG' AND g.status = 'completed'
            UNION ALL
            SELECT g.id, g.away_team_id, g.away_score, g.home_score
            FROM sport_games g WHERE g.sport = 'nfl' AND g.season = :season AND g.week < :week AND g.game_type = 'REG' AND g.status = 'completed'
        ), team_context AS (
            SELECT team_id, COUNT(*) games, COUNT(*) FILTER (WHERE points_for > points_allowed) wins,
                   COUNT(*) FILTER (WHERE points_for < points_allowed) losses,
                   AVG(points_for) points_for_per_game, AVG(points_allowed) points_allowed_per_game
            FROM team_games GROUP BY team_id
        ), latest_odds AS (
            SELECT DISTINCT ON (g.id, o.market) g.id game_id, o.book, o.market, o.line, o.first_odds, o.second_odds
            FROM sport_games g JOIN sport_game_odds o ON o.sport = 'nfl' AND o.provider = 'the_odds_api_us' AND o.game_id = g.id
            WHERE g.sport = 'nfl' AND g.season = :season AND g.week = :week AND g.game_type = 'REG'
            ORDER BY g.id, o.market, (o.book = 'draftkings') DESC, o.fetched_at DESC, o.id DESC
        )
        SELECT g.id, ml.book, ml.first_odds, ml.second_odds, sp.line, tot.line,
               aw.games, aw.wins, aw.losses, aw.points_for_per_game, aw.points_allowed_per_game,
               hm.games, hm.wins, hm.losses, hm.points_for_per_game, hm.points_allowed_per_game
        FROM sport_games g
        LEFT JOIN latest_odds ml ON ml.game_id = g.id AND ml.market = 'moneyline'
        LEFT JOIN latest_odds sp ON sp.game_id = g.id AND sp.market = 'spread'
        LEFT JOIN latest_odds tot ON tot.game_id = g.id AND tot.market = 'total'
        LEFT JOIN team_context aw ON aw.team_id = g.away_team_id
        LEFT JOIN team_context hm ON hm.team_id = g.home_team_id
        WHERE g.sport = 'nfl' AND g.season = :season AND g.week = :week AND g.game_type = 'REG'
    """), {"season": season, "week": week})
    result: dict[int, dict] = {}
    for row in rows.fetchall():
        def context(offset: int) -> dict | None:
            return None if row[offset] is None else {"games": row[offset], "wins": row[offset + 1], "losses": row[offset + 2], "points_for_per_game": float(row[offset + 3]), "points_allowed_per_game": float(row[offset + 4])}
        result[row[0]] = {"odds": None if row[1] is None else {"book": row[1], "home_moneyline": row[2], "away_moneyline": row[3], "home_spread": float(row[4]) if row[4] is not None else None, "total": float(row[5]) if row[5] is not None else None}, "away_context": context(6), "home_context": context(11)}
    return result


async def get_unmatched_slate_lines(db: AsyncSession, season: int, week: int) -> list[dict]:
    """Lines placed in this week's games but not resolved to a player.

    Surfaced rather than dropped: a line missing from the board without
    explanation looks like the provider stopped offering it.
    """
    rows = await db.execute(
        text(f"""
            WITH {_LATEST_LINES_CTE}
            SELECT l.id, l.raw_json ->> 'player_name', l.raw_json ->> 'player_team',
                   l.raw_json ->> 'player_position', l.market, l.segment, l.line,
                   l.provider, l.fetched_at, l.odds_type, l.game_id
            FROM latest_lines l
            JOIN sport_games g ON g.sport = 'nfl' AND g.id = l.game_id
            WHERE g.season = :season AND g.week = :week AND g.game_type = 'REG'
              AND l.player_id IS NULL
            ORDER BY l.raw_json ->> 'player_name', l.market, l.id
        """),
        {"season": season, "week": week},
    )
    return [
        {"id": r[0], "player_name": r[1] or "Unknown player", "provider_team": r[2],
         "provider_position": r[3], "market": r[4], "segment": r[5], "line": float(r[6]),
         "provider": r[7], "fetched_at": r[8], "odds_type": r[9], "game_id": r[10]}
        for r in rows.fetchall()
    ]


LINE_ONLY_MARKET_FILTER = "l.market IN ({})".format(", ".join(f"'{market.value}'" for market in NflLineOnlyMarket))


async def get_line_only_lines(db: AsyncSession, game_id: int) -> list[dict]:
    """Each linked full-game line-only prop on one game, at its last snapshot before kickoff (item 35).

    Partial-game lines are left out: the weekly stats that give their recent
    results are full-game totals.
    """
    rows = await db.execute(text(f"""
        SELECT DISTINCT ON (l.provider, l.provider_prop_id)
               l.player_id, p.name, p.position, l.raw_json ->> 'player_team', l.market, l.odds_type,
               l.line, l.fetched_at
        FROM sport_prop_lines l
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = l.game_id
        JOIN sport_players p ON p.sport = 'nfl' AND p.id = l.player_id
        WHERE l.sport = 'nfl' AND l.game_id = :game_id AND l.segment = 'full_game'
          AND l.fetched_at < g.start_utc AND {LINE_ONLY_MARKET_FILTER}
        ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC
    """), {"game_id": game_id})
    return [
        {"player_id": r[0], "player_name": r[1], "position": r[2], "team": r[3], "market": r[4],
         "odds_type": r[5], "line": float(r[6]), "fetched_at": r[7]}
        for r in rows.fetchall()
    ]


async def get_recent_stat_rows(
    db: AsyncSession, player_ids: list[int], season: int, week: int, limit: int = 5,
) -> list[dict]:
    """Each player's last `limit` regular-season games strictly before (season, week), newest first."""
    stat_columns = ", ".join(f"s.{column}" for column in LINE_ONLY_COLUMNS)
    rows = await db.execute(text(f"""
        SELECT player_id, season, week, opponent, {", ".join(LINE_ONLY_COLUMNS)}
        FROM (
            SELECT s.player_id, s.season, s.week, opp.team_code AS opponent, {stat_columns},
                   ROW_NUMBER() OVER (PARTITION BY s.player_id ORDER BY s.season DESC, s.week DESC) AS recency
            FROM nfl_player_weekly_stats s
            JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
            LEFT JOIN sport_teams opp ON opp.sport = 'nfl' AND opp.id = s.opponent_team_id
            WHERE s.player_id = ANY(:player_ids) AND g.game_type = 'REG'
              AND (s.season < :season OR (s.season = :season AND s.week < :week))
        ) ranked
        WHERE recency <= :limit
        ORDER BY player_id, season DESC, week DESC
    """), {"player_ids": player_ids, "season": season, "week": week, "limit": limit})
    return [dict(row) for row in rows.mappings()]


async def get_latest_prop_lines(db: AsyncSession) -> list[dict]:
    """Return the newest stored provider snapshot for each NFL player prop.

    PrizePicks identifiers do not currently map to our normalized player IDs at
    ingest time, so the provider player name retained in raw_json is the safe
    display fallback until that linking step is introduced.
    """
    rows = await db.execute(
        text("""
            SELECT DISTINCT ON (l.provider, l.provider_prop_id)
                   l.id, l.provider, l.provider_prop_id, l.market, l.line,
                   l.start_time, l.fetched_at,
                   COALESCE(p.name, l.raw_json ->> 'player_name', 'Unknown player') AS player_name,
                   p.position, l.segment, l.raw_json ->> 'league_name' AS league_name
            FROM sport_prop_lines l
            LEFT JOIN sport_players p ON p.sport = 'nfl' AND p.id = l.player_id
            WHERE l.sport = 'nfl'
            ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC
        """),
    )
    return [
        {
            "id": row[0], "provider": row[1], "provider_prop_id": row[2],
            "market": row[3], "line": float(row[4]), "start_time": row[5],
            "fetched_at": row[6], "player_name": row[7], "position": row[8],
            "segment": row[9], "league_name": row[10],
        }
        for row in rows.fetchall()
    ]


async def get_settled_prop_prices(db: AsyncSession) -> list[SettledPropRow]:
    """Every anytime-TD price stored for a completed game, with its result evidence.

    One row per player per game: the latest price per book, collapsed by the same
    median consensus the slate shows. Unresolved provider names are kept and
    keyed by name so the report can count them.
    """
    rows = await db.execute(text("""
        WITH latest AS (
            SELECT DISTINCT ON (o.game_id, o.player_id, o.provider_player_name, o.book)
                   o.game_id, o.player_id, o.provider_player_name, o.market_prob, o.includes_margin
            FROM nfl_player_prop_odds o
            JOIN sport_games g ON g.sport = 'nfl' AND g.id = o.game_id
            WHERE o.market = 'anytime_touchdown'
              AND g.game_type = 'REG' AND g.status = 'completed'
            ORDER BY o.game_id, o.player_id, o.provider_player_name, o.book,
                     o.fetched_at DESC, o.id DESC
        ), book_total AS (
            SELECT DISTINCT ON (o.game_id) o.game_id, o.line
            FROM sport_game_odds o
            WHERE o.sport = 'nfl' AND o.provider = 'the_odds_api_us' AND o.market = 'total' AND o.line IS NOT NULL
            ORDER BY o.game_id, o.fetched_at DESC, o.id DESC
        )
        SELECT l.game_id, g.season, g.week, l.player_id, l.provider_player_name,
               l.market_prob::double precision, l.includes_margin,
               bt.line::double precision, g.total_line::double precision,
               s.touchdowns, sc.offense_snaps
        FROM latest l
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = l.game_id
        LEFT JOIN book_total bt ON bt.game_id = l.game_id
        LEFT JOIN nfl_player_weekly_stats s ON s.game_id = l.game_id AND s.player_id = l.player_id
        LEFT JOIN nfl_player_snap_counts sc ON sc.game_id = l.game_id AND sc.player_id = l.player_id
        ORDER BY g.season, g.week, l.game_id, l.player_id NULLS LAST, l.provider_player_name
    """))

    grouped: dict[tuple[int, int | None, str], list] = {}
    for row in rows.fetchall():
        grouped.setdefault((row[0], row[3], row[4]), []).append(row)

    settled: list[SettledPropRow] = []
    for (game_id, player_id, provider_name), prices in grouped.items():
        price = consensus([(row[5], row[6]) for row in prices])
        if price is None:
            continue
        first = prices[0]
        book_total, nflverse_total = first[7], first[8]
        total_line = book_total if book_total is not None else nflverse_total
        settled.append(SettledPropRow(
            game_id=game_id, season=first[1], week=first[2],
            player_id=player_id, provider_player_name=provider_name,
            book_probability=price.probability, book_count=price.book_count,
            includes_margin=price.includes_margin,
            total_line=total_line,
            total_source=None if total_line is None else ("book" if book_total is not None else "nflverse"),
            touchdowns=first[9], offense_snaps=first[10],
        ))
    return settled


_GRADED_STAT_COLUMNS = (
    "passing_yards", "passing_attempts", "passing_completions", "rushing_yards",
    "rushing_attempts", "receiving_yards", "receptions", "touchdowns", "prizepicks_fantasy_points",
)


async def get_gradeable_prop_lines(db: AsyncSession, season: int, player_id: int | None = None) -> list[GradeableLine]:
    """The last pre-kickoff snapshot of every linked PrizePicks prop on a completed game.

    A snapshot taken after kickoff can already reflect the game, so it never
    counts. Stats and snaps are left-joined: a missing stat row is settled from
    snaps by the grading code, and `week_has_stats` separates a player who sat
    from a week whose stats are not loaded yet. `player_id` narrows it to one
    player's lines for the player page.
    """
    stat_columns = ", ".join(f"s.{column}" for column in _GRADED_STAT_COLUMNS)
    player_filter = "AND l.player_id = :player_id" if player_id is not None else ""
    params: dict[str, object] = {"season": season}
    if player_id is not None:
        params["player_id"] = player_id
    rows = await db.execute(
        text(f"""
            WITH latest AS (
                SELECT DISTINCT ON (l.provider, l.provider_prop_id)
                       l.id, l.market, l.segment, l.odds_type, l.line, l.fetched_at, l.player_id, l.game_id
                FROM sport_prop_lines l
                JOIN sport_games g ON g.sport = 'nfl' AND g.id = l.game_id
                WHERE l.sport = 'nfl' AND g.season = :season AND g.game_type = 'REG' AND g.status = 'completed'
                  AND l.player_id IS NOT NULL AND l.provider_prop_id IS NOT NULL
                  AND l.fetched_at < g.start_utc {player_filter} AND {MODELLED_MARKET_FILTER}
                ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC
            ),
            loaded_weeks AS (
                SELECT DISTINCT season, week FROM nfl_player_weekly_stats WHERE season = :season
            )
            SELECT latest.id, g.season, g.week, latest.game_id, latest.player_id, latest.market,
                   latest.segment, latest.odds_type, latest.line, latest.fetched_at,
                   {stat_columns}, sc.offense_snaps, lw.week IS NOT NULL AS week_has_stats
            FROM latest
            JOIN sport_games g ON g.sport = 'nfl' AND g.id = latest.game_id
            LEFT JOIN nfl_player_weekly_stats s ON s.player_id = latest.player_id AND s.game_id = latest.game_id
            LEFT JOIN nfl_player_snap_counts sc ON sc.player_id = latest.player_id AND sc.game_id = latest.game_id
            LEFT JOIN loaded_weeks lw ON lw.season = g.season AND lw.week = g.week
            ORDER BY g.week, latest.id
        """),
        params,
    )
    return [_gradeable_line(row) for row in rows.mappings()]


def _gradeable_line(row: RowMapping) -> GradeableLine:
    # StrEnum keys match the stored market string directly; an unknown market has no stat.
    column = STAT_COLUMN_BY_MARKET.get(row["market"])
    value = row[column] if column is not None else None
    return GradeableLine(
        line_id=row["id"], season=row["season"], week=row["week"], game_id=row["game_id"],
        player_id=row["player_id"], market=row["market"], segment=row["segment"], odds_type=row["odds_type"],
        line=float(row["line"]), fetched_at=row["fetched_at"],
        stat_value=float(value) if value is not None else None,
        offense_snaps=row["offense_snaps"], week_has_stats=bool(row["week_has_stats"]),
    )


async def get_frozen_gradeable_lines(db: AsyncSession, season: int) -> list[FrozenLine]:
    """The latest frozen pre-kickoff prediction of every linked PrizePicks prop on a completed game.

    Graded at the line it was frozen on (27j), not the newest snapshot 27a grades:
    a snapshot taken after the last freeze would otherwise throw away a real
    pre-kickoff prediction for the same prop.
    """
    stat_columns = ", ".join(f"s.{column}" for column in _GRADED_STAT_COLUMNS)
    rows = await db.execute(
        text(f"""
            WITH frozen AS (
                SELECT DISTINCT ON (l.provider, l.provider_prop_id)
                       l.id, l.market, l.segment, l.odds_type, l.line, l.fetched_at, l.player_id, l.game_id,
                       p.p_over, p.p_under, p.model_version, p.over_probability_version
                FROM sport_prop_predictions p
                JOIN sport_prop_lines l ON l.sport = 'nfl' AND l.id = p.prop_line_id
                JOIN sport_games g ON g.sport = 'nfl' AND g.id = l.game_id
                WHERE p.sport = 'nfl' AND g.season = :season AND g.game_type = 'REG' AND g.status = 'completed'
                  AND l.player_id IS NOT NULL AND l.provider_prop_id IS NOT NULL
                  AND l.fetched_at < g.start_utc AND p.generated_at < g.start_utc
                ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC, p.generated_at DESC, p.id DESC
            ),
            loaded_weeks AS (
                SELECT DISTINCT season, week FROM nfl_player_weekly_stats WHERE season = :season
            )
            SELECT frozen.id, g.season, g.week, frozen.game_id, frozen.player_id, frozen.market,
                   frozen.segment, frozen.odds_type, frozen.line, frozen.fetched_at,
                   {stat_columns}, sc.offense_snaps, lw.week IS NOT NULL AS week_has_stats,
                   frozen.p_over, frozen.p_under, frozen.model_version, frozen.over_probability_version
            FROM frozen
            JOIN sport_games g ON g.sport = 'nfl' AND g.id = frozen.game_id
            LEFT JOIN nfl_player_weekly_stats s ON s.player_id = frozen.player_id AND s.game_id = frozen.game_id
            LEFT JOIN nfl_player_snap_counts sc ON sc.player_id = frozen.player_id AND sc.game_id = frozen.game_id
            LEFT JOIN loaded_weeks lw ON lw.season = g.season AND lw.week = g.week
            ORDER BY g.week, frozen.id
        """),
        {"season": season},
    )
    return [_frozen_line(row) for row in rows.mappings()]


def _frozen_line(row: RowMapping) -> FrozenLine:
    line = _gradeable_line(row)
    return FrozenLine(
        line_id=line.line_id, period=line.week, player_id=line.player_id, game_id=line.game_id, market=line.market,
        odds_type=line.odds_type, outcome=settle_line(line).outcome, p_over=row["p_over"], p_under=row["p_under"],
        model_version=row["model_version"], over_probability_version=row["over_probability_version"],
    )


async def get_finished_weeks(db: AsyncSession, season: int) -> set[int]:
    """Weeks whose regular-season games are all completed."""
    rows = await db.execute(text("""
        SELECT week FROM sport_games
        WHERE sport = 'nfl' AND season = :season AND game_type = 'REG'
        GROUP BY week HAVING bool_and(status = 'completed')
    """), {"season": season})
    return {row[0] for row in rows.fetchall()}


async def get_frozen_coverage(db: AsyncSession, season: int) -> dict[int, tuple[int, int]]:
    """Per week: (27a's gradeable full-game lines, how many of their provider props have any frozen row).

    Per week because weeks before freezing began (27i) are wholly unfrozen by
    construction, which a season total would blur into the real gaps.
    """
    rows = await db.execute(text(f"""
        WITH latest AS (
            SELECT DISTINCT ON (l.provider, l.provider_prop_id) l.provider, l.provider_prop_id, g.week
            FROM sport_prop_lines l
            JOIN sport_games g ON g.sport = 'nfl' AND g.id = l.game_id
            WHERE l.sport = 'nfl' AND g.season = :season AND g.game_type = 'REG' AND g.status = 'completed'
              AND l.player_id IS NOT NULL AND l.provider_prop_id IS NOT NULL
              AND l.fetched_at < g.start_utc AND l.segment = 'full_game' AND {MODELLED_MARKET_FILTER}
            ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC
        )
        SELECT latest.week, COUNT(*),
               COUNT(*) FILTER (WHERE EXISTS (
                   SELECT 1 FROM sport_prop_lines fl
                   JOIN sport_prop_predictions p ON p.sport = 'nfl' AND p.prop_line_id = fl.id
                   JOIN sport_games g ON g.sport = 'nfl' AND g.id = fl.game_id
                   WHERE fl.sport = 'nfl' AND fl.provider = latest.provider AND fl.provider_prop_id = latest.provider_prop_id
                     AND fl.fetched_at < g.start_utc AND p.generated_at < g.start_utc
               ))
        FROM latest
        GROUP BY latest.week ORDER BY latest.week
    """), {"season": season})
    return {week: (int(lines), int(frozen)) for week, lines, frozen in rows.fetchall()}


# The week's played QB/RB/WR/TE games crossed with their positions' markets,
# shaped like stored lines so `_slate_line_rows` projects them unchanged. The id
# is stable per player-game and market; the line is a placeholder never graded.
_REPLAY_LINES_CTE = """
    latest_lines AS (
        SELECT s.id * 32 + m.ordinal AS id, 'replay' AS provider, m.market, 'full_game' AS segment,
               0::numeric AS line, g.start_utc AS start_time, g.start_utc AS fetched_at,
               s.player_id, s.game_id, 'standard' AS odds_type, NULL::jsonb AS raw_json
        FROM nfl_player_weekly_stats s
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
        JOIN sport_players p ON p.sport = 'nfl' AND p.id = s.player_id
        JOIN unnest(CAST(:replay_positions AS text[]), CAST(:replay_markets AS text[]))
             WITH ORDINALITY AS m(position, market, ordinal) ON m.position = p.position
        WHERE g.season = :season AND g.week = :week AND g.game_type = 'REG'
    )
"""


async def get_environment_fit_games(db: AsyncSession, season: int) -> list[NflEnvironmentGame]:
    """Every rated position's player-game in a season's REG games with both closing lines."""
    stat_columns = ", ".join(f"s.{column}" for column in _GRADED_STAT_COLUMNS)
    rows = await db.execute(
        text(f"""
            SELECT s.player_id, p.position, {stat_columns},
                   ((g.total_line + {_TEAM_MARGIN}) / 2)::double precision AS team_total,
                   ({_TEAM_MARGIN})::double precision AS team_margin, g.roof, g.wind
            FROM nfl_player_weekly_stats s
            JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
            JOIN sport_players p ON p.sport = 'nfl' AND p.id = s.player_id
            WHERE g.season = :season AND g.game_type = 'REG' AND {_LINES_FILTER}
              AND p.position = ANY(CAST(:positions AS text[]))
        """),
        {"season": season, "positions": sorted(REPLAY_MARKETS_BY_POSITION)},
    )
    return [
        NflEnvironmentGame(
            player_id=row["player_id"], position=row["position"],
            team_total=row["team_total"], team_margin=row["team_margin"], roof=row["roof"], wind=row["wind"],
            stats={
                market.value: float(row[column]) if row[column] is not None else None
                for market, column in STAT_COLUMN_BY_MARKET.items()
            },
        )
        for row in rows.mappings()
    ]


def _closing_game_lines(spread_line: float | None, total_line: float | None) -> dict | None:
    if spread_line is None or total_line is None:
        return None
    return {"home_spread_margin": float(spread_line), "total": float(total_line)}


async def get_replay_rows(db: AsyncSession, season: int, week: int) -> list[ReplayRow]:
    """Every rated position's player-game this week, projected as the slate would, with the result."""
    pairs = [(position, market) for position, markets in REPLAY_MARKETS_BY_POSITION.items() for market in markets]
    rows = await _slate_line_rows(db, season, week, _REPLAY_LINES_CTE, {
        "replay_positions": [position for position, _ in pairs],
        "replay_markets": [market for _, market in pairs],
    })
    stat_columns = ", ".join(f"s.{column}" for column in _GRADED_STAT_COLUMNS)
    outcomes = await db.execute(
        text(f"""
            SELECT s.player_id, s.game_id, {stat_columns}, g.home_moneyline, g.away_moneyline,
                   g.spread_line::double precision, g.total_line::double precision, g.roof, g.wind
            FROM nfl_player_weekly_stats s
            JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
            WHERE g.season = :season AND g.week = :week AND g.game_type = 'REG'
        """),
        {"season": season, "week": week},
    )
    by_player_game = {(row["player_id"], row["game_id"]): row for row in outcomes.mappings()}
    team_game_totals = await get_team_game_position_totals(db, season, week)
    league = league_averages(team_game_totals)
    replay = []
    for row in rows:
        outcome = by_player_game.get((row["player_id"], row["game_id"]))
        column = STAT_COLUMN_BY_MARKET.get(row["market"])
        if outcome is None or column is None or outcome[column] is None:
            continue
        row = row | team_game_inputs(team_game_totals, league, row.get("opponent_team_id"), row["position"]) | {
            "game_lines": _closing_game_lines(outcome["spread_line"], outcome["total_line"]),
            "game_weather": {"roof": outcome["roof"], "wind": outcome["wind"]},
        }
        replay.append(ReplayRow(
            row=row, actual=float(outcome[column]),
            home_market_prob=market_home_probability(outcome["home_moneyline"], outcome["away_moneyline"]),
        ))
    return replay


async def get_player_profile(db: AsyncSession, player_id: int, season: int, week: int) -> dict | None:
    """One player's identity as of the week: team by the roster rule, depth, injury, aliases, stats loaded."""
    rows = await db.execute(
        text(f"""
            WITH {_player_teams_cte()}
            SELECT p.id, p.name, p.position, t.team_code,
                   d.position AS depth_position, d.depth_rank,
                   i.report_status, i.practice_status, i.primary_injury,
                   ARRAY(SELECT a.alias_name FROM sport_player_aliases a
                         WHERE a.sport = 'nfl' AND a.player_id = p.id ORDER BY a.alias_name) AS aliases,
                   loaded.season AS stats_season, loaded.week AS stats_week
            FROM sport_players p
            LEFT JOIN player_teams pt ON pt.player_id = p.id
            LEFT JOIN sport_teams t ON t.sport = 'nfl' AND t.id = pt.team_id
            LEFT JOIN nfl_player_depth_charts d ON d.player_id = p.id AND d.season = :season AND d.week = :week
            LEFT JOIN nfl_player_injuries i ON i.player_id = p.id AND i.season = :season AND i.week = :week
            LEFT JOIN LATERAL (
                SELECT season, week FROM nfl_player_weekly_stats ORDER BY season DESC, week DESC LIMIT 1
            ) loaded ON TRUE
            WHERE p.sport = 'nfl' AND p.id = :player_id
        """),
        {"player_id": player_id, "season": season, "week": week},
    )
    row = next(iter(rows.mappings()), None)
    return dict(row) if row is not None else None


async def get_player_game_rows(db: AsyncSession, player_id: int, season: int) -> list[PlayerGameRow]:
    """The player's completed regular-season games this season and last, newest first.

    Home, score and spread read from the stat row's own team, so a traded
    player's earlier games show the team he played for then.
    """
    rows = await db.execute(
        text("""
            SELECT g.id AS game_id, g.season, g.week, opponent.team_code AS opponent,
                   s.team_id = g.home_team_id AS is_home,
                   CASE WHEN s.team_id = g.home_team_id THEN g.home_score ELSE g.away_score END AS team_score,
                   CASE WHEN s.team_id = g.home_team_id THEN g.away_score ELSE g.home_score END AS opponent_score,
                   CASE WHEN s.team_id = g.home_team_id THEN -g.spread_line ELSE g.spread_line END AS team_spread,
                   g.roof, sc.offense_pct AS snap_pct,
                   s.passing_completions, s.passing_attempts, s.passing_yards, s.rushing_attempts, s.rushing_yards,
                   s.targets, s.receptions, s.receiving_yards, s.touchdowns, s.prizepicks_fantasy_points
            FROM nfl_player_weekly_stats s
            JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
            LEFT JOIN sport_teams opponent
                   ON opponent.sport = 'nfl' AND opponent.id = CASE WHEN s.team_id = g.home_team_id THEN g.away_team_id ELSE g.home_team_id END
            LEFT JOIN nfl_player_snap_counts sc ON sc.player_id = s.player_id AND sc.game_id = s.game_id
            WHERE s.player_id = :player_id AND g.game_type = 'REG' AND g.status = 'completed'
              AND g.season IN (:season, :previous_season)
            ORDER BY g.season DESC, g.week DESC, g.id DESC
        """),
        {"player_id": player_id, "season": season, "previous_season": season - 1},
    )
    return [_player_game_row(row) for row in rows.mappings()]


def _player_game_row(row: RowMapping) -> PlayerGameRow:
    return PlayerGameRow(
        game_id=row["game_id"], season=row["season"], week=row["week"], opponent=row["opponent"] or "--",
        is_home=bool(row["is_home"]), team_score=row["team_score"], opponent_score=row["opponent_score"],
        team_spread=_optional_float(row["team_spread"]), roof=row["roof"], snap_pct=_optional_float(row["snap_pct"]),
        passing_completions=row["passing_completions"], passing_attempts=row["passing_attempts"],
        passing_yards=row["passing_yards"], rushing_attempts=row["rushing_attempts"],
        rushing_yards=row["rushing_yards"], targets=row["targets"], receptions=row["receptions"],
        receiving_yards=row["receiving_yards"], touchdowns=row["touchdowns"],
        prizepicks_fantasy_points=_optional_float(row["prizepicks_fantasy_points"]),
    )
