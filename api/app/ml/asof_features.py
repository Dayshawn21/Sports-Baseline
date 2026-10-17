"""As-of-date match features, derived from match results alone.

Training previously read head-to-head and form from `h2h` and `player_rolling_stats`,
which hold only a current snapshot. Applied to a 2023 match that means the features
describe 2026, and the head-to-head record includes the result of the match being
predicted. A model fit on that learns relationships that do not exist at prediction
time: it scores well in cross-validation and has no edge live.

Everything here is computed from completed matches strictly before a cutoff date, so a
row can only ever see what was knowable when the match started.

Pure: no DB, no I/O. Build the index once from all completed matches, then query it.
"""
from __future__ import annotations

import bisect
import datetime as dt
from dataclasses import dataclass
from typing import Iterable, Optional

# Form windows, chosen to match the feature names the model already used.
_LAST_N = 20
_LAST_SHORT_N = 3
_SURFACE_N = 20


@dataclass(frozen=True)
class PlayedMatch:
    date: dt.date
    won: bool
    surface: Optional[str]
    opponent_id: int


class HistoryIndex:
    """Per-player match history, sorted by date, queryable as of any cutoff."""

    def __init__(self, rows: Iterable[tuple]) -> None:
        """rows: (match_date, p1_id, p2_id, winner_id, surface) for completed matches."""
        by_player: dict[int, list[PlayedMatch]] = {}
        for match_date, p1_id, p2_id, winner_id, surface in rows:
            if match_date is None or winner_id is None:
                continue
            surf = (surface or None)
            for pid, opp in ((p1_id, p2_id), (p2_id, p1_id)):
                if pid is None or opp is None:
                    continue
                by_player.setdefault(pid, []).append(
                    PlayedMatch(match_date, winner_id == pid, surf, opp)
                )

        self._by_player: dict[int, list[PlayedMatch]] = {}
        self._dates: dict[int, list[dt.date]] = {}
        for pid, played in by_player.items():
            played.sort(key=lambda m: m.date)
            self._by_player[pid] = played
            self._dates[pid] = [m.date for m in played]

    def prior(self, player_id: int, before: dt.date) -> list[PlayedMatch]:
        """Every completed match for this player strictly before `before`."""
        played = self._by_player.get(player_id)
        if not played:
            return []
        cut = bisect.bisect_left(self._dates[player_id], before)
        return played[:cut]

    def form(self, player_id: int, before: dt.date, surface: Optional[str] = None) -> dict[str, Optional[float]]:
        """Form as it stood the day before `before`.

        Values are None rather than 0.0 where there is no history to compute them from,
        so the caller can encode them as missing instead of as a real extreme.
        """
        played = self.prior(player_id, before)
        if not played:
            return {
                "experience": 0.0, "rest_days": None, "matches_10d": 0.0,
                "matches_30d": 0.0, "streak": 0.0, "win_rate_last_20": None,
                "win_rate_last_3": None, "win_rate_surface": None,
            }

        last = played[-1]
        recent = played[-_LAST_N:]
        short = played[-_LAST_SHORT_N:]
        on_surface = [m for m in played if surface and m.surface == surface][-_SURFACE_N:]

        streak = 0
        for m in reversed(played):
            if m.won != played[-1].won:
                break
            streak += 1
        if not played[-1].won:
            streak = -streak

        return {
            "experience": float(len(played)),
            "rest_days": float((before - last.date).days),
            "matches_10d": float(sum(1 for m in played if (before - m.date).days <= 10)),
            "matches_30d": float(sum(1 for m in played if (before - m.date).days <= 30)),
            "streak": float(streak),
            "win_rate_last_20": sum(m.won for m in recent) / len(recent),
            "win_rate_last_3": sum(m.won for m in short) / len(short),
            "win_rate_surface": (sum(m.won for m in on_surface) / len(on_surface)) if on_surface else None,
        }

    def h2h(
        self,
        p1_id: int,
        p2_id: int,
        before: dt.date,
        surface: Optional[str] = None,
    ) -> tuple[int, int]:
        """(p1 wins, p2 wins) in meetings strictly before `before`.

        This is the feature the old export got most wrong: the `h2h` table is a running
        total that already includes the match being predicted.
        """
        p1_wins = p2_wins = 0
        for m in self.prior(p1_id, before):
            if m.opponent_id != p2_id:
                continue
            if surface is not None and m.surface != surface:
                continue
            if m.won:
                p1_wins += 1
            else:
                p2_wins += 1
        return p1_wins, p2_wins


def h2h_win_pct(p1_wins: int, p2_wins: int) -> Optional[float]:
    """p1's share of prior meetings, or None when they have never played."""
    total = p1_wins + p2_wins
    return (p1_wins / total) if total else None
