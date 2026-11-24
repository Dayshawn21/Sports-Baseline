"""Grade stored pre-match PrizePicks projections by stat, and by confidence tier up to props-v2 (26f).

Read-only. Each graded row is the app's own recommendation, frozen before the
start by app.ingest.prop_snapshots, settled against the final score or, for
aces, double faults and break points, the one box score that joins the match.

Run from api/: python -m app.backtest.tennis_prop_snapshots
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from dataclasses import dataclass
from math import sqrt

from app.core.box_score_join import JoinResult
from app.core.prop_ev import leg_decimal_odds
from app.core.prop_projection import normalize_stat_type
from app.core.prop_settlement import resolve_actual, settle
from app.core.tennis_grading import calibration_bins, is_completed_score
from app.repositories.prop_snapshots import GradedPropSnapshot
from app.services.tennis.prop_snapshots import PROJECTION_VERSION

TIERS = ("LOCK", "STRONG", "LEAN", "PASS")
# Tennis props carry no tier from 48f on; early props-v3 rows hold a LEAN or PASS
# that nothing grades.
TIERED_VERSIONS = ("props-v1", "props-v2")
Pair = tuple[int, int]
ODDS_TYPES = ("standard", "goblin", "demon")


@dataclass(frozen=True)
class GradedPick:
    row: GradedPropSnapshot
    odds_type: str
    hit: bool | None
    """None on a push."""
    units: float


@dataclass(frozen=True)
class Awaiting:
    no_recommendation: int
    not_settleable: Counter[str]
    incomplete_score: int
    unjoined: Counter[str]
    """Box-score picks left ungraded, by join reason."""


def grade(
    rows: list[GradedPropSnapshot], joins: dict[Pair, JoinResult] | None = None,
) -> tuple[list[GradedPick], Awaiting]:
    joins = joins or {}
    picks: list[GradedPick] = []
    no_recommendation = incomplete = 0
    not_settleable: Counter[str] = Counter()
    unjoined: Counter[str] = Counter()
    for row in rows:
        stat = normalize_stat_type(row.stat_type)
        if row.recommendation is None:
            no_recommendation += 1
        elif not is_completed_score(row.score, row.best_of or 3):
            incomplete += 1
        else:
            actual, reason = resolve_actual(stat, row.score, row.player_is_p1, joins.get((row.player_id, row.match_id)))
            if actual is None:
                if reason == "not_settleable":
                    not_settleable[stat] += 1
                else:
                    unjoined[str(reason)] += 1
                continue
            outcome = settle(actual, row.line)
            odds_type = (row.odds_type or "standard").lower()
            decimal = leg_decimal_odds(odds_type, source="prizepicks") or 0.0
            hit = None if outcome == "push" else outcome == row.recommendation.lower()
            units = 0.0 if hit is None else (decimal - 1.0 if hit else -1.0)
            picks.append(GradedPick(row, odds_type, hit, units))
    return picks, Awaiting(no_recommendation, not_settleable, incomplete, unjoined)


def _row(label: str, picks: list[GradedPick], odds_type: str, width: int = 18) -> str:
    decided = [p for p in picks if p.hit is not None]
    pushes = len(picks) - len(decided)
    units = sum(p.units for p in picks) / len(picks)
    if not decided:
        return f"  {label:<{width}}{len(picks):>5} {pushes:>5}   {'n/a':>6}{'':<10}  {'':>6}  {'':>7}  {units:+7.3f}"
    hit = sum(p.hit for p in decided) / len(decided)
    # Goblin and demon lines stack several per player-stat and move together, so
    # a binomial error bar would claim far more evidence than they carry.
    se = f" +/- {sqrt(hit * (1 - hit) / len(decided)):.1%}" if odds_type == "standard" else ""
    probs = [p.row.hit_probability for p in decided if p.row.hit_probability is not None]
    mean_prob = sum(probs) / len(probs) if probs else None
    prob_text = f"{mean_prob:6.1%}" if mean_prob is not None else f"{'n/a':>6}"
    gap_text = f"{hit - mean_prob:+7.1%}" if mean_prob is not None else f"{'n/a':>7}"
    return f"  {label:<{width}}{len(picks):>5} {pushes:>5}   {hit:6.1%}{se:<10}  {prob_text}  {gap_text}  {units:+7.3f}"


_HEADER = (f"  {'tier':<18}{'n':>5} {'push':>5}   {'hit':>6}{'':<10}  {'p(hit)':>6}  {'hit-p':>7}  "
           f"{'units':>7}")


def _tier_section(picks: list[GradedPick], version: str) -> list[str]:
    if version not in TIERED_VERSIONS:
        return [f"By confidence tier: no tiers under {version} (retired by 48f)"]
    lines = ["By confidence tier and odds type (hit excludes pushes; units per line at the app's assumed payout)",
             _HEADER]
    for odds_type in ODDS_TYPES:
        of_type = [p for p in picks if p.odds_type == odds_type]
        lines.append(f" {odds_type} ({len(of_type)} picks)")
        for tier in TIERS:
            in_tier = [p for p in of_type if p.row.confidence == tier]
            if in_tier:
                lines.append(_row(tier, in_tier, odds_type))
    return lines


_STAT_WIDTH = 26


def _stat_section(picks: list[GradedPick]) -> list[str]:
    """Per stat, so a newly projected stat (16e's first-set lines) reads apart from its tier."""
    lines = ["By stat and odds type",
             f"  {'stat':<{_STAT_WIDTH}}" + _HEADER[2 + 18:]]
    for odds_type in ODDS_TYPES:
        of_type = [p for p in picks if p.odds_type == odds_type]
        if not of_type:
            continue
        lines.append(f" {odds_type}")
        for stat in sorted({normalize_stat_type(p.row.stat_type) for p in of_type}):
            in_stat = [p for p in of_type if normalize_stat_type(p.row.stat_type) == stat]
            lines.append(_row(stat, in_stat, odds_type, _STAT_WIDTH))
    return lines


def _calibration_section(picks: list[GradedPick]) -> list[str]:
    decided = [p for p in picks if p.odds_type == "standard" and p.hit is not None
               and p.row.hit_probability is not None]
    if not decided:
        return ["Calibration (standard lines): no decided picks yet"]
    bins = calibration_bins([p.row.hit_probability for p in decided], [bool(p.hit) for p in decided])
    cells = "  ".join(f"{b.low:.1f}-{b.high:.1f}: {b.mean_predicted:.2f}/{b.actual_rate:.2f} (n={b.n})" for b in bins)
    return ["Calibration (standard lines, predicted vs actual hit rate)", f"  {cells}"]


def report(
    rows: list[GradedPropSnapshot], version: str = PROJECTION_VERSION, joins: dict[Pair, JoinResult] | None = None,
) -> str:
    picks, awaiting = grade(rows, joins)
    totals = [
        f"PrizePicks projection grading - {version}",
        "  (the daily scheduled snapshot, not necessarily what a later page view showed)",
        f"  latest pre-start snapshots of finished matches: {len(rows)}",
        f"  no recommendation (blocked by the page):        {awaiting.no_recommendation}",
        f"  retirement, walkover or bad score:              {awaiting.incomplete_score}",
        f"  box-score stat with no join (yet):              {sum(awaiting.unjoined.values())}",
    ]
    for reason, count in awaiting.unjoined.most_common():
        totals.append(f"    {reason:<44}{count:>6}")
    totals.append(f"  no settlement source:                           {sum(awaiting.not_settleable.values())}")
    for stat, count in awaiting.not_settleable.most_common():
        totals.append(f"    {stat:<44}{count:>6}")
    totals.append(f"  graded:                                         {len(picks)}")
    sections = [totals, _tier_section(picks, version), _stat_section(picks), _calibration_section(picks)]
    return "\n\n".join("\n".join(section) for section in sections)


async def _main() -> None:
    from app.db.pool import SessionLocal
    from app.repositories.player_match_stats import get_box_score_candidates
    from app.repositories.prop_snapshots import get_graded_prop_snapshots

    parser = argparse.ArgumentParser(description="Grade stored PrizePicks projections")
    parser.add_argument("--version", default=PROJECTION_VERSION)
    args = parser.parse_args()
    async with SessionLocal() as db:
        rows = await get_graded_prop_snapshots(db, args.version)
        contexts = await get_box_score_candidates(db, sorted({(row.player_id, row.match_id) for row in rows}))
    print(report(rows, args.version, {pair: context.join() for pair, context in contexts.items()}))


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
