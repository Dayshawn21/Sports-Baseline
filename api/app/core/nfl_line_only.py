"""Settlement rules for the line-only NFL markets (item 34): a weekly stat row to a market value.

Each market is a weighted sum of `nfl_player_weekly_stats` columns. Any NULL input
makes the value None rather than a partial sum, because NULL means not loaded.
"""
from __future__ import annotations

from collections.abc import Mapping

from app.nfl.markets import NflLineOnlyMarket

# market -> ((column, weight), ...). Kicking points use PrizePicks' standard
# scoring, 3 per field goal and 1 per extra point.
_RULES: dict[NflLineOnlyMarket, tuple[tuple[str, int], ...]] = {
    NflLineOnlyMarket.PASSING_TOUCHDOWNS: (("passing_tds", 1),),
    NflLineOnlyMarket.INTERCEPTIONS: (("interceptions", 1),),
    NflLineOnlyMarket.RUSHING_RECEIVING_YARDS: (("rushing_yards", 1), ("receiving_yards", 1)),
    NflLineOnlyMarket.PASSING_RUSHING_YARDS: (("passing_yards", 1), ("rushing_yards", 1)),
    NflLineOnlyMarket.PASSING_RUSHING_RECEIVING_TOUCHDOWNS: (("passing_tds", 1), ("touchdowns", 1)),
    NflLineOnlyMarket.FIELD_GOALS_MADE: (("fg_made", 1),),
    NflLineOnlyMarket.KICKING_POINTS: (("fg_made", 3), ("pat_made", 1)),
    NflLineOnlyMarket.PUNTS: (("punts", 1),),
}

LINE_ONLY_COLUMNS: tuple[str, ...] = tuple(sorted({column for rule in _RULES.values() for column, _ in rule}))


def line_only_value(market: NflLineOnlyMarket, row: Mapping[str, int | None]) -> float | None:
    total = 0
    for column, weight in _RULES[market]:
        value = row.get(column)
        if value is None:
            return None
        total += weight * value
    return float(total)
