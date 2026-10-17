"""ELO computed forward from match results, so it exists for every historical match.

`player_elo` is scraped from TennisAbstract, which publishes only current ratings. The
earliest snapshot in the database is 2026-01-05, so two thirds of backfilled matches
have no as-of-date rating at all, and ELO is the strongest leak-free signal available.

Ratings here are rebuilt by walking matches in chronological order. A match is always
scored with the ratings as they stood before it was played, so the result being
predicted cannot influence its own features.

K-factor decays with matches played, following the approach FiveThirtyEight used for
tennis: new players move fast, established ones move slowly.

Pure: no DB, no I/O.
"""
from __future__ import annotations

import bisect
import datetime as dt
from typing import Iterable, Optional

BASE_RATING = 1500.0
_K_NUMERATOR = 250.0
_K_OFFSET = 5.0
_K_EXPONENT = 0.4

_SURFACES = ("hard", "clay", "grass")


def expected_score(rating_a: float, rating_b: float) -> float:
    """Probability a beats b, on the standard 400-point logistic scale."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def k_factor(matches_played: int) -> float:
    return _K_NUMERATOR / ((matches_played + _K_OFFSET) ** _K_EXPONENT)


class EloIndex:
    """Per-player rating timelines, queryable as of any date."""

    def __init__(self, rows: Iterable[tuple]) -> None:
        """rows: (match_date, p1_id, p2_id, winner_id, surface), any order."""
        played = sorted(
            (r for r in rows if r[0] is not None and r[3] is not None),
            key=lambda r: r[0],
        )

        ratings: dict[int, float] = {}
        counts: dict[int, int] = {}
        surf_ratings: dict[tuple[int, str], float] = {}
        surf_counts: dict[tuple[int, str], int] = {}

        # timeline[pid] = list of (date, rating_after_that_match), chronological
        self._timeline: dict[int, list[tuple[dt.date, float]]] = {}
        self._surf_timeline: dict[tuple[int, str], list[tuple[dt.date, float]]] = {}

        for match_date, p1_id, p2_id, winner_id, surface in played:
            if p1_id is None or p2_id is None:
                continue
            surf = (surface or "").lower()
            surf = surf if surf in _SURFACES else None

            r1 = ratings.get(p1_id, BASE_RATING)
            r2 = ratings.get(p2_id, BASE_RATING)
            s1 = 1.0 if winner_id == p1_id else 0.0

            e1 = expected_score(r1, r2)
            k1 = k_factor(counts.get(p1_id, 0))
            k2 = k_factor(counts.get(p2_id, 0))
            ratings[p1_id] = r1 + k1 * (s1 - e1)
            ratings[p2_id] = r2 + k2 * ((1.0 - s1) - (1.0 - e1))
            counts[p1_id] = counts.get(p1_id, 0) + 1
            counts[p2_id] = counts.get(p2_id, 0) + 1

            self._timeline.setdefault(p1_id, []).append((match_date, ratings[p1_id]))
            self._timeline.setdefault(p2_id, []).append((match_date, ratings[p2_id]))

            if surf:
                k1s, k2s = (p1_id, surf), (p2_id, surf)
                sr1 = surf_ratings.get(k1s, BASE_RATING)
                sr2 = surf_ratings.get(k2s, BASE_RATING)
                es1 = expected_score(sr1, sr2)
                surf_ratings[k1s] = sr1 + k_factor(surf_counts.get(k1s, 0)) * (s1 - es1)
                surf_ratings[k2s] = sr2 + k_factor(surf_counts.get(k2s, 0)) * ((1.0 - s1) - (1.0 - es1))
                surf_counts[k1s] = surf_counts.get(k1s, 0) + 1
                surf_counts[k2s] = surf_counts.get(k2s, 0) + 1
                self._surf_timeline.setdefault(k1s, []).append((match_date, surf_ratings[k1s]))
                self._surf_timeline.setdefault(k2s, []).append((match_date, surf_ratings[k2s]))

        self._dates = {pid: [d for d, _ in tl] for pid, tl in self._timeline.items()}
        self._surf_dates = {key: [d for d, _ in tl] for key, tl in self._surf_timeline.items()}

    @staticmethod
    def _lookup(timeline, dates, key, before: dt.date) -> Optional[float]:
        tl = timeline.get(key)
        if not tl:
            return None
        cut = bisect.bisect_left(dates[key], before)
        return tl[cut - 1][1] if cut else None

    def rating(self, player_id: int, before: dt.date) -> Optional[float]:
        """Overall rating after the player's last match before `before`.

        None when they had not played yet, so the caller can encode it as missing
        rather than as a default 1500 that looks like a real mid-tier rating.
        """
        return self._lookup(self._timeline, self._dates, player_id, before)

    def surface_rating(self, player_id: int, surface: Optional[str], before: dt.date) -> Optional[float]:
        surf = (surface or "").lower()
        if surf not in _SURFACES:
            return None
        return self._lookup(self._surf_timeline, self._surf_dates, (player_id, surf), before)
