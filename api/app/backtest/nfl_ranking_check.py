"""Forward ranking check: 27i's pre-registered rule on frozen, settled NFL predictions (27j).

Read-only. Grades each provider prop's latest frozen pre-kickoff row at the
line it was frozen on, then reports every payout slice's running sample and,
once the sample is fixed, its one-time verdict. 27h may rank by P(over) only
on a slice that reads `adopt`.

Run from api/: python -m app.backtest.nfl_ranking_check [--season 2026] [--model-version all]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping, Sequence

from app.core.nfl_projection import NFL_PROJECTION_MODEL_VERSION
from app.core.nfl_targets_projection import NFL_TARGETS_MODEL_VERSION
from app.core.prop_ranking_check import RankingCheck, slice_results
from app.core.prop_ranking_report import ranking_report
from app.services.nfl.slate import OVER_PROBABILITY_VERSION


def report(
    season: int, check: RankingCheck, graded: int, exclusions: Mapping[str, int],
    coverage: Mapping[int, tuple[int, int]],
    model_version: str = NFL_PROJECTION_MODEL_VERSION, over_probability_version: str | None = OVER_PROBABILITY_VERSION,
) -> str:
    targets = model_version == NFL_TARGETS_MODEL_VERSION
    text = ranking_report(
        "NFL", season, check, graded, exclusions, coverage, model_version,
        "not served" if targets or over_probability_version is None else over_probability_version,
        coverage_label=(
            "eligible standard Rec Targets props with a targets-version frozen row"
            if targets else "27a full-game lines with a frozen row"
        ),
    )
    if targets:
        text += (
            "\n\nRec Targets reference only: P(over) is unavailable because validation did not pass; "
            "no probability-based picks accrue. Goblin and demon lines are not projected."
        )
    return text


def model_versions(selector: str) -> tuple[str, ...]:
    if selector == "all":
        return NFL_PROJECTION_MODEL_VERSION, NFL_TARGETS_MODEL_VERSION
    if selector in (NFL_PROJECTION_MODEL_VERSION, NFL_TARGETS_MODEL_VERSION):
        return (selector,)
    raise ValueError(f"Unknown NFL ranking model: {selector}")


async def run(season: int, model_version: str = NFL_PROJECTION_MODEL_VERSION) -> str:
    versions = model_versions(model_version)
    from app.services.nfl.track_record import load_ranking_calls, ranking_source
    from app.db.pool import SessionLocal

    reports: list[str] = []
    async with SessionLocal() as db:
        for version in versions:
            source = ranking_source(version)
            inputs = await load_ranking_calls(db, season, version)
            reports.append(report(
                season, slice_results(inputs.calls), inputs.frozen_rows, inputs.exclusions, inputs.coverage,
                source.model_version, source.over_probability_version,
            ))
    return "\n\n".join(reports)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply 27i's ranking rule to frozen, settled NFL predictions")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument(
        "--model-version", choices=(NFL_PROJECTION_MODEL_VERSION, NFL_TARGETS_MODEL_VERSION, "all"),
        default=NFL_PROJECTION_MODEL_VERSION, help="default: v4 only; all prints v4 then Rec Targets separately",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print(asyncio.run(run(args.season, args.model_version)))


if __name__ == "__main__":
    main()
