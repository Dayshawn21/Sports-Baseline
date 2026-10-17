"""Blend the current and previous season into one baseline (build-plan item 27d).

The season switch in `choose_baseline_season` drops all of last season the week
a player reaches four games this season. The blend weights each season by its
games instead, with last season's games discounted, so the current season takes
over gradually.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from app.core.nfl_baseline import CURRENT_PREVIOUS_BLEND
from app.core.nfl_projection import SEASON_BLEND_MARKETS
from app.nfl.markets import NflPropMarket

# Last season counts at the same discount anytime TD already gives it
# (TD_SEASON_WEIGHTS[1]); fixed before scoring, not fitted to 2025.
PREVIOUS_SEASON_WEIGHT = 0.6

_STATS = (
    "passing_yards", "passing_attempts", "passing_completions", "rushing_yards",
    "rushing_attempts", "receiving_yards", "receptions", "touchdowns",
)
_USAGE_STATS = ("targets", "target_share")


def _weighted(values: list[tuple[float, float]]) -> float:
    total = sum(weight for _, weight in values)
    return sum(value * weight for value, weight in values) / total


def _blend_dicts(current: dict, previous: dict, current_weight: float, previous_weight: float) -> dict:
    """Averages in the `_averages` shape, weighted per season; `games` is the raw sum."""
    blended = {
        stat: _weighted([(current[stat], current_weight), (previous[stat], previous_weight)])
        for stat in _STATS
    }
    fantasy = [
        (season["fantasy_points"], weight)
        for season, weight in ((current, current_weight), (previous, previous_weight))
        if season["fantasy_points"] is not None
    ]
    blended["fantasy_points"] = _weighted(fantasy) if fantasy else None
    blended["games"] = current["games"] + previous["games"]
    return blended


def blend_averages(current: dict, previous: dict, weight: float = PREVIOUS_SEASON_WEIGHT) -> dict:
    return _blend_dicts(current, previous, current["games"], weight * previous["games"])


def _blend_usage(current: dict | None, previous: dict | None, current_weight: float, previous_weight: float) -> dict | None:
    if current is None or previous is None:
        return current or previous
    blended = {
        stat: _weighted([(current[stat], current_weight), (previous[stat], previous_weight)])
        for stat in _USAGE_STATS
    }
    blended["games"] = current["games"] + previous["games"]
    return blended


def blend_usage(current: dict | None, previous: dict | None, weight: float = PREVIOUS_SEASON_WEIGHT) -> dict | None:
    """Usage weighted by each season's usage games, which can be fewer than its stat games."""
    if current is None or previous is None:
        return current or previous
    return _blend_usage(current, previous, current["games"], weight * previous["games"])


def _blend_environment(current: dict | None, previous: dict | None, weight: float) -> dict | None:
    """Mean team total and margin weighted by each season's games with lines, raw-sum games."""
    if current is None or previous is None:
        return current or previous
    current_weight, previous_weight = current["games"], weight * previous["games"]
    return {
        "games": current["games"] + previous["games"],
        "team_total": _weighted([(current["team_total"], current_weight), (previous["team_total"], previous_weight)]),
        "team_margin": _weighted([(current["team_margin"], current_weight), (previous["team_margin"], previous_weight)]),
    }


def season_blend_inputs(baseline_seasons: dict[int, dict], line_season: int) -> dict | None:
    """Blended `averages`, `position_averages`, `usage`, `position_usage` and `environment` for a line.

    "Previous" is the most recent earlier season with games, so a player who
    missed a year blends with the last season they played. None unless both
    seasons exist: with one, `choose_baseline_season` already picks it, and it
    also knows to skip a thin last season for a full one before it.
    """
    played = {season: entry for season, entry in baseline_seasons.items() if entry["averages"]["games"] > 0}
    current = played.get(line_season)
    earlier = [season for season in played if season < line_season]
    if current is None or not earlier:
        return None
    previous = played[max(earlier)]
    current_weight = current["averages"]["games"]
    previous_weight = PREVIOUS_SEASON_WEIGHT * previous["averages"]["games"]
    return {
        "averages": blend_averages(current["averages"], previous["averages"]),
        # The position reference describes the same mix of seasons as the player.
        "position_averages": _blend_dicts(
            current["position_averages"], previous["position_averages"], current_weight, previous_weight,
        ),
        "usage": blend_usage(current["usage"], previous["usage"]),
        "position_usage": _blend_usage(
            current["position_usage"], previous["position_usage"], current_weight, previous_weight,
        ),
        # The game environment is compared against the same mix of seasons as the baseline.
        "environment": _blend_environment(
            current.get("environment"), previous.get("environment"), PREVIOUS_SEASON_WEIGHT,
        ),
    }


def blended_row(row: dict, line_season: int) -> dict:
    """The row with the season blend swapped in, for every market but anytime TD.

    `current_season_games` keeps the season flags on the line's own season, so a
    mostly-last-season blend still reads as stale and ranks as it did before.
    """
    if NflPropMarket(row["market"]) is NflPropMarket.ANYTIME_TOUCHDOWN:
        return row
    inputs = season_blend_inputs(row["baseline_seasons"], line_season)
    if inputs is None:
        return row
    current_games = row["baseline_seasons"][line_season]["averages"]["games"]
    return {**row, **inputs, "baseline_reason": CURRENT_PREVIOUS_BLEND, "current_season_games": current_games}


def apply_season_blend(row: dict, line_season: int) -> dict:
    """The row blended when its market adopted the blend; otherwise the row itself."""
    if NflPropMarket(row["market"]) not in SEASON_BLEND_MARKETS:
        return row
    return blended_row(row, line_season)
