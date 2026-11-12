"""One frozen projection per game and stat for the NHL player-page projection history (60b).

Pure: rows arrive from the repository, nothing here reads the database.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from app.core.nhl_prop_predictions import frozen_actual


@dataclass(frozen=True)
class NhlProjectionHistoryLine:
    """One frozen pre-puck-drop line with the box-score values that settle it."""

    line_id: int
    game_id: int
    season: int
    game_date: date
    market: str
    line: float
    fetched_at: datetime
    projection: float | None
    opponent_id: int | None
    """From the player's box-score row, so None only on a line that voids or has not loaded."""
    opponent_code: str | None
    skater_row: Mapping[str, int | None] | None
    goalie_row: Mapping[str, int | bool | None] | None
    game_has_box_scores: bool

    # The names `latest_line_per_match` reads, so 60a's reducer runs on NHL rows unchanged.
    @property
    def match_id(self) -> int:
        return self.game_id

    @property
    def stat_type(self) -> str:
        return self.market

    @property
    def snapshot_at(self) -> datetime:
        return self.fetched_at

    @property
    def snapshot_id(self) -> int:
        return self.line_id


@dataclass(frozen=True)
class NhlProjectionHistoryPoint:
    """A settled frozen line: always a result and an opponent, the projection only when one was frozen."""

    game_id: int
    game_date: date
    season: int
    opponent_id: int
    opponent_name: str
    stat: str
    line: float
    projection: float | None
    """None for a gated line (no confirmed goalie, injury gate); never recomputed."""
    actual: float
    snapshot_at: datetime


def nhl_history_point(line: NhlProjectionHistoryLine) -> NhlProjectionHistoryPoint | Literal["void", "unsettled"]:
    """The frozen line with its result, settled by `frozen_actual` so the chart agrees with the forward check.

    A void line (did not dress, goalie did not start) is dropped as PrizePicks voids it;
    an unloaded game or missing stat is only counted until the box score lands.
    """
    actual = frozen_actual(line.market, line.skater_row, line.goalie_row, line.game_has_box_scores)
    if actual == "void_dnp":
        return "void"
    if isinstance(actual, str) or line.opponent_id is None or line.opponent_code is None:
        return "unsettled"
    return NhlProjectionHistoryPoint(
        game_id=line.game_id, game_date=line.game_date, season=line.season,
        opponent_id=line.opponent_id, opponent_name=line.opponent_code, stat=line.market,
        line=line.line, projection=line.projection, actual=actual, snapshot_at=line.fetched_at,
    )
