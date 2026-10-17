"""Forward ranking check: 27i's pre-registered rule on frozen, settled NFL predictions (27j).

Read-only. Grades each provider prop's latest frozen pre-kickoff row at the
line it was frozen on, then reports every payout slice's running sample and,
once the sample is fixed, its one-time verdict. 27h may rank by P(over) only
on a slice that reads `adopt`.

Run from api/: python -m app.backtest.nfl_ranking_check [--season 2026]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping

from app.core.nfl_projection import NFL_PROJECTION_MODEL_VERSION
from app.core.prop_ranking_check import RankingCheck, slice_results
from app.core.prop_ranking_report import ranking_report
from app.services.nfl.slate import OVER_PROBABILITY_VERSION


def report(
    season: int, check: RankingCheck, graded: int, exclusions: Mapping[str, int],
    coverage: Mapping[int, tuple[int, int]],
    model_version: str = NFL_PROJECTION_MODEL_VERSION, over_probability_version: str = OVER_PROBABILITY_VERSION,
) -> str:
    return ranking_report(
        "NFL", season, check, graded, exclusions, coverage, model_version, over_probability_version,
        coverage_label="27a full-game lines with a frozen row",
    )


async def _main(season: int) -> None:
    from app.db.pool import SessionLocal
    from app.services.nfl.track_record import load_ranking_calls

    async with SessionLocal() as db:
        inputs = await load_ranking_calls(db, season)
    print(report(season, slice_results(inputs.calls), inputs.frozen_rows, inputs.exclusions, inputs.coverage))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply 27i's ranking rule to frozen, settled NFL predictions")
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.season))
