"""NFL fantasy scoring: documented PPR for ESPN-derived baselines, and PrizePicks' formula."""
from __future__ import annotations

from dataclasses import dataclass


def ppr_fantasy_points(passing_yards: int, passing_tds: int, interceptions: int, rushing_yards: int, rushing_tds: int, receiving_yards: int, receiving_tds: int, receptions: int) -> float:
    return round(passing_yards / 25 + passing_tds * 4 - interceptions * 2 + rushing_yards / 10 + rushing_tds * 6 + receiving_yards / 10 + receiving_tds * 6 + receptions, 2)


@dataclass(frozen=True)
class NflFantasyComponents:
    passing_yards: int
    passing_tds: int
    interceptions: int
    rushing_yards: int
    receiving_yards: int
    touchdowns: int  # rushing plus receiving, both worth 6
    receptions: int
    fumbles_lost: int
    two_point_conversions: int
    return_tds: int
    fumble_recovery_tds: int


def _shared_points(c: NflFantasyComponents) -> float:
    return (
        c.passing_yards / 25 + c.passing_tds * 4 + c.rushing_yards / 10 + c.receiving_yards / 10
        + c.touchdowns * 6 + c.receptions + c.two_point_conversions * 2 + c.return_tds * 6
    )


def nflverse_ppr_points(c: NflFantasyComponents) -> float:
    """NFLverse `fantasy_points_ppr`, rebuilt from components to prove they are complete."""
    return round(_shared_points(c) - c.interceptions * 2 - c.fumbles_lost * 2, 2)


def prizepicks_fantasy_points(c: NflFantasyComponents) -> float:
    # https://www.prizepicks.com/playbook-article/how-to-play-prizepicks-nfl-fantasy-scoring-system
    # (2025-09-17): -1 per interception and lost fumble, +6 per offensive fumble-recovery TD.
    return round(_shared_points(c) - c.interceptions - c.fumbles_lost + c.fumble_recovery_tds * 6, 2)


_AVERAGES_KEYS = ("averages", "position_averages", "opponent_averages", "league_position_averages")


def _prizepicks_averages(averages: dict | None) -> dict | None:
    if averages is None:
        return None
    return {**averages, "fantasy_points": averages.get("prizepicks_fantasy_points")}


def apply_prizepicks_fantasy(row: dict) -> dict:
    """Project a fantasy line from PrizePicks points instead of NFLverse PPR (the 27f arm).

    Team-game DVP inputs keep PPR: 27c rejected them for fantasy, so nothing reads them here.
    """
    if row["market"] != "fantasy_points":
        return row
    seasons = {
        season: {**values, **{key: _prizepicks_averages(values[key]) for key in ("averages", "position_averages")}}
        for season, values in row["baseline_seasons"].items()
    }
    return {
        **row,
        **{key: _prizepicks_averages(row.get(key)) for key in _AVERAGES_KEYS},
        "baseline_seasons": seasons,
    }
