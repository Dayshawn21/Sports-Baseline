"""Frozen NHL prop predictions and their settlement (item 56c4).

A frozen row is what `project_line` said about one stored line before puck drop,
graded later by the shared forward check. Pure: no DB, no I/O, no clock.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

from app.core.nhl_player_values import GOALIE_MARKETS, nhl_stat_value
from app.core.nhl_projection import NhlLineProjection
from app.core.prop_predictions import PropPredictionRow
from app.core.prop_settlement import settle
from app.nhl.markets import NhlLineOnlyMarket


@dataclass(frozen=True)
class NhlFreezeLine:
    """One stored PrizePicks line at its latest pre-puck-drop snapshot, with what the projection reads besides history."""

    line_id: int
    game_id: int
    game_date: date
    start_utc: datetime | None
    player_id: int
    team: str | None
    position: str | None
    market: str
    odds_type: str | None
    line: float
    fetched_at: datetime


def prediction_row(line: NhlFreezeLine, projection: NhlLineProjection, now: datetime) -> PropPredictionRow:
    """The row for one line; a gated line is still frozen, with a null projection and its flag."""
    return PropPredictionRow(
        prop_line_id=line.line_id,
        model_version=projection.model_version,
        over_probability_version=projection.over_probability_version,
        projection=projection.projection, p_over=projection.p_over, p_under=projection.p_under,
        # NHL serves a gap, not an edge, until 56d adopts a slice.
        edge=None,
        quality_flags=list(projection.flags),
        feature_snapshot={
            "games_in_sample": projection.games_in_sample, "prior_toi_minutes": projection.prior_toi_minutes,
            "gap": projection.gap, "line": line.line, "odds_type": line.odds_type, "market": line.market,
            "segment": "full_game", "line_fetched_at": line.fetched_at.isoformat(),
        },
        generated_at=now,
    )


def frozen_actual(
    market: str, skater_row: Mapping[str, int | None] | None,
    goalie_row: Mapping[str, int | bool | None] | None, game_has_box_scores: bool,
) -> float | str:
    """The frozen line's result in the market's unit, else why it is not a call.

    A game with no box-score rows at all has not loaded yet, which must never read
    as every player sitting out. With the game loaded, a skater with no row did not
    dress and a goalie with no row or a non-start did not play; PrizePicks voids both.
    """
    if not game_has_box_scores:
        return "stats_not_loaded"
    nhl_market = NhlLineOnlyMarket(market)
    if nhl_market in GOALIE_MARKETS:
        if goalie_row is None or not goalie_row.get("started"):
            return "void_dnp"
        stats = goalie_row
    else:
        if skater_row is None:
            return "void_dnp"
        stats = skater_row
    value = nhl_stat_value(nhl_market, stats)
    return "missing_stat" if value is None else value


def settle_frozen(
    market: str, line: float, skater_row: Mapping[str, int | None] | None,
    goalie_row: Mapping[str, int | bool | None] | None, game_has_box_scores: bool,
) -> str:
    """The frozen line's outcome: over, under or push, else why it is not a call (see `frozen_actual`)."""
    actual = frozen_actual(market, skater_row, goalie_row, game_has_box_scores)
    return actual if isinstance(actual, str) else settle(actual, line)
