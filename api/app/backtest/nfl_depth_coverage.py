"""Compare seasons' depth-chart and Out-report coverage before a usage-shift replay (70b1).

Counts only: it reads the stored chart and injury rows and prints how many
team-weeks name a starter, how many Out players have a chart row, and how many
Out starters have a charted backup. No projection or result is read, so it
spends no holdout.

Run from api/: python -m app.backtest.nfl_depth_coverage [--seasons 2024,2025]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping

from app.core.nfl_depth_coverage import POSITIONS, DepthCoverage, depth_coverage


def _share(count: int, total: int) -> str:
    return f"{count} ({count / total:.0%})" if total else str(count)


def report(coverage_by_season: Mapping[int, DepthCoverage]) -> str:
    seasons = list(coverage_by_season)
    rows = [
        ("Team-weeks charted", [str(c.team_weeks) for c in coverage_by_season.values()]),
        *(
            (f"Team-weeks with a {position}1", [_share(c.starter_team_weeks[position], c.team_weeks) for c in coverage_by_season.values()])
            for position in POSITIONS
        ),
        ("Out players (QB/RB/WR/TE)", [str(c.out_players) for c in coverage_by_season.values()]),
        ("  with a chart row that week", [_share(c.out_with_depth, c.out_players) for c in coverage_by_season.values()]),
        ("  Out starters with a charted backup", [str(c.actionable_out_starters) for c in coverage_by_season.values()]),
    ]
    width = max(len(label) for label, _ in rows)
    lines = ["NFL depth and Out coverage (counts only, no results read)", "",
             f"{'':<{width}}  " + "  ".join(f"{season:>12}" for season in seasons)]
    lines += [f"{label:<{width}}  " + "  ".join(f"{value:>12}" for value in values) for label, values in rows]
    return "\n".join(lines)


async def _main(seasons: list[int]) -> None:
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    coverage: dict[int, DepthCoverage] = {}
    async with SessionLocal() as db:
        for season in seasons:
            depth, out = await nfl_repo.get_depth_coverage_rows(db, season)
            coverage[season] = depth_coverage(depth, out)
    print(report(coverage))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare NFL depth-chart and Out-report coverage by season")
    parser.add_argument("--seasons", default="2024,2025", help="comma-separated seasons")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main([int(season) for season in args.seasons.split(",")]))


if __name__ == "__main__":
    main()
