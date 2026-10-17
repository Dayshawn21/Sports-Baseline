"""Defense-versus-position from per-game position totals (build-plan item 27c).

A defense's allowance is what one position gained against it in a whole game,
summed across that position's players, so a game counts once however many
receivers played in it.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.nfl_projection import TEAM_GAME_DVP_MARKETS
from app.nfl.markets import NflPropMarket


@dataclass(frozen=True)
class NflTeamGameTotals:
    game_id: int
    season: int
    week: int
    passing_yards: float
    passing_attempts: float
    passing_completions: float
    rushing_yards: float
    rushing_attempts: float
    receiving_yards: float
    receptions: float
    touchdowns: float
    fantasy_points: float | None


# One regular season. Fixed before 27c was scored, not fitted: early in a season
# the window reaches back into the previous one instead of trusting a few games.
DVP_TEAM_GAME_WINDOW = 17

_COUNT_FIELDS = (
    "passing_yards", "passing_attempts", "passing_completions", "rushing_yards",
    "rushing_attempts", "receiving_yards", "receptions", "touchdowns",
)


def _mean_averages(games: list[NflTeamGameTotals]) -> dict | None:
    """The team-games' means in the shape `NflHistoricalAverages(**...)` accepts."""
    if not games:
        return None
    fantasy = [game.fantasy_points for game in games if game.fantasy_points is not None]
    return {
        "games": len(games),
        **{field: sum(getattr(game, field) for game in games) / len(games) for field in _COUNT_FIELDS},
        "fantasy_points": sum(fantasy) / len(fantasy) if fantasy else None,
    }


def window_averages(totals: list[NflTeamGameTotals], window: int = DVP_TEAM_GAME_WINDOW) -> dict | None:
    """Mean of a defense's newest `window` team-games at one position; totals arrive newest first."""
    return _mean_averages(totals[:window])


def league_averages(
    totals_by_key: dict[tuple[int, str], list[NflTeamGameTotals]], window: int = DVP_TEAM_GAME_WINDOW,
) -> dict[str, dict]:
    """Per position, the mean over every defense's windowed team-games pooled.

    Pooling the same windows the defenses are rated on keeps the ratio centered:
    the league reference is exactly what an average defense's window allowed.
    """
    pooled: dict[str, list[NflTeamGameTotals]] = {}
    for (_, position), totals in totals_by_key.items():
        pooled.setdefault(position, []).extend(totals[:window])
    return {position: averages for position, games in pooled.items() if (averages := _mean_averages(games))}


def team_game_inputs(
    totals_by_key: dict[tuple[int, str], list[NflTeamGameTotals]], league: dict[str, dict],
    defense_team_id: int | None, position: str | None,
) -> dict[str, dict | None]:
    """A line's team-game opponent and league averages, keyed as replay and slate rows carry them."""
    opponent = None
    if defense_team_id is not None and position is not None:
        opponent = window_averages(totals_by_key.get((defense_team_id, position), []))
    return {
        "team_game_opponent_averages": opponent,
        "team_game_league_averages": league.get(position) if position is not None else None,
    }


def apply_team_game_dvp(row: dict) -> dict:
    """The row with team-game DVP swapped in when its market adopted it; otherwise the row itself."""
    if NflPropMarket(row["market"]) not in TEAM_GAME_DVP_MARKETS:
        return row
    return {
        **row,
        "opponent_averages": row["team_game_opponent_averages"],
        "league_position_averages": row["team_game_league_averages"],
    }
