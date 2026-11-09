"""27l2's pre-registered rule for which kicker fantasy formula PrizePicks uses.

Each matched kicker-game has a standard full-game fantasy line and a
kicking-points line (3 per FG, 1 per PAT) from PrizePicks. Their difference is
what PrizePicks expects the fantasy formula to add over flat scoring, so for
the true formula F the residual

    z = (fantasy line - kicking line) - (F(game) - flat(game))

averages zero. The constants and branch order below are the registration:
changing one after a candidate is scored on real data is a new rule, not an edit.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from math import sqrt
from statistics import fmean, stdev
from typing import Literal

from app.core.nfl_kicking import CANDIDATE_FORMULAS, FLAT_KICKING, KickingFormula, kicking_points

DECISION_THROUGH_WEEK = 8
MIN_MATCHED = 60
CONSISTENT_Z = 1.96
ANCHOR_OVER_RATE = (0.35, 0.65)

VerdictOutcome = Literal["insufficient", "anchor_broken", "unresolved", "pinned"]
FormulaTerm = Literal["fg_by_distance", "pat_points", "fg_miss_points", "pat_miss_points"]
FORMULA_TERMS: tuple[FormulaTerm, ...] = ("fg_by_distance", "pat_points", "fg_miss_points", "pat_miss_points")


@dataclass(frozen=True)
class MatchedKick:
    fantasy_line: float
    kicking_line: float
    # Every column any candidate reads, all non-NULL (the loader leaves out a game otherwise).
    stats: Mapping[str, int | None]


@dataclass(frozen=True)
class CandidateRead:
    formula: KickingFormula
    n: int
    mean_z: float | None
    standard_error: float | None

    @property
    def consistent(self) -> bool:
        if self.mean_z is None or self.standard_error is None:
            return False
        return abs(self.mean_z) <= CONSISTENT_Z * self.standard_error


@dataclass(frozen=True)
class UnresolvedTerm:
    term: FormulaTerm
    # Mean over matched games of (score with the other consistent value) - (pinned score).
    average_effect: float


@dataclass(frozen=True)
class KickerScoringVerdict:
    outcome: VerdictOutcome
    matched: int
    anchor_over_rate: float | None
    reads: tuple[CandidateRead, ...]
    pinned: KickingFormula | None
    unresolved_terms: tuple[UnresolvedTerm, ...]


def _points(formula: KickingFormula, game: MatchedKick) -> float:
    points = kicking_points(formula, game.stats)
    if points is None:
        raise ValueError(f"a matched kicker-game is missing a column {formula.name} reads")
    return points


def residual(formula: KickingFormula, game: MatchedKick) -> float:
    line_gap = game.fantasy_line - game.kicking_line
    return line_gap - (_points(formula, game) - _points(FLAT_KICKING, game))


def candidate_read(formula: KickingFormula, matched: Sequence[MatchedKick]) -> CandidateRead:
    residuals = [residual(formula, game) for game in matched]
    if len(residuals) < 2:
        return CandidateRead(formula, len(residuals), fmean(residuals) if residuals else None, None)
    return CandidateRead(formula, len(residuals), fmean(residuals), stdev(residuals) / sqrt(len(residuals)))


def anchor_over_rate(matched: Sequence[MatchedKick]) -> float | None:
    """How often the kicking-points line went over under flat scoring; pushes excluded."""
    overs = unders = 0
    for game in matched:
        actual = _points(FLAT_KICKING, game)
        overs += actual > game.kicking_line
        unders += actual < game.kicking_line
    return overs / (overs + unders) if overs + unders else None


def _penalty_count(formula: KickingFormula) -> int:
    return (formula.fg_miss_points != 0) + (formula.pat_miss_points != 0)


def _unresolved_terms(
    pinned: KickingFormula, consistent: Sequence[KickingFormula], matched: Sequence[MatchedKick],
) -> tuple[UnresolvedTerm, ...]:
    terms = []
    for term in FORMULA_TERMS:
        others = sorted({getattr(f, term) for f in consistent} - {getattr(pinned, term)})
        for value in others:
            alternative = replace(pinned, name=f"{pinned.name}:{term}={value}", **{term: value})
            effect = fmean(_points(alternative, game) - _points(pinned, game) for game in matched)
            terms.append(UnresolvedTerm(term, effect))
    return tuple(terms)


def kicker_scoring_verdict(
    matched: Sequence[MatchedKick], candidates: Sequence[KickingFormula] = CANDIDATE_FORMULAS,
) -> KickerScoringVerdict:
    reads = tuple(candidate_read(formula, matched) for formula in candidates)
    anchor = anchor_over_rate(matched)

    def verdict(outcome: VerdictOutcome, pinned: KickingFormula | None = None,
                unresolved: tuple[UnresolvedTerm, ...] = ()) -> KickerScoringVerdict:
        return KickerScoringVerdict(outcome, len(matched), anchor, reads, pinned, unresolved)

    if len(matched) < MIN_MATCHED:
        return verdict("insufficient")
    low, high = ANCHOR_OVER_RATE
    if anchor is None or not low <= anchor <= high:
        return verdict("anchor_broken")
    consistent = [read for read in reads if read.consistent]
    if not consistent:
        return verdict("unresolved")
    best = min(consistent, key=lambda r: (_penalty_count(r.formula), abs(r.mean_z or 0.0), r.formula.name))
    return verdict("pinned", best.formula, _unresolved_terms(best.formula, [r.formula for r in consistent], matched))
