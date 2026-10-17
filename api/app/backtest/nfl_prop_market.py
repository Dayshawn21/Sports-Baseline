"""Report the forward holdout of sportsbook anytime-TD prices against results.

The Odds API sells current markets only, so there is no historical sample to
score: it accrues week by week from prices already stored, at roughly 350
player-games a week. This report prints what has accrued so far and how the raw
book price, the 25a de-vigged price, and the production model score on it.

It reads and prints. Nothing is fitted, stored, or fed back into a projection.

Pre-registered rule for item 25c, fixed on 2026-09-19, when zero priced
player-games had settled:

  - Minimum sample: 2000 settled common-subset player-games, where every arm has
    a probability. Roughly week 8 to 12 of 2026.
  - Pass: book_devig beats book_raw on log loss and on Brier, with a mean
    predicted closer to the actual rate. All three, not two of three.
  - The model arm is reported as context for whether rating against the market is
    worth doing. It does not decide whether the de-vig is right.
  - Scored once, at the first run that clears the minimum. Every earlier run is a
    coverage check, not a decision: judging weekly until a week passes would turn
    the holdout into a search.
  - A fail is a live outcome. 19j, 19n, 24b, 24c, and 24e all failed theirs, and
    25c does not ship on a near miss.

Run from api/: python -m app.backtest.nfl_prop_market
"""
from __future__ import annotations

import asyncio
import sys
from typing import Sequence

from app.core.nfl_prop_market import (
    ARMS,
    PropCase,
    PropCoverage,
    SettledPropRow,
    build_prop_cases,
    by_week,
    coverage,
    score_arm,
)
from app.core.nfl_td_backtest import NflTdScore, build_cases, production_probability

HEADER = f"{'week':<10}{'cases':>7}  {'arm':<11}{'log loss':>10}{'brier':>9}{'predicted':>11}{'actual':>8}"


def _arm_lines(label: str, cases: Sequence[PropCase]) -> list[str]:
    scores = {arm: score_arm(cases, arm) for arm in ARMS}
    subset = next((score.games for score in scores.values() if score is not None), 0)
    lines = []
    for index, arm in enumerate(ARMS):
        score = scores[arm]
        prefix = f"{label:<10}{subset:>7}  " if index == 0 else f"{'':<10}{'':>7}  "
        lines.append(prefix + (_score(arm, score) if score else f"{arm:<11}{'no settled cases':>38}"))
    return lines


def _score(arm: str, score: NflTdScore) -> str:
    return (
        f"{arm:<11}{score.log_loss:>10.5f}{score.brier:>9.5f}"
        f"{score.mean_predicted:>11.3f}{score.actual_rate:>8.3f}"
    )


def _coverage_lines(counts: PropCoverage) -> list[str]:
    return [
        "Coverage",
        f"  priced player-games   {counts.priced_player_games:>6}",
        f"  unresolved player     {counts.unresolved:>6}  (name never linked, cannot be settled)",
        f"  settled               {counts.settled:>6}",
        f"  did not play          {counts.did_not_play:>6}  (voided by the book, never a miss)",
        f"  settled, no total     {counts.missing_total:>6}  (no de-vigged arm)",
        f"  settled, no model     {counts.missing_model:>6}  (too little player history)",
        f"  common subset         {counts.common_subset:>6}  (all three arms present)",
    ]


# Pre-registered at 25b, before any priced game had settled, so the rule cannot
# be chosen after seeing the numbers.
MINIMUM_SAMPLE = 2000
RULE = (
    "Pre-registered rule for 25c: adopt only once the common subset reaches "
    f"{MINIMUM_SAMPLE} settled player-games, and only if book_devig beats book_raw on "
    "both log loss and Brier with a mean predicted closer to the actual rate. "
    "The model arm is context, not a gate. Judged once, at the first run that "
    "clears the minimum; weekly runs before that are coverage checks, not decisions."
)


def _verdict(counts: PropCoverage) -> str:
    if counts.common_subset >= MINIMUM_SAMPLE:
        return f"Sample assessable: {counts.common_subset} common-subset player-games. Score the rule once, now."
    weeks = -(-(MINIMUM_SAMPLE - counts.common_subset) // 350)
    return (
        f"Sample not yet assessable: {counts.common_subset} of {MINIMUM_SAMPLE} common-subset "
        f"player-games, roughly {weeks} more weeks at 350 a week."
    )


def report(rows: Sequence[SettledPropRow], cases: Sequence[PropCase]) -> str:
    counts = coverage(rows, cases)
    lines = [HEADER, "-" * len(HEADER)]
    for (season, week), week_cases in by_week(cases):
        lines.extend(_arm_lines(f"{season} w{week}", week_cases))
    lines.extend(["-" * len(HEADER), *_arm_lines("all", cases), "", *_coverage_lines(counts), "", _verdict(counts), RULE])
    return "\n".join(lines)


async def _main() -> None:
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    async with SessionLocal() as db:
        rows = await nfl_repo.get_settled_prop_prices(db)
        seasons = frozenset(row.season for row in rows)
        td_rows = await nfl_repo.get_weekly_td_rows(db) if seasons else []
        snap_rows = await nfl_repo.get_snap_rows(db) if seasons else []

    model = {
        (case.player_id, case.season, case.week): production_probability(case)
        for case in build_cases(td_rows, seasons, snap_rows)
    }
    print(report(rows, build_prop_cases(rows, model)))


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
