"""The NFL player page's derived numbers: focus by position, summary, splits and past lines.

Pure: no DB, no I/O. Display only; nothing here feeds a projection, edge or rank.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from app.core.nfl_line_grading import LineResult
from app.nfl.markets import STANDARD_ODDS_TYPE, NflPropMarket, NflPropSegment

SPLIT_WINDOW = 17
SNAP_STAT = "snap_pct"
DOME_ROOFS = frozenset({"dome", "closed"})
OUTDOOR_ROOFS = frozenset({"outdoors", "open"})


@dataclass(frozen=True)
class PlayerGameRow:
    """One completed regular-season game with a stat row, from the player's side."""

    game_id: int
    season: int
    week: int
    opponent: str
    is_home: bool
    team_score: int | None
    opponent_score: int | None
    # Closing spread from the player's side in book sign: negative means the player's team was favored.
    team_spread: float | None
    roof: str | None
    # 0 to 1; None when no snap row was loaded, never 0.
    snap_pct: float | None
    passing_completions: int
    passing_attempts: int
    passing_yards: int
    rushing_attempts: int
    rushing_yards: int
    targets: int | None
    receptions: int
    receiving_yards: int
    touchdowns: int
    prizepicks_fantasy_points: float | None
    fg_made: int | None = None
    pat_made: int | None = None
    punts: int | None = None


@dataclass(frozen=True)
class PositionFocus:
    """What a position's page leads with; stats name `PlayerGameRow` fields."""

    market: NflPropMarket | None
    focus_stat: str | None
    volume_stat: str | None
    usage_stats: tuple[str, ...]


_RECEIVER = PositionFocus(NflPropMarket.RECEIVING_YARDS, "receiving_yards", "targets", ("targets", "receptions", SNAP_STAT))

POSITION_FOCUS: dict[str, PositionFocus] = {
    "QB": PositionFocus(NflPropMarket.PASSING_YARDS, "passing_yards", "passing_attempts", ("passing_attempts", "rushing_attempts", SNAP_STAT)),
    "RB": PositionFocus(NflPropMarket.RUSHING_YARDS, "rushing_yards", "rushing_attempts", ("rushing_attempts", "targets", SNAP_STAT)),
    "WR": _RECEIVER,
    "TE": _RECEIVER,
}

NO_FOCUS = PositionFocus(None, None, None, (SNAP_STAT,))


def focus_for(position: str | None) -> PositionFocus:
    return POSITION_FOCUS.get((position or "").upper(), NO_FOCUS)


@dataclass(frozen=True)
class StatLine:
    """Per-game means over a set of games; a mean is None when no game has the stat."""

    label: str
    games: int
    focus_per_game: float | None
    volume_per_game: float | None
    snap_share: float | None


@dataclass(frozen=True)
class PastLineCount:
    market: str
    overs: int
    decided: int


def _mean(values: Iterable[float | int | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return sum(present) / len(present) if present else None


def _stat(row: PlayerGameRow, name: str | None) -> float | int | None:
    return getattr(row, name) if name is not None else None


def _stat_line(label: str, rows: Sequence[PlayerGameRow], focus: PositionFocus) -> StatLine:
    return StatLine(
        label=label,
        games=len(rows),
        focus_per_game=_mean(_stat(row, focus.focus_stat) for row in rows),
        volume_per_game=_mean(_stat(row, focus.volume_stat) for row in rows),
        snap_share=_mean(row.snap_pct for row in rows),
    )


def season_summary(rows: Iterable[PlayerGameRow], season: int, focus: PositionFocus) -> StatLine:
    return _stat_line("Season", [row for row in rows if row.season == season], focus)


# A pick'em, a missing line, or an unknown roof falls in neither side of its pair.
_SPLITS: tuple[tuple[str, Callable[[PlayerGameRow], bool]], ...] = (
    ("All", lambda row: True),
    ("Home", lambda row: row.is_home),
    ("Away", lambda row: not row.is_home),
    ("Team favored", lambda row: row.team_spread is not None and row.team_spread < 0),
    ("Team underdog", lambda row: row.team_spread is not None and row.team_spread > 0),
    ("Dome", lambda row: row.roof in DOME_ROOFS),
    ("Outdoor", lambda row: row.roof in OUTDOOR_ROOFS),
)


def record_splits(rows: Sequence[PlayerGameRow], focus: PositionFocus) -> list[StatLine]:
    """Splits over the latest `SPLIT_WINDOW` games; `rows` are newest first. Empty without a focus."""
    if focus.market is None:
        return []
    window = rows[:SPLIT_WINDOW]
    return [_stat_line(label, [row for row in window if keep(row)], focus) for label, keep in _SPLITS]


def past_line_counts(results: Iterable[LineResult]) -> list[PastLineCount]:
    """Over hits out of decided standard full-game lines, per market, in market order."""
    counts: dict[str, list[int]] = {}
    for result in results:
        line = result.line
        if line.odds_type != STANDARD_ODDS_TYPE or line.segment != NflPropSegment.FULL_GAME:
            continue
        if result.outcome not in ("over", "under"):
            continue
        overs, decided = counts.setdefault(line.market, [0, 0])
        counts[line.market] = [overs + (result.outcome == "over"), decided + 1]
    order = {market.value: index for index, market in enumerate(NflPropMarket)}
    return [
        PastLineCount(market, overs, decided)
        for market, (overs, decided) in sorted(counts.items(), key=lambda item: order.get(item[0], len(order)))
    ]
