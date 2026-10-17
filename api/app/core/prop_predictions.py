"""Frozen prop predictions for any sport (17c, from 27i).

A row is what a sport's slate served for one line before its game started,
graded later by the forward check in `app/core/prop_ranking_check.py`.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PropPredictionRow:
    prop_line_id: int
    model_version: str
    over_probability_version: str | None
    projection: float | None
    p_over: float | None
    p_under: float | None
    edge: float | None
    quality_flags: list[str]
    feature_snapshot: dict[str, str | float | int | None]
    generated_at: datetime


@dataclass(frozen=True)
class FreezableGame:
    """One game's predictions as the sport's slate served them; frozen only if the game has not started."""

    start_utc: datetime | None
    rows: list[PropPredictionRow]


def freeze_rows(games: Sequence[FreezableGame], now: datetime) -> tuple[list[PropPredictionRow], Counter[str]]:
    """Rows for every game that has not started at `now`, and why the others were skipped.

    Only a prediction made strictly before the start is a record of what could
    have been bet on; anything later may already reflect the game.
    """
    rows: list[PropPredictionRow] = []
    counts: Counter[str] = Counter()
    for game in games:
        if game.start_utc is None:
            counts["no_start_time"] += len(game.rows)
            continue
        if game.start_utc <= now:
            counts["kicked_off"] += len(game.rows)
            continue
        rows += game.rows
    counts["frozen"] = len(rows)
    return rows, counts
