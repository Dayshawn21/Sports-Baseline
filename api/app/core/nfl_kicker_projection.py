"""Kicker fantasy projection (build-plan item 27l3) and the reference it is scored against.

Pre-registered before any kicker projection was scored on real data: the
candidate, the reference and the sample below are fixed, and the verdict is
27b's `adoption_verdict`, imported unchanged. Pure: no DB, no I/O.
"""
from __future__ import annotations

from app.core.nfl_fantasy import apply_prizepicks_fantasy
from app.core.nfl_season_blend import PREVIOUS_SEASON_WEIGHT, blended_row, season_blend_inputs
from app.nfl.markets import NflPropMarket

NFL_KICKER_MODEL_VERSION = "nfl-kicker-v1"
# The position mean counts as this many games of evidence a kicker has to outweigh:
# the value anytime TD already uses (TD_PRIOR_GAMES), fixed here, not fitted.
KICKER_PRIOR_GAMES = 10.0
# Flipped only on an `adopt` verdict from the pre-registered 2025 run.
KICKER_PROJECTION_SERVED = False
# The row key that tells `_slate_line` to project a kicker fantasy line.
KICKER_PROJECTED = "kicker_projected"

KICKER_BACKTEST_SEASON = 2025
KICKER_REPLAY_MARKETS: dict[str, tuple[str, ...]] = {"K": (NflPropMarket.FANTASY_POINTS.value,)}


def _is_kicker_fantasy(row: dict) -> bool:
    return row["market"] == NflPropMarket.FANTASY_POINTS.value and row.get("position") == "K"


def _blended_prizepicks(row: dict, season: int) -> dict:
    """PrizePicks points (which carry kicking since 27l3) in place of PPR, with 27d's season blend."""
    return blended_row(apply_prizepicks_fantasy(row), season)


def _effective_games(row: dict, season: int) -> float:
    """Current games plus last season's at the blend's weight; one season's games when nothing blends."""
    if season_blend_inputs(row["baseline_seasons"], season) is None:
        return float(row["averages"]["games"])
    played = {year: entry["averages"]["games"] for year, entry in row["baseline_seasons"].items()
              if entry["averages"]["games"] > 0}
    previous = max(year for year in played if year < season)
    return played[season] + PREVIOUS_SEASON_WEIGHT * played[previous]


def shrunk_average(player: float, position: float, effective_games: float) -> float:
    return (effective_games * player + KICKER_PRIOR_GAMES * position) / (effective_games + KICKER_PRIOR_GAMES)


def kicker_row(row: dict, season: int) -> dict:
    """The candidate's inputs for a K fantasy line, flagged for `_slate_line`; any other row unchanged.

    A kicker with no PrizePicks points on record, or no position mean, stays
    unflagged and so unprojected: a missing average must never read as 0.
    """
    if not _is_kicker_fantasy(row):
        return row
    blended = _blended_prizepicks(row, season)
    player = blended["averages"]["fantasy_points"]
    position = blended["position_averages"]["fantasy_points"]
    if player is None or position is None:
        return row
    shrunk = shrunk_average(player, position, _effective_games(row, season))
    return {**blended, "averages": {**blended["averages"], "fantasy_points": shrunk}, KICKER_PROJECTED: True}


def kicker_reference(row: dict, season: int) -> float | None:
    """The pre-registered reference: the K position's blended pre-week mean, with no adjustment."""
    if not _is_kicker_fantasy(row):
        return None
    position = _blended_prizepicks(row, season)["position_averages"]["fantasy_points"]
    return round(position, 2) if position is not None else None
