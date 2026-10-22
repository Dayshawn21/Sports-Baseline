"""Descriptive workload and rate conversions for match research."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import math
import re


@dataclass(frozen=True)
class WorkloadMatch:
    match_id: int
    match_date: date
    status: str
    score: str | None


@dataclass(frozen=True)
class Workload:
    window_start: date
    window_end_exclusive: date
    previous_match_date: date | None
    calendar_days_since_match: int | None
    matches_played: int
    completed_sets: int
    matches_with_complete_scores: int
    minutes_played: int | None = None
    date_basis: str = "UTC match dates; same-day matches excluded"
    history_lookback_days: int = 365
    source: str = "Stored canonical matches"


@dataclass(frozen=True)
class ResearchStats:
    surface: str | None
    matches_count: int | None
    computed_at: datetime | None
    win_rate: float | None
    hold_pct: float | None
    return_points_won: float | None
    break_conversion_pct: float | None
    first_in_pct: float | None
    first_serve_won: float | None
    second_serve_won: float | None
    first_return_won: float | None
    second_return_won: float | None
    thin_sample: bool
    stat_period: str = "last_52w"
    source: str = "TennisAbstract"
    snapshot_basis: str = "Current rolling snapshot, not a historical pre-match snapshot"


def valid_rate(value: float | None) -> float | None:
    return value if value is not None and math.isfinite(value) and 0 <= value <= 1 else None


def return_rate(opponent_serve_won: float | None) -> float | None:
    rate = valid_rate(opponent_serve_won)
    return None if rate is None else 1 - rate


def completed_sets(score: str | None) -> tuple[int, bool]:
    if not score:
        return 0, False
    total, complete = 0, True
    for token in score.split():
        parsed = re.fullmatch(r"(\d+)-(\d+)(?:\(\d+\))?", token)
        if parsed is None:
            complete = False
            continue
        high, low = sorted(map(int, parsed.groups()), reverse=True)
        finished = (high == 6 and low <= 4) or (high == 7 and low in (5, 6)) or (high >= 8 and high - low == 2)
        if finished:
            total += 1
        else:
            complete = False
    return total, complete and total > 0


def workload(rows: list[WorkloadMatch], target_id: int, on: date) -> Workload:
    start = on - timedelta(days=7)
    seen: set[int] = set()
    played: list[WorkloadMatch] = []
    for row in rows:
        if row.match_id == target_id or row.match_id in seen or not on - timedelta(days=365) <= row.match_date < on:
            continue
        seen.add(row.match_id)
        score = (row.score or "").strip().upper()
        unplayed = re.search(r"W[./\s-]*O|WALKOVER|CANCEL|DEFAULT", score)
        zero_only = bool(score) and all(token == "0-0" for token in score.split())
        if row.status not in ("completed", "retired") or unplayed or zero_only:
            continue
        played.append(row)
    recent = [row for row in played if row.match_date >= start]
    scores = [completed_sets(row.score) for row in recent]
    previous = max((row.match_date for row in played), default=None)
    return Workload(start, on, previous, (on - previous).days if previous else None,
                    len(recent), sum(count for count, _ in scores), sum(complete for _, complete in scores))
