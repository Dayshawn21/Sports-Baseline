"""Read-only pre-week Rec Targets inputs for serving and development replay."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_availability import NflAvailability
from app.core.nfl_baseline import PROJECTION_FIRST_HISTORY_SEASON
from app.core.nfl_game_lines import market_home_probability
from app.core.nfl_targets_projection import TargetsObservation, TargetsProjectionInput, TargetsReplayRow
from app.repositories.nfl import _AVAILABILITY_COLUMNS, _AVAILABILITY_CTE, _player_teams_cte


@dataclass(frozen=True)
class TargetsHistoryGame:
    observation: TargetsObservation
    opponent_team_id: int | None
    opponent_team: str | None


@dataclass(frozen=True)
class TargetsServingLine:
    line_id: int
    game_id: int
    player_id: int
    player_name: str
    position: str
    player_team_id: int | None
    opponent_team_id: int | None
    opponent_team: str | None
    start_utc: datetime | None
    market: str
    segment: str
    odds_type: str
    line: float | None
    provider: str
    fetched_at: datetime
    input: TargetsProjectionInput
    history: tuple[TargetsHistoryGame, ...]
    availability: NflAvailability
    practice_status: str | None
    injury: str | None


@dataclass(frozen=True)
class TargetsUnmatchedLine:
    line_id: int
    game_id: int
    player_name: str
    provider_team: str | None
    provider_position: str | None
    market: str
    segment: str
    odds_type: str
    line: float
    provider: str
    fetched_at: datetime


_LATEST_TARGETS_LINES_CTE = """
    latest_targets_lines AS (
        SELECT DISTINCT ON (l.provider, l.provider_prop_id)
               l.id, l.game_id, l.player_id, p.name AS player_name, p.position,
               l.market, l.segment, l.odds_type, l.line, l.provider, l.fetched_at, l.raw_json,
               g.start_utc, g.home_team_id, g.away_team_id
        FROM sport_prop_lines l
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = l.game_id
        LEFT JOIN sport_players p ON p.sport = 'nfl' AND p.id = l.player_id
        WHERE l.sport = 'nfl' AND l.market = 'receiving_targets'
          AND g.season = :season AND g.week = :week AND g.week BETWEEN 1 AND 18
          AND g.game_type = 'REG' AND l.segment = 'full_game' AND l.odds_type = 'standard'
          AND l.provider_prop_id IS NOT NULL
          AND (l.player_id IS NULL OR p.position IN ('RB', 'WR', 'TE'))
          AND (g.start_utc IS NULL OR l.fetched_at < g.start_utc)
        ORDER BY l.provider, l.provider_prop_id, l.fetched_at DESC, l.id DESC
    )
"""

_SERVING_SQL = f"""
    WITH {_LATEST_TARGETS_LINES_CTE}, {_player_teams_cte()}, {_AVAILABILITY_CTE}
    SELECT l.*, pt.team_id AS player_team_id,
           CASE
               WHEN pt.team_id = l.home_team_id THEN l.away_team_id
               WHEN pt.team_id = l.away_team_id THEN l.home_team_id
           END AS opponent_team_id,
           CASE
               WHEN pt.team_id = l.home_team_id THEN away.team_code
               WHEN pt.team_id = l.away_team_id THEN home.team_code
           END AS opponent_team,
           {_AVAILABILITY_COLUMNS}
    FROM latest_targets_lines l
    LEFT JOIN player_teams pt ON pt.player_id = l.player_id
    JOIN sport_teams home ON home.sport = 'nfl' AND home.id = l.home_team_id
    JOIN sport_teams away ON away.sport = 'nfl' AND away.id = l.away_team_id
    LEFT JOIN week_injuries wi ON wi.player_id = l.player_id
    LEFT JOIN week_depth wd ON wd.player_id = l.player_id
    LEFT JOIN previous_depth pd ON pd.player_id = l.player_id
    WHERE l.player_id IS NOT NULL
    ORDER BY l.player_name, l.line, l.id
"""

_REPLAY_SQL = f"""
    WITH {_player_teams_cte()}
    SELECT s.player_id, s.game_id, g.week, p.position,
           s.targets::double precision AS actual,
           g.home_moneyline, g.away_moneyline,
           CASE
               WHEN pt.team_id = g.home_team_id THEN TRUE
               WHEN pt.team_id = g.away_team_id THEN FALSE
               ELSE NULL
           END AS player_is_home
    FROM nfl_player_weekly_stats s
    JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
    JOIN sport_players p ON p.sport = 'nfl' AND p.id = s.player_id
    JOIN player_teams pt ON pt.player_id = p.id
    WHERE g.season = :season AND g.week = :week
      AND g.game_type = 'REG' AND g.status = 'completed'
      AND p.position IN ('RB', 'WR', 'TE')
    ORDER BY g.id, s.player_id
