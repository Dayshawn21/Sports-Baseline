"""Forward ranking check: 27i's pre-registered rule on frozen, settled NHL predictions (56d).

Read-only. NFL's 27j check, unchanged, on NHL's frozen pre-puck-drop rows
(56c4): each provider prop's latest frozen row is graded at the line it was
frozen on, and every payout slice reports its running sample and, once fixed,
its one-time verdict. A later NHL adoption item may rank by P(over) only on a
slice that reads `adopt`.

Run from api/: python -m app.backtest.nhl_ranking_check [--season 2026]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping
from datetime import UTC, datetime

from app.core import nhl_over_probability_fit as fit
from app.core.nhl_projection_backtest import NHL_PROJECTION_REFERENCE_VERSION
from app.core.prop_ranking_check import RankingCheck, slice_results
from app.core.prop_ranking_report import ranking_report


def report(
    season: int, check: RankingCheck, graded: int, exclusions: Mapping[str, int],
    coverage: Mapping[int, tuple[int, int]],
) -> str:
    return ranking_report(
        "NHL", season, check, graded, exclusions, coverage, NHL_PROJECTION_REFERENCE_VERSION,
        fit.OVER_PROBABILITY_VERSION, coverage_label="full-game lines with a frozen row",
    )


async def _main(season: int | None) -> int:
    from app.db.pool import SessionLocal
    from app.services.nhl.track_record import load_ranking_calls, nhl_season

    async with SessionLocal() as db:
        if season is None:
            season = await nhl_season(db, datetime.now(UTC))
        if season is None:
            print("No NHL regular-season games are loaded, so there is no season to grade.", file=sys.stderr)
            return 1
        inputs = await load_ranking_calls(db, season)
    print(report(season, slice_results(inputs.calls), inputs.frozen_rows, inputs.exclusions, inputs.coverage))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply 27i's ranking rule to frozen, settled NHL predictions")
    parser.add_argument("--season", type=int, default=None, help="start year; default the current NHL season")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.exit(asyncio.run(_main(args.season)))
