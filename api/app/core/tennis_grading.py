"""Scoring stored tennis predictions against results and the closing market.

Pure functions only: the loader and the report live elsewhere. Log loss and Brier
come from the NFL backtest module so every sport scores the same way.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from math import log, sqrt
from typing import Iterable, Optional

from app.core.nfl_td_backtest import brier, log_loss

_PROBABILITY_FLOOR = 1e-6
_SET_SCORE = re.compile(r"(\d+)-(\d+)")


@dataclass(frozen=True)
class ComponentScore:
    n: int
    log_loss: float
    brier: float
    mean_predicted: float
    actual_rate: float


def score_component(probabilities: list[float], outcomes: list[bool]) -> ComponentScore:
    return ComponentScore(
        n=len(probabilities),
        log_loss=log_loss(probabilities, outcomes),
        brier=brier(probabilities, outcomes),
        mean_predicted=sum(probabilities) / len(probabilities),
        actual_rate=sum(outcomes) / len(outcomes),
    )


def _match_log_loss(probability: float, outcome: bool) -> float:
    p = min(max(probability, _PROBABILITY_FLOOR), 1 - _PROBABILITY_FLOOR)
    return -log(p if outcome else 1 - p)


@dataclass(frozen=True)
class PairedDifference:
    n: int
    mean: float
    """Mean of (candidate log loss - baseline log loss); negative favors the candidate."""
    standard_error: Optional[float]


def paired_loss_difference(
    candidate: list[float], baseline: list[float], outcomes: list[bool],
) -> PairedDifference:
    """Per-match log-loss difference, so a comparison carries its own error bar.

    Pairing on the same matches removes the match-to-match noise both forecasts
    share, which is most of it: a coin-flip match is hard for everyone.
    """
    if not outcomes or not (len(candidate) == len(baseline) == len(outcomes)):
        raise ValueError("paired_loss_difference needs equal, non-empty inputs")
    diffs = [
        _match_log_loss(c, o) - _match_log_loss(b, o)
        for c, b, o in zip(candidate, baseline, outcomes)
    ]
    n = len(diffs)
    mean = sum(diffs) / n
    if n < 2:
        return PairedDifference(n, mean, None)
    variance = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    return PairedDifference(n, mean, sqrt(variance / n))


@dataclass(frozen=True)
class CalibrationBin:
    low: float
    high: float
    n: int
    mean_predicted: float
    actual_rate: float


def calibration_bins(probabilities: list[float], outcomes: list[bool], width: float = 0.1) -> list[CalibrationBin]:
    """Fixed-width bins, empty ones omitted. A probability of 1.0 falls in the top bin."""
    count = round(1 / width)
    grouped: dict[int, list[tuple[float, bool]]] = {}
    for p, o in zip(probabilities, outcomes):
        grouped.setdefault(min(int(p / width), count - 1), []).append((p, o))
    return [
        CalibrationBin(
            low=i * width,
            high=(i + 1) * width,
            n=len(members),
            mean_predicted=sum(p for p, _ in members) / len(members),
            actual_rate=sum(o for _, o in members) / len(members),
        )
        for i, members in sorted(grouped.items())
    ]


@dataclass(frozen=True)
class ClvSummary:
    eligible: int
    moved: int
    toward: int
    mean_move_toward: float
    """Mean of move x sign(gap) over eligible rows, unmoved rows counting as 0."""

    @property
    def unmoved(self) -> int:
        return self.eligible - self.moved

    @property
    def toward_rate(self) -> Optional[float]:
        return self.toward / self.moved if self.moved else None


def clv_summary(
    rows: Iterable[tuple[Optional[float], Optional[float], Optional[float]]],
    min_gap: float = 0.0,
) -> ClvSummary:
    """Did the market move toward the model between the prediction and the start?

    Each row is (model, market at prediction, market at close), all for the same
    side. Rows missing a price, or where the model agreed with the market, have no
    direction to move toward and are not eligible.
    """
    eligible = moved = toward = 0
    total = 0.0
    for model, opening, closing in rows:
        if model is None or opening is None or closing is None:
            continue
        gap = model - opening
        if gap == 0 or abs(gap) < min_gap:
            continue
        eligible += 1
        move = closing - opening
        signed = move if gap > 0 else -move
        total += signed
        if move != 0:
            moved += 1
            if signed > 0:
                toward += 1
    return ClvSummary(eligible, moved, toward, total / eligible if eligible else 0.0)


def _finished_set(a: int, b: int) -> bool:
    high, low = max(a, b), min(a, b)
    return (high == 6 and low <= 4) or (high == 7 and low in (5, 6))


def is_completed_score(score: Optional[str], best_of: int = 3) -> bool:
    """Whether a score is a match played to the end: no retirement, no walkover.

    Retirements stop mid-set ("3-6 3-5") and walkovers have no score. Books settle
    those unevenly, and neither says anything about who was the better player.
    """
    sets = [(int(a), int(b)) for a, b in _SET_SCORE.findall(score or "")]
    if not sets or not all(_finished_set(a, b) for a, b in sets):
        return False
    needed = best_of // 2 + 1
    p1_sets = sum(a > b for a, b in sets)
    p2_sets = len(sets) - p1_sets
    last_a, last_b = sets[-1]
    last_winner_sets = p1_sets if last_a > last_b else p2_sets
    # The final set must be the one that clinched it, so "6-4 6-3 4-6" is not a finish.
    return last_winner_sets == needed and min(p1_sets, p2_sets) < needed
