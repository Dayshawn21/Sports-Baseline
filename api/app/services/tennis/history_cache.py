"""Cached as-of-date indexes for serving, matching how the model was trained.

v6 learns head-to-head, form, and computed ELO from match results via HistoryIndex and
EloIndex. Serving has to produce those same features by the same definitions, or the
model is handed a different vector than it was fit on.

Both indexes are built from every completed match (~35k rows, about a second), so they
are built once and reused. They are rebuilt when new results land, detected by the count
of completed matches rather than a timer, so a quiet day costs nothing and an ingest is
picked up on the next prediction.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.asof_features import HistoryIndex, h2h_win_pct
from app.ml.elo_history import EloIndex
from app.repositories.matches import Match

logger = logging.getLogger(__name__)

_COMPLETED_SQL = """
SELECT match_date, p1_id, p2_id, winner_id, surface
FROM matches
WHERE status = 'completed' AND winner_id IS NOT NULL
ORDER BY match_date
"""

_COUNT_SQL = "SELECT COUNT(*) FROM matches WHERE status = 'completed' AND winner_id IS NOT NULL"


class HistoryCache:
    """Holds the two indexes, rebuilding only when the result set grows."""

    def __init__(self) -> None:
        self._history: Optional[HistoryIndex] = None
        self._elo: Optional[EloIndex] = None
        self._built_at_count: int = -1
        self._rebuild = asyncio.Lock()

    async def get(self, db: AsyncSession) -> tuple[HistoryIndex, EloIndex]:
        count = (await db.execute(text(_COUNT_SQL))).scalar() or 0
        async with self._rebuild:
            if self._history is None or self._elo is None or count != self._built_at_count:
                rows = (await db.execute(text(_COMPLETED_SQL))).fetchall()
                logger.info("Rebuilding history indexes from %d completed matches", len(rows))
                self._history, self._elo = await asyncio.to_thread(
                    lambda: (HistoryIndex(rows), EloIndex(rows))
                )
                self._built_at_count = count
            return self._history, self._elo


def min_prior_matches(history: HistoryIndex, match: Match) -> int:
    """Completed matches before this one for the player with fewer of them."""
    on: dt.date = match.match_date or dt.date.today()
    return int(min(history.form(match.p1_id, on)["experience"], history.form(match.p2_id, on)["experience"]))


def asof_features(
    history: HistoryIndex,
    elo: EloIndex,
    match: Match,
) -> dict[str, Optional[float]]:
    """Features for `match` derived only from results before it.

    Returns the subset the model was trained on. Values are None where there is no
    history to compute them from, which the caller encodes as missing rather than as a
    real value.
    """
    on: dt.date = match.match_date or dt.date.today()
    surface = match.surface or None
    p1, p2 = match.p1_id, match.p2_id

    f1 = history.form(p1, on, surface)
    f2 = history.form(p2, on, surface)

    def diff(key: str) -> Optional[float]:
        a, b = f1[key], f2[key]
        return None if (a is None or b is None) else a - b

    c1, c2 = elo.rating(p1, on), elo.rating(p2, on)
    s1, s2 = elo.surface_rating(p1, surface, on), elo.surface_rating(p2, surface, on)

    h1, h2 = history.h2h(p1, p2, on)
    sh1, sh2 = history.h2h(p1, p2, on, surface=surface) if surface else (0, 0)

    return {
        "d_elo_computed": (c1 - c2) if (c1 is not None and c2 is not None) else None,
        "d_surface_elo_computed": (s1 - s2) if (s1 is not None and s2 is not None) else None,
        "d_experience": diff("experience"),
        "d_rest_days": diff("rest_days"),
        "d_matches_10d": diff("matches_10d"),
        "d_matches_30d": diff("matches_30d"),
        "d_streak": diff("streak"),
        "d_win_rate_last_20": diff("win_rate_last_20"),
        "d_win_rate_last_3": diff("win_rate_last_3"),
        "d_win_rate_surface": diff("win_rate_surface"),
        "h2h_total_matches": float(h1 + h2),
        "h2h_p1_win_pct": h2h_win_pct(h1, h2),
        "h2h_surface_matches": float(sh1 + sh2),
        "h2h_surface_p1_win_pct": h2h_win_pct(sh1, sh2),
    }