"""


async def _get_history_with_opponents(
    db: AsyncSession, season: int, week: int, player_ids: list[int],
) -> dict[int, tuple[TargetsHistoryGame, ...]]:
    result = await db.execute(text("""
        SELECT s.player_id, s.game_id, g.season, g.week, g.start_utc,
               s.targets::double precision AS targets, s.opponent_team_id,
               opponent.team_code AS opponent_team
        FROM nfl_player_weekly_stats s
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
        LEFT JOIN sport_teams opponent ON opponent.sport = 'nfl' AND opponent.id = s.opponent_team_id
        WHERE s.player_id = ANY(CAST(:player_ids AS bigint[]))
          AND g.game_type = 'REG' AND g.status = 'completed' AND g.season >= :first_history_season
          AND (g.season < :season OR (g.season = :season AND g.week < :week))
        ORDER BY s.player_id, g.season DESC, g.week DESC,
                 g.start_utc DESC NULLS LAST, g.id DESC
    """), {
        "season": season, "week": week, "player_ids": player_ids,
        "first_history_season": PROJECTION_FIRST_HISTORY_SEASON,
    })
    by_player: dict[int, list[TargetsHistoryGame]] = {}
    for row in result.mappings():
        by_player.setdefault(row["player_id"], []).append(TargetsHistoryGame(
            observation=TargetsObservation(
                game_id=row["game_id"], season=row["season"], week=row["week"], start_utc=row["start_utc"],
                targets=float(row["targets"]) if row["targets"] is not None else None,
            ),
            opponent_team_id=row.get("opponent_team_id"), opponent_team=row.get("opponent_team"),
        ))
    return {player_id: tuple(history) for player_id, history in by_player.items()}


async def _get_history(
    db: AsyncSession, season: int, week: int, player_ids: list[int],
) -> dict[int, tuple[TargetsObservation, ...]]:
    history = await _get_history_with_opponents(db, season, week, player_ids)
    return {player_id: tuple(game.observation for game in games) for player_id, games in history.items()}


def _serving_row(
    row: RowMapping, season: int, week: int, history: tuple[TargetsHistoryGame, ...],
) -> TargetsServingLine:
    return TargetsServingLine(
        line_id=row["id"], game_id=row["game_id"], player_id=row["player_id"], player_name=row["player_name"],
        position=row["position"], player_team_id=row["player_team_id"],
        opponent_team_id=row["opponent_team_id"], opponent_team=row["opponent_team"], start_utc=row["start_utc"],
        market=row["market"], segment=row["segment"], odds_type=row["odds_type"],
        line=float(row["line"]) if row["line"] is not None else None,
        provider=row["provider"], fetched_at=row["fetched_at"],
        input=TargetsProjectionInput(season, week, tuple(game.observation for game in history)), history=history,
        availability=NflAvailability(
            injury_status=row["injury_status"], depth_team_id=row["depth_team_id"],
            depth_position=row["depth_position"], depth_rank=row["depth_rank"],
            previous_depth_team_id=row["previous_depth_team_id"],
            previous_depth_position=row["previous_depth_position"], previous_depth_rank=row["previous_depth_rank"],
        ),
        practice_status=row["practice_status"], injury=row["injury"],
    )


async def get_targets_serving_lines(db: AsyncSession, season: int, week: int) -> list[TargetsServingLine]:
    """Eligible stored lines with batched pre-week history, independent of the game's outcome."""
    result = await db.execute(text(_SERVING_SQL), {"season": season, "week": week})
    rows = list(result.mappings())
    if not rows:
        return []
    player_ids = sorted({row["player_id"] for row in rows})
    history = await _get_history_with_opponents(db, season, week, player_ids)
    return [_serving_row(row, season, week, history.get(row["player_id"], ())) for row in rows]


async def get_unmatched_targets_lines(db: AsyncSession, season: int, week: int) -> list[TargetsUnmatchedLine]:
    """Eligible lines linked to this week's games but unresolved to a player."""
    result = await db.execute(text(f"""
        WITH {_LATEST_TARGETS_LINES_CTE}
        SELECT id, game_id, raw_json ->> 'player_name' AS player_name,
               raw_json ->> 'player_team' AS provider_team, raw_json ->> 'player_position' AS provider_position,
               market, segment, odds_type, line, provider, fetched_at
        FROM latest_targets_lines
        WHERE player_id IS NULL
        ORDER BY player_name, market, id
    """), {"season": season, "week": week})
    return [TargetsUnmatchedLine(
        line_id=row["id"], game_id=row["game_id"], player_name=row["player_name"] or "Unknown player",
        provider_team=row["provider_team"], provider_position=row["provider_position"],
        market=row["market"], segment=row["segment"], odds_type=row["odds_type"], line=float(row["line"]),
        provider=row["provider"], fetched_at=row["fetched_at"],
    ) for row in result.mappings()]


def _replay_row(row: RowMapping, season: int, history: tuple[TargetsObservation, ...]) -> TargetsReplayRow:
    return TargetsReplayRow(
        player_id=row["player_id"], game_id=row["game_id"], week=row["week"], position=row["position"],
        input=TargetsProjectionInput(
            season=season, week=row["week"], observations=history,
            home_market_prob=market_home_probability(row["home_moneyline"], row["away_moneyline"]),
            player_is_home=row["player_is_home"],
        ),
        actual=float(row["actual"]) if row["actual"] is not None else None,
    )


async def get_targets_replay_rows(db: AsyncSession, season: int, week: int) -> list[TargetsReplayRow]:
    """Completed RB/WR/TE player-games with separate outcomes and pre-week history."""
    result = await db.execute(text(_REPLAY_SQL), {"season": season, "week": week})
    rows = list(result.mappings())
    if not rows:
        return []
    player_ids = sorted({row["player_id"] for row in rows})
    history = await _get_history(db, season, week, player_ids)
    return [_replay_row(row, season, history.get(row["player_id"], ())) for row in rows]
