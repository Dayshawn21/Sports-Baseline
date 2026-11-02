"""Per-game values and date choice for the NHL player page. Pure: no database, no I/O."""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence

from app.nhl.markets import NhlLineOnlyMarket

# Every season stored when the page was built; a later backfill must not change what the sample covers.
NHL_FIRST_HISTORY_SEASON = 2023

GOALIE_MARKETS = frozenset({NhlLineOnlyMarket.GOALIE_SAVES, NhlLineOnlyMarket.GOALS_ALLOWED})

_COLUMNS: dict[NhlLineOnlyMarket, str] = {
    NhlLineOnlyMarket.SHOTS_ON_GOAL: "shots",
    NhlLineOnlyMarket.POINTS: "points",
    NhlLineOnlyMarket.ASSISTS: "assists",
    NhlLineOnlyMarket.GOALS: "goals",
    NhlLineOnlyMarket.POWER_PLAY_POINTS: "power_play_points",
    NhlLineOnlyMarket.BLOCKED_SHOTS: "blocked_shots",
    NhlLineOnlyMarket.PLUS_MINUS: "plus_minus",
    NhlLineOnlyMarket.HITS: "hits",
    NhlLineOnlyMarket.FACEOFFS_WON: "faceoffs_won",
    NhlLineOnlyMarket.TIME_ON_ICE: "time_on_ice_seconds",
    NhlLineOnlyMarket.GOALIE_SAVES: "saves",
    NhlLineOnlyMarket.GOALS_ALLOWED: "goals_against",
}


def nhl_stat_value(market: NhlLineOnlyMarket, row: Mapping[str, object]) -> float | None:
    """The stored stat in the market's unit; None when the box score left it unloaded, never 0."""
    raw = row.get(_COLUMNS[market])
    if raw is None:
        return None
    value = float(str(raw))
    return round(value / 60, 2) if market is NhlLineOnlyMarket.TIME_ON_ICE else value


def player_props_date(
    requested: dt.date | None, default: dt.date, player_dates: Sequence[dt.date],
) -> dt.date:
    """A named date is honored as asked; otherwise the default if the player has lines then, else the nearest date they do."""
    if requested is not None:
        return requested
    if not player_dates or default in player_dates:
        return default
    earlier = [date for date in player_dates if date < default]
    if earlier:
        return max(earlier)
    return min(player_dates)
