"""Frozen NBA prop predictions and their settlement (item 20g3).

A frozen row is what `project_line` served for one stored line before tip-off,
graded later by the shared forward check. Pure: no DB, no I/O, no clock.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from app.core.nba_line_only import line_only_value
from app.core.nba_projection import NbaLineProjection, project_line
from app.core.nba_projection_backtest import NbaHistoryRow
from app.core.prop_predictions import FreezableGame, PropPredictionRow
from app.core.prop_settlement import settle
from app.nba.markets import NbaPropMarket


@dataclass(frozen=True)
class NbaFreezeLine:
    """One stored PrizePicks line at its latest pre-tip snapshot, with its game's date and tip time."""

    line_id: int
    game_id: int
    game_date: date
    start_utc: datetime | None
    player_id: int
    market: str
    odds_type: str | None
    line: float
    fetched_at: datetime


def prediction_row(line: NbaFreezeLine, projection: NbaLineProjection, now: datetime) -> PropPredictionRow:
    """The row for one line; an ineligible line is still frozen, with a null projection and its flag."""
    return PropPredictionRow(
        prop_line_id=line.line_id,
        model_version=projection.model_version,
        over_probability_version=projection.over_probability_version,
        projection=projection.projection, p_over=projection.p_over, p_under=projection.p_under,
        # NBA serves a gap, not an edge, until 20g4 adopts a slice.
        edge=None,
        quality_flags=list(projection.flags),
        feature_snapshot={
            "games_in_sample": projection.games_in_sample, "prior_minutes": projection.prior_minutes,
            "gap": projection.gap, "line": line.line, "odds_type": line.odds_type, "market": line.market,
            "segment": "full_game", "line_fetched_at": line.fetched_at.isoformat(),
        },
        generated_at=now,
    )


def freezable_games(
    lines: Sequence[NbaFreezeLine],
    prior_by_date: Mapping[date, Mapping[int, Sequence[NbaHistoryRow]]],
    now: datetime,
) -> list[FreezableGame]:
    """Every line projected as the game page projects it, grouped by game for `freeze_rows`.

    Prior games are keyed by game date, then player: a player can play twice in
    a week, and each game reads only the games dated before its own. A player
    missing for a date has no prior games.
    """
    by_game: dict[int, list[NbaFreezeLine]] = {}
    for line in lines:
        by_game.setdefault(line.game_id, []).append(line)
    return [
        FreezableGame(game_lines[0].start_utc, [_freeze(line, prior_by_date, now) for line in game_lines])
        for game_lines in by_game.values()
    ]


def _freeze(
    line: NbaFreezeLine, prior_by_date: Mapping[date, Mapping[int, Sequence[NbaHistoryRow]]], now: datetime,
) -> PropPredictionRow:
    prior = prior_by_date.get(line.game_date, {}).get(line.player_id, [])
    return prediction_row(line, project_line(prior, NbaPropMarket(line.market), line.line), now)


def settle_frozen(
    market: str, line: float, box_row: Mapping[str, int | bool | None] | None, game_has_box_scores: bool,
) -> str:
    """The frozen line's outcome: over, under or push, else why it is not a call.

    A game with no box-score rows at all has not loaded yet, which must never
    read as every player sitting out. With the game loaded, a player with no
    row or a DNP row did not play, and PrizePicks voids the line.
    """
    if not game_has_box_scores:
        return "stats_not_loaded"
    if box_row is None or box_row.get("did_not_play"):
        return "void_dnp"
    value = line_only_value(NbaPropMarket(market), box_row)
    if value is None:
        return "missing_stat"
    return settle(value, line)
