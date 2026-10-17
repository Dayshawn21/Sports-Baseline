"""Level check for the first-set chain against completed 2026 first sets (16e).

Read-only. It compares the chain's mean first-set games with what was played,
by tour, using each player's current all-surface rolling stats. Those stats are
overwritten in place, so they already include these matches: the check reads
the mean bias only, never per-match accuracy.

Run from api/: python -m app.backtest.tennis_first_set_level [--since 2026-01-01]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import date

from app.core.prop_projection import serve_hold
from app.core.prop_settlement import parse_sets
from app.core.tennis_grading import is_completed_score
from app.core.tennis_first_set import first_set_distribution
from app.repositories.matches import CompletedMatchScore
from app.repositories.players import PlayerRollingStats

# Pre-registered in the 16e spec: stop before any projection is shown beyond this.
MAX_TOTAL_GAMES_BIAS = 0.5


@dataclass(frozen=True)
class FirstSetCase:
    tour: str
    actual_total: int
    actual_p1: int
    model_total: float
    model_p1: float


def build_cases(
    matches: list[CompletedMatchScore], stats: dict[tuple[int, str | None], PlayerRollingStats],
) -> tuple[list[FirstSetCase], int]:
    """(cases, skipped for missing stats). Unfinished matches are left out, not counted."""
    cases = []
    skipped = 0
    for match in matches:
        if not is_completed_score(match.score, match.best_of):
            continue
        p1_stats, p2_stats = stats.get((match.p1_id, None)), stats.get((match.p2_id, None))
        if p1_stats is None or p2_stats is None:
            skipped += 1
            continue
        p1_games, p2_games = parse_sets(match.score)[0]
        dist = first_set_distribution(serve_hold(p1_stats), serve_hold(p2_stats))
        cases.append(FirstSetCase(match.tour, p1_games + p2_games, p1_games, dist.mean_total_games, dist.mean_player_games))
    return cases, skipped


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def report(cases: list[FirstSetCase], skipped: int) -> str:
    lines = [
        f"First-set level check: {len(cases)} completed ATP/WTA matches, {skipped} skipped for missing stats",
        f"Stop if the total-games bias exceeds {MAX_TOTAL_GAMES_BIAS} games in either tour (pre-registered).",
        f"  {'tour':<6}{'n':>6}{'actual':>9}{'model':>9}{'bias':>8}{'p1 act':>9}{'p1 mod':>9}{'p1 bias':>9}  verdict",
    ]
    for tour in sorted({case.tour for case in cases}):
        group = [case for case in cases if case.tour == tour]
        actual = _mean([case.actual_total for case in group])
        model = _mean([case.model_total for case in group])
        p1_actual = _mean([case.actual_p1 for case in group])
        p1_model = _mean([case.model_p1 for case in group])
        verdict = "stop" if abs(model - actual) > MAX_TOTAL_GAMES_BIAS else "proceed"
        lines.append(
            f"  {tour:<6}{len(group):>6}{actual:>9.2f}{model:>9.2f}{model - actual:>+8.2f}"
            f"{p1_actual:>9.2f}{p1_model:>9.2f}{p1_model - p1_actual:>+9.2f}  {verdict}"
        )
    return "\n".join(lines)


async def _main(since: date) -> None:
    from app.db.pool import SessionLocal
    from app.repositories.matches import get_completed_match_scores
    from app.repositories.players import get_rolling_stats_batch_all_surfaces

    async with SessionLocal() as db:
        matches = await get_completed_match_scores(db, since)
        player_ids = sorted({pid for match in matches for pid in (match.p1_id, match.p2_id)})
        stats = await get_rolling_stats_batch_all_surfaces(db, player_ids)
    print(report(*build_cases(matches, stats)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check the first-set chain's level against completed matches")
    parser.add_argument("--since", type=date.fromisoformat, default=date(2026, 1, 1))
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.since))
