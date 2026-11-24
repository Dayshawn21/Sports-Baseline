"""Kicker scoring check: 27l2's pre-registered rule on the 2026 PrizePicks kicker lines.

Read-only. Pairs each kicker-game's standard full-game fantasy line with its
kicking-points line, scores every candidate formula through
`kicker_scoring_verdict`, and prints the verdict. The week bound is the rule's
constant, not a flag: the sample was fixed before any candidate was scored.

Run from api/: python -m app.backtest.nfl_kicker_scoring [--season 2026]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median

from app.core.nfl_kicker_scoring_check import (
    ANCHOR_OVER_RATE,
    CONSISTENT_Z,
    DECISION_THROUGH_WEEK,
    MIN_MATCHED,
    CandidateRead,
    KickerScoringVerdict,
    MatchedKick,
    kicker_scoring_verdict,
)
from app.core.nfl_kicking import CANDIDATE_FORMULAS, KickingFormula, kicking_points
from app.core.prop_settlement import settle
from app.repositories.nfl import KickerGameLines

# The commit that fixed the rule and the candidates before any was scored on real data.
PREREGISTRATION_COMMIT = "14b36ea5cb07ac2d1ec8df065ddf7bd3142cd986"


@dataclass(frozen=True)
class KickerScoringSample:
    matched: tuple[MatchedKick, ...]
    # Every fantasy line with a complete stat row, matched or not, for the over rates.
    fantasy_lines: tuple[tuple[float, Mapping[str, int | None]], ...]
    counts: Mapping[str, int]
    median_fetch_gap_minutes: float | None


def _complete(stats: Mapping[str, int | None]) -> bool:
    return all(value is not None for value in stats.values())


def build_sample(rows: Sequence[KickerGameLines]) -> KickerScoringSample:
    matched: list[MatchedKick] = []
    fantasy_lines: list[tuple[float, Mapping[str, int | None]]] = []
    gaps: list[float] = []
    counts = {"loaded": len(rows), "matched": 0, "fantasy only": 0, "kicking only": 0, "no stat row or a NULL column": 0}
    for row in rows:
        stats = row.stats
        if stats is None or not _complete(stats):
            counts["no stat row or a NULL column"] += 1
            continue
        if row.fantasy_line is not None:
            fantasy_lines.append((row.fantasy_line, stats))
        if row.fantasy_line is not None and row.kicking_line is not None:
            counts["matched"] += 1
            matched.append(MatchedKick(row.fantasy_line, row.kicking_line, stats))
            if row.fantasy_fetched_at is not None and row.kicking_fetched_at is not None:
                gaps.append(abs((row.fantasy_fetched_at - row.kicking_fetched_at).total_seconds()) / 60)
        elif row.fantasy_line is not None:
            counts["fantasy only"] += 1
        else:
            counts["kicking only"] += 1
    return KickerScoringSample(tuple(matched), tuple(fantasy_lines), counts, median(gaps) if gaps else None)


def _over_rate(formula: KickingFormula, lines: Sequence[tuple[float, Mapping[str, int | None]]]) -> tuple[float | None, int]:
    outcomes = []
    for line, stats in lines:
        points = kicking_points(formula, stats)
        if points is not None:
            outcomes.append(settle(points, line))
    decided = outcomes.count("over") + outcomes.count("under")
    return (outcomes.count("over") / decided if decided else None), outcomes.count("push")


def _percent(rate: float | None) -> str:
    return "-" if rate is None else f"{rate:.1%}"


def _number(value: float | None, sign: bool = False) -> str:
    if value is None:
        return "-"
    return f"{value:+.3f}" if sign else f"{value:.3f}"


def _candidate_line(read: CandidateRead, sample: KickerScoringSample) -> str:
    all_rate, pushes = _over_rate(read.formula, sample.fantasy_lines)
    matched_rate, _ = _over_rate(read.formula, [(game.fantasy_line, game.stats) for game in sample.matched])
    return (
        f"  {read.formula.name:34} {read.n:>4} {_number(read.mean_z, sign=True):>8} {_number(read.standard_error):>7}"
        f" {'yes' if read.consistent else 'no':>10} {_percent(all_rate):>8} {_percent(matched_rate):>8} {pushes:>6}"
    )


def _verdict_lines(verdict: KickerScoringVerdict) -> list[str]:
    lines = [f"Verdict: {verdict.outcome}" + (f" {verdict.pinned.name}" if verdict.pinned else "")]
    if verdict.pinned is None:
        lines.append("  nothing pinned: K and P fantasy lines stay hidden, and 27l3 waits for a new pre-registration")
    for term in verdict.unresolved_terms:
        lines.append(
            f"  unresolved by this sample: {term.term} (the other consistent value moves a kicker"
            f" {term.average_effect:+.3f} points a game on average)"
        )
    return lines


def report(season: int, sample: KickerScoringSample) -> str:
    verdict = kicker_scoring_verdict(sample.matched, CANDIDATE_FORMULAS)
    gap = "-" if sample.median_fetch_gap_minutes is None else f"{sample.median_fetch_gap_minutes:.0f} min"
    low, high = ANCHOR_OVER_RATE
    lines = [
        f"Kicker scoring check, {season} weeks 1-{DECISION_THROUGH_WEEK} (27l2, pre-registered {PREREGISTRATION_COMMIT[:8]})",
        "",
        "Coverage (K player-games, standard full-game lines, last snapshot before kickoff)",
        *(f"  {label:30} {count:>5}" for label, count in sample.counts.items()),
        f"  median gap between paired lines' snapshots: {gap}",
        "",
        f"Candidates: mean z = mean of (fantasy line - kicking line) - (F - flat); consistent when |mean z| <= {CONSISTENT_Z} SE",
        f"  {'formula':34} {'n':>4} {'mean z':>8} {'SE':>7} {'consistent':>10} {'over all':>8} {'over mat':>8} {'pushes':>6}",
        *(
            _candidate_line(read, sample)
            for read in sorted(verdict.reads, key=lambda r: (r.mean_z is None, abs(r.mean_z or 0.0), r.formula.name))
        ),
        "  (over rates: fantasy lines settled under that formula, pushes excluded; they are reported, never deciding)",
        "",
        f"Anchor: kicking-points over rate under flat scoring {_percent(verdict.anchor_over_rate)}"
        f" (must be {low:.0%} to {high:.0%}); matched {verdict.matched} (need {MIN_MATCHED})",
        "",
        *_verdict_lines(verdict),
    ]
    return "\n".join(lines)


async def run(season: int) -> str:
    from app.db.pool import SessionLocal
    from app.repositories.nfl import get_kicker_scoring_rows

    async with SessionLocal() as db:
        rows = await get_kicker_scoring_rows(db, season, DECISION_THROUGH_WEEK)
    return report(season, build_sample(rows))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply 27l2's pre-registered kicker scoring rule to PrizePicks' lines")
    parser.add_argument("--season", type=int, default=2026)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print(asyncio.run(run(args.season)))


if __name__ == "__main__":
    main()
