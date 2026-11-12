"""One frozen projection per match and stat for the player-page projection history (60a).

Pure: rows arrive from the repository, nothing here reads the database.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, TypeVar

from app.core.box_score_join import JoinResult
from app.core.prop_projection import normalize_stat_type
from app.core.prop_settlement import resolve_actual
from app.core.tennis_grading import is_completed_score


class _SnapshotRow(Protocol):
    @property
    def snapshot_id(self) -> int: ...
    @property
    def match_id(self) -> int: ...
    @property
    def stat_type(self) -> str: ...
    @property
    def snapshot_at(self) -> datetime: ...


_Row = TypeVar("_Row", bound=_SnapshotRow)


def latest_line_per_match(rows: list[_Row]) -> list[_Row]:
    """Keep one line per match and stat: the latest snapshot, so a line that moved between fetches shows its closing value."""
    latest: dict[tuple[int, str], _Row] = {}
    for row in rows:
        key = (row.match_id, normalize_stat_type(row.stat_type))
        kept = latest.get(key)
        if kept is None or (row.snapshot_at, row.snapshot_id) > (kept.snapshot_at, kept.snapshot_id):
            latest[key] = row
    return list(latest.values())


class _HistoryRow(_SnapshotRow, Protocol):
    @property
    def line(self) -> float: ...
    @property
    def projection(self) -> float | None: ...
    @property
    def player_is_p1(self) -> bool: ...
    @property
    def score(self) -> str | None: ...
    @property
    def best_of(self) -> int | None: ...
    @property
    def match_date(self) -> date | None: ...
    @property
    def tournament(self) -> str | None: ...
    @property
    def round(self) -> str | None: ...
    @property
    def surface(self) -> str | None: ...
    @property
    def opponent_id(self) -> int: ...
    @property
    def opponent_name(self) -> str: ...


@dataclass(frozen=True)
class ProjectionHistoryPoint:
    match_id: int
    match_date: date | None
    tournament: str | None
    round: str | None
    surface: str | None
    opponent_id: int
    opponent_name: str
    stat: str
    line: float
    projection: float | None
    actual: int | None
    """None until the result can be settled; such a point is counted, never charted."""
    snapshot_at: datetime


def history_point(row: _HistoryRow, join: JoinResult | None) -> ProjectionHistoryPoint | None:
    """The frozen line and projection with the settled result, or None for a retirement or walkover.

    Same order as the settled-props table: a match not played to the end voids the
    line before any result is read.
    """
    if not is_completed_score(row.score, row.best_of or 3):
        return None
    stat = normalize_stat_type(row.stat_type)
    actual, _ = resolve_actual(stat, row.score, row.player_is_p1, join)
    return ProjectionHistoryPoint(
        match_id=row.match_id, match_date=row.match_date, tournament=row.tournament, round=row.round,
        surface=row.surface, opponent_id=row.opponent_id, opponent_name=row.opponent_name,
        stat=stat, line=row.line, projection=row.projection, actual=actual, snapshot_at=row.snapshot_at,
    )
