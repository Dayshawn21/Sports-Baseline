"""Settlement rules for the line-only NBA markets (item 20c): a box-score row to a market value.

Each market is a sum of `nba_player_game_stats` columns, except double-double. A DNP
or any NULL input makes the value None rather than a partial sum or a zero,
because NULL means not loaded or did not play.
"""
from __future__ import annotations

from collections.abc import Mapping

from app.nba.markets import NbaLineOnlyMarket, NbaMarket, NbaPropMarket

_SUMS: dict[NbaPropMarket, tuple[str, ...]] = {
    NbaPropMarket.POINTS: ("points",),
    NbaPropMarket.REBOUNDS: ("rebounds",),
    NbaPropMarket.ASSISTS: ("assists",),
    NbaPropMarket.THREES_MADE: ("three_pointers_made",),
    NbaPropMarket.BLOCKS: ("blocks",),
    NbaPropMarket.POINTS_REBOUNDS_ASSISTS: ("points", "rebounds", "assists"),
    NbaPropMarket.POINTS_REBOUNDS: ("points", "rebounds"),
    NbaPropMarket.POINTS_ASSISTS: ("points", "assists"),
    NbaPropMarket.REBOUNDS_ASSISTS: ("rebounds", "assists"),
}

# The standard double-double categories; a triple-double also counts.
DOUBLE_DOUBLE_COLUMNS = ("points", "rebounds", "assists", "steals", "blocks")

LINE_ONLY_COLUMNS: tuple[str, ...] = tuple(sorted(
    {column for columns in _SUMS.values() for column in columns} | set(DOUBLE_DOUBLE_COLUMNS)
))


def has_rule(market: NbaMarket) -> bool:
    return market in _SUMS or market is NbaLineOnlyMarket.DOUBLE_DOUBLE


def line_only_value(market: NbaMarket, row: Mapping[str, int | bool | None]) -> float | None:
    if row.get("did_not_play"):
        return None
    columns = DOUBLE_DOUBLE_COLUMNS if market is NbaLineOnlyMarket.DOUBLE_DOUBLE else _SUMS[market]
    values = [row.get(column) for column in columns]
    if any(value is None for value in values):
        return None
    if market is NbaLineOnlyMarket.DOUBLE_DOUBLE:
        return 1.0 if sum(value >= 10 for value in values) >= 2 else 0.0
    return float(sum(values))
