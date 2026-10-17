"""Record splits, tour averages and the ELO summary for the tennis player page (32c).

Pure: no database, no clock. The caller passes the as-of date.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date, timedelta
from typing import Optional

from app.core.prop_settlement import parse_sets
from app.core.tennis_grading import is_completed_score

RECORD_WINDOW_DAYS = 365
TOP_RANK = 20
SURFACES = ("Hard", "Clay", "Grass")


@dataclass(frozen=True)
class PlayerMatchRow:
    match_date: date
    surface: Optional[str]
    best_of: int
    won: bool
    score: Optional[str]
    """Oriented to the player: the player's games come first in each set."""
    opponent_rank: Optional[int]


@dataclass
class WinLoss:
    wins: int = 0
    losses: int = 0

    def add(self, won: bool) -> None:
        if won:
            self.wins += 1
        else:
            self.losses += 1


@dataclass
class RecordSplits:
    window_start: date
    all: WinLoss = field(default_factory=WinLoss)
    hard: WinLoss = field(default_factory=WinLoss)
    clay: WinLoss = field(default_factory=WinLoss)
    grass: WinLoss = field(default_factory=WinLoss)
    vs_top20: WinLoss = field(default_factory=WinLoss)
    deciding_sets: WinLoss = field(default_factory=WinLoss)
    tie_breaks: WinLoss = field(default_factory=WinLoss)
    """Counted in sets, not matches: every 7-6 set is a tie-break won, every 6-7 one lost."""


def record_splits(matches: list[PlayerMatchRow], as_of: date) -> RecordSplits:
    """Win-loss splits over the 365 days before `as_of`.

    A retirement still decides the match, so it counts in the win-loss rows, but
    a set it cut short says nothing about deciding sets or tie-breaks.
    """
    window_start = as_of - timedelta(days=RECORD_WINDOW_DAYS)
    splits = RecordSplits(window_start=window_start)
    for match in matches:
        if not (window_start <= match.match_date < as_of) or not match.score:
            continue
        splits.all.add(match.won)
        if match.surface in SURFACES:
            getattr(splits, match.surface.lower()).add(match.won)
        if match.opponent_rank is not None and match.opponent_rank <= TOP_RANK:
            splits.vs_top20.add(match.won)
        if not is_completed_score(match.score, match.best_of):
            continue
        sets = parse_sets(match.score)
        if len(sets) == match.best_of:
            splits.deciding_sets.add(match.won)
        for mine, theirs in sets:
            if {mine, theirs} == {6, 7}:
                splits.tie_breaks.add(mine > theirs)
    return splits


@dataclass(frozen=True)
class ServeReturnStats:
    hold_pct: Optional[float] = None
    break_pct: Optional[float] = None
    """Break points converted, despite the name (open question 30)."""
    first_in_pct: Optional[float] = None
    first_won_pct: Optional[float] = None
    second_won_pct: Optional[float] = None
    ret_pts_won: Optional[float] = None
    aces_per_game: Optional[float] = None
    """Aces per serve point, despite the name."""
    df_per_game: Optional[float] = None
    """Double faults per serve point, despite the name."""


METRICS = tuple(f.name for f in fields(ServeReturnStats))


@dataclass(frozen=True)
class AverageStats:
    players: int
    stats: ServeReturnStats


def tour_average(rows: list[tuple[int, ServeReturnStats]], min_matches: int) -> AverageStats:
    """Unweighted mean of each metric over players with at least `min_matches`.

    Each metric averages only the players who have it, so one player's missing
    serve split does not drag the others toward zero.
    """
    eligible = [stats for matches, stats in rows if matches >= min_matches]
    means: dict[str, Optional[float]] = {}
    for metric in METRICS:
        values = [v for s in eligible if (v := getattr(s, metric)) is not None]
        means[metric] = sum(values) / len(values) if values else None
    return AverageStats(len(eligible), ServeReturnStats(**means))


@dataclass(frozen=True)
class EloSnapshot:
    as_of: date
    overall: Optional[float]
    hard: Optional[float]
    clay: Optional[float]
    grass: Optional[float]


@dataclass(frozen=True)
class EloSummary:
    latest: Optional[EloSnapshot]
    change: Optional[float]
    """Latest overall minus the first snapshot's; None with fewer than two overall values."""


def elo_summary(history: list[EloSnapshot]) -> EloSummary:
    ordered = sorted(history, key=lambda s: s.as_of)
    if not ordered:
        return EloSummary(None, None)
    overall = [s.overall for s in ordered if s.overall is not None]
    change = overall[-1] - overall[0] if len(overall) >= 2 else None
    return EloSummary(ordered[-1], change)
