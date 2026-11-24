"""Reduce an ordered, single-book market history to line changes."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast


@dataclass(frozen=True)
class LineStep:
    fetched_at: datetime
    line: float


@dataclass(frozen=True)
class LineHistory:
    market: str
    book: str
    steps: list[LineStep]


def line_history_steps(rows: Sequence[Mapping[str, object]]) -> list[LineHistory]:
    """Rows must be ordered by market/time and contain one book per market."""
    histories: dict[str, LineHistory] = {}
    for row in rows:
        market, book = cast(str, row["market"]), cast(str, row["book"])
        history = histories.setdefault(market, LineHistory(market, book, []))
        if not history.steps or history.steps[-1].line != row["line"]:
            history.steps.append(LineStep(cast(datetime, row["fetched_at"]), cast(float, row["line"])))
    return list(histories.values())
