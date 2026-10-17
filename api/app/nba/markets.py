"""PrizePicks NBA prop markets and leagues (item 20c).

`NbaPropMarket` holds the markets the reference projection covers (20g2);
`NbaLineOnlyMarket` holds the rest, stored for line history and shown gray
(20e). The two are disjoint, and no stored value is ever renamed.
"""
from __future__ import annotations

from enum import StrEnum

from app.core.prop_sports import FULL_GAME_SEGMENT, SportPropConfig


class NbaPropMarket(StrEnum):
    """Projected by `nba-reference-v1` (20g2); 20f's backtest markets, in this order."""

    POINTS = "points"
    REBOUNDS = "rebounds"
    ASSISTS = "assists"
    THREES_MADE = "threes_made"
    BLOCKS = "blocks"
    POINTS_REBOUNDS_ASSISTS = "points_rebounds_assists"
    POINTS_REBOUNDS = "points_rebounds"
    POINTS_ASSISTS = "points_assists"
    REBOUNDS_ASSISTS = "rebounds_assists"


class NbaLineOnlyMarket(StrEnum):
    """Stored for line history only: double-double is binary, so a mean cannot project it."""

    DOUBLE_DOUBLE = "double_double"


NbaMarket = NbaPropMarket | NbaLineOnlyMarket

# Modelled markets first, in enum order, then line-only: the order NBA lines are listed in.
NBA_MARKETS: tuple[NbaMarket, ...] = (*NbaPropMarket, *NbaLineOnlyMarket)


def nba_market(value: str) -> NbaMarket:
    """A stored market string as its enum member; raises ValueError for an unknown one."""
    return NbaPropMarket(value) if value in NbaPropMarket._value2member_map_ else NbaLineOnlyMarket(value)


NBA_PROPS = SportPropConfig(
    code="nba",
    league_prefix="NBA",
    # Recognized so they are never mistaken for game lines, but kept off the board:
    # no stored data settles a half, a quarter or a season. NBAP (preseason) and
    # the other unknown suffixes map to no segment.
    segment_suffixes={"1H": "first_half", "2H": "second_half", "1Q": "q1", "SZN": "season"},
    board_segments=frozenset({FULL_GAME_SEGMENT}),
    # Exact names from the 2026-10-06 board; names not yet seen are logged as
    # unsupported and the "(Combo)" variants stay unmapped.
    market_aliases={
        "points": NbaPropMarket.POINTS,
        "rebounds": NbaPropMarket.REBOUNDS,
        "assists": NbaPropMarket.ASSISTS,
        "3-pt made": NbaPropMarket.THREES_MADE,
        "blocked shots": NbaPropMarket.BLOCKS,
        "pts+rebs+asts": NbaPropMarket.POINTS_REBOUNDS_ASSISTS,
        "pts+rebs": NbaPropMarket.POINTS_REBOUNDS,
        "pts+asts": NbaPropMarket.POINTS_ASSISTS,
        "rebs+asts": NbaPropMarket.REBOUNDS_ASSISTS,
        "double-double": NbaLineOnlyMarket.DOUBLE_DOUBLE,
    },
    period_label="week",
)
