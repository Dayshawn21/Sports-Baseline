"""Read-only pre-week Rec Targets inputs for the development replay."""
from __future__ import annotations

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_game_lines import market_home_probability
from app.core.nfl_targets_projection import TargetsObservation, TargetsProjectionInput, TargetsReplayRow
from app.repositories.nfl import _player_teams_cte

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


async def _get_history(
    db: AsyncSession, season: int, week: int, player_ids: list[int],
) -> dict[int, tuple[TargetsObservation, ...]]:
    result = await db.execute(text("""
        SELECT s.player_id, s.game_id, g.season, g.week, g.start_utc,
               s.targets::double precision AS targets
        FROM nfl_player_weekly_stats s
        JOIN sport_games g ON g.sport = 'nfl' AND g.id = s.game_id
        WHERE s.player_id = ANY(CAST(:player_ids AS bigint[]))
          AND g.game_type = 'REG' AND g.status = 'completed'
          AND (g.season < :season OR (g.season = :season AND g.week < :week))
        ORDER BY s.player_id, g.season DESC, g.week DESC,
                 g.start_utc DESC NULLS LAST, g.id DESC
    """), {"season": season, "week": week, "player_ids": player_ids})
    by_player: dict[int, list[TargetsObservation]] = {}
    for row in result.mappings():
        by_player.setdefault(row["player_id"], []).append(TargetsObservation(
            game_id=row["game_id"], season=row["season"], week=row["week"], start_utc=row["start_utc"],
            targets=float(row["targets"]) if row["targets"] is not None else None,
        ))
    return {player_id: tuple(history) for player_id, history in by_player.items()}


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
