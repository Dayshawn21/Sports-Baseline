"""PrizePicks NHL markets, all stored for line history only (45c)."""
from __future__ import annotations

from enum import StrEnum

from app.core.prop_sports import FULL_GAME_SEGMENT, SportPropConfig


class NhlLineOnlyMarket(StrEnum):
    SHOTS_ON_GOAL = "shots_on_goal"
    POINTS = "points"
    ASSISTS = "assists"
    GOALS = "goals"
    POWER_PLAY_POINTS = "power_play_points"
    BLOCKED_SHOTS = "blocked_shots"
    PLUS_MINUS = "plus_minus"
    GOALIE_SAVES = "goalie_saves"
    HITS = "hits"
    TIME_ON_ICE = "time_on_ice"
    GOALS_ALLOWED = "goals_allowed"
    FACEOFFS_WON = "faceoffs_won"


NHL_PROPS = SportPropConfig(
    code="nhl",
    league_prefix="NHL",
    segment_suffixes={"1P": "p1", "SZN": "season"},
    board_segments=frozenset({FULL_GAME_SEGMENT}),
    market_aliases={
        "shots on goal": NhlLineOnlyMarket.SHOTS_ON_GOAL,
        "points": NhlLineOnlyMarket.POINTS,
        "assists": NhlLineOnlyMarket.ASSISTS,
        "goals": NhlLineOnlyMarket.GOALS,
        "power play points": NhlLineOnlyMarket.POWER_PLAY_POINTS,
        "blocked shots": NhlLineOnlyMarket.BLOCKED_SHOTS,
        "plus/minus": NhlLineOnlyMarket.PLUS_MINUS,
        "goalie saves": NhlLineOnlyMarket.GOALIE_SAVES,
        "hits": NhlLineOnlyMarket.HITS,
        # The provider labels this "Minutes"; NHL box scores store seconds.
        "time on ice": NhlLineOnlyMarket.TIME_ON_ICE,
        "goals allowed": NhlLineOnlyMarket.GOALS_ALLOWED,
        "faceoffs won": NhlLineOnlyMarket.FACEOFFS_WON,
    },
    period_label="week",
)
