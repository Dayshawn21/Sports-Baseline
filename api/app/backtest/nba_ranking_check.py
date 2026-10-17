"""Forward ranking check: 27i's pre-registered rule on frozen, settled NBA predictions (20g4).

Read-only. NFL's 27j check, unchanged, on NBA's frozen pre-tip rows (20g3):
each provider prop's latest frozen row is graded at the line it was frozen on,
and every payout slice reports its running sample and, once fixed, its
one-time verdict. A later NBA adoption item may rank by P(over) only on a
slice that reads `adopt`.

Run from api/: python -m app.backtest.nba_ranking_check [--season 2026]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping
from datetime import UTC, datetime

from app.core import nba_over_probability_fit as fit
from app.core.nba_projection_backtest import NBA_PROJECTION_MODEL_VERSION
from app.core.prop_ranking_check import RankingCheck, slice_results
from app.core.prop_ranking_report import ranking_report


def report(
    season: int, check: RankingCheck, graded: int, exclusions: Mapping[str, int],
    coverage: Mapping[int, tuple[int, int]],
) -> str:
    return ranking_report(
        "NBA", season, check, graded, exclusions, coverage, NBA_PROJECTION_MODEL_VERSION,
        fit.OVER_PROBABILITY_VERSION, coverage_label="modelled full-game lines with a frozen row",
    )


async def _main(season: int | None) -> int:
    from app.db.pool import SessionLocal
    from app.services.nba.track_record import load_ranking_calls, nba_season

    async with SessionLocal() as db:
        if season is None:
            season = await nba_season(db, datetime.now(UTC))
        if season is None:
            print("No NBA regular-season games are loaded, so there is no season to grade.", file=sys.stderr)
            return 1
        inputs = await load_ranking_calls(db, season)
    print(report(season, slice_results(inputs.calls), inputs.frozen_rows, inputs.exclusions, inputs.coverage))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply 27i's ranking rule to frozen, settled NBA predictions")
    parser.add_argument("--season", type=int, default=None, help="start year; default the current NBA season")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.exit(asyncio.run(_main(args.season)))
