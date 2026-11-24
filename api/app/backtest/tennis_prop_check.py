"""Forward prop check: 48e's pre-registered rule on settled PrizePicks tennis snapshots.

Read-only. Each line is graded on its latest pre-start snapshot, settled as the
26f report settles it, and every slice with a pick reports its state. A slice
that has not fixed its verdict sample shows only its size, never a running hit
rate, so nobody retunes on a number the rule has not judged yet.

Run from api/: python -m app.backtest.tennis_prop_check [--version props-v3] [--as-of YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from statistics import NormalDist

from app.core.box_score_join import JoinResult
from app.core.tennis_prop_check import (
    TENNIS_PROP_CHECK_RULE, TENNIS_STANDARD_ERRORS_REQUIRED, CheckResult, TennisFrozenLine, check,
    settled_outcome,
)
from app.repositories.prop_snapshots import PropCheckSnapshot
from app.services.tennis.prop_snapshots import PROJECTION_VERSION

Pair = tuple[int, int]
FALSE_ADOPT_RATE = 1 - NormalDist().cdf(TENNIS_STANDARD_ERRORS_REQUIRED)


def to_frozen_lines(rows: Sequence[PropCheckSnapshot], joins: Mapping[Pair, JoinResult]) -> list[TennisFrozenLine]:
    return [
        TennisFrozenLine(
            line_id=row.snapshot_id, player_id=row.player_id, match_id=row.match_id, stat_type=row.stat_type,
            match_tour=row.match_tour, p1_tour=row.p1_tour, p2_tour=row.p2_tour, odds_type=row.odds_type,
            start_time=row.start_time, p_over=row.p_over, p_under=row.p_under, p_push=row.p_push,
            market_total_games=row.market_total_games, data_quality_flags=row.data_quality_flags,
            outcome=settled_outcome(
                row.stat_type, row.line, row.score, row.best_of, row.player_is_p1,
                joins.get((row.player_id, row.match_id)),
            ),
        )
        for row in rows
    ]


def _pct(value: float | None) -> str:
    return f"{value:.1%}" if value is not None else "-"


def report(result: CheckResult, version: str, as_of: date) -> str:
    funnel = result.funnel
    excluded = ", ".join(f"{reason} {count}" for reason, count in sorted(result.exclusions.items())) or "none"
    decided = sum(s.verdict != "insufficient" for s in result.slices.values())
    se = f"{TENNIS_STANDARD_ERRORS_REQUIRED:g}"
    lines = [
        f"Tennis forward prop check - {TENNIS_PROP_CHECK_RULE} on {version} (as of {as_of.isoformat()})",
        f"  frozen rows {funnel.rows} | excluded: {excluded}",
        f"  calls {funnel.calls} | picks {funnel.picks} | bets {funnel.bets} | finished weeks {result.finished_weeks}",
        f"  decided slices {decided} | expected false adopts at {se} SE: {decided * FALSE_ADOPT_RATE:.3f}",
    ]
    if not result.slices:
        return "\n".join(lines + ["  no slice has a pick yet"])
    lines.append(f"  {'stat':<26}{'tour':<12}{'anchor':<7}{'odds':<9}{'side':<6}{'n':>5}{'weeks':>6}"
                 f"{'hit':>8}{'SE':>7}{'lower':>8}{'b/e':>8}  reads")
    for key, s in result.slices.items():
        is_decided = s.verdict != "insufficient"
        hit = s.hit_rate if is_decided else None
        error = s.standard_error if is_decided else None
        lower = hit - TENNIS_STANDARD_ERRORS_REQUIRED * error if hit is not None and error is not None else None
        reads = "adopt" if s.verdict == "adopt" else ("hide (reject, final)" if is_decided else "hide (insufficient)")
        lines.append(
            f"  {key.stat:<26}{key.tour:<12}{key.anchor:<7}{key.odds_type:<9}{key.side:<6}{s.n:>5}{s.periods:>6}"
            f"{_pct(hit):>8}{_pct(error):>7}{_pct(lower):>8}{_pct(s.break_even):>8}  {reads}"
        )
    return "\n".join(lines)


async def _main(version: str, as_of: date) -> None:
    from app.db.pool import SessionLocal
    from app.repositories.player_match_stats import get_box_score_candidates
    from app.repositories.prop_snapshots import get_prop_check_snapshots

    async with SessionLocal() as db:
        rows = await get_prop_check_snapshots(db, version)
        contexts = await get_box_score_candidates(db, sorted({(row.player_id, row.match_id) for row in rows}))
    joins = {pair: context.join() for pair, context in contexts.items()}
    print(report(check(to_frozen_lines(rows, joins), as_of), version, as_of))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply 48e's pre-registered rule to settled tennis prop snapshots")
    parser.add_argument("--version", default=PROJECTION_VERSION, help="projection version; never pooled")
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(UTC).date())
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.version, args.as_of))
