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
from datetime import UTC, datetime

from app.core.nfl_projection import NFL_PROJECTION_MODEL_VERSION
from app.core.nfl_targets_projection import NFL_TARGETS_MODEL_VERSION
from app.core.nfl_volume_projection import NFL_VOLUME_MODEL_VERSION
from app.core.nfl_volume_verdict import LogLossResult
from app.core.prop_ranking_check import RankingCheck, slice_results
from app.core.prop_ranking_report import ranking_report
from app.core.prop_ranking_rule import MIN_PERIODS, MIN_PICKS, SliceResult
from app.services.nfl.slate import OVER_PROBABILITY_VERSION
from app.services.nfl.volume_ranking import VolumeRankingRecord


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


def _number(value: float | None) -> str:
    return "-" if value is None else f"{value:.4f}"


def _log_loss_line(label: str, clause: LogLossResult | None) -> str:
    if clause is None or clause.n == 0:
        return f"  {label}: no settled lines yet"
    gap = "-" if clause.raw_difference is None else f"{clause.raw_difference:+.4f} (SE {_number(clause.raw_standard_error)})"
    coin = "-" if clause.half_difference is None else f"{clause.half_difference:+.4f} (SE {_number(clause.half_standard_error)})"
    return (
        f"  {label}: {clause.n} lines, blend {_number(clause.blend)}, raw {_number(clause.raw)}, coin flip {_number(clause.half)}; "
        f"blend minus raw {gap}, minus coin flip {coin}; weeks won {clause.weeks_won} of {clause.weeks} (need {clause.weeks_required})"
    )


def volume_report(volume: VolumeRankingRecord) -> str:
    """The volume record in the shared layout, with verdicts that need both of 49b's clauses."""
    record = volume.record
    states = {(item.odds_type, item.side): item for item in volume.states}
    evaluated = {
        (row.odds_type, row.side): row for row in record.slices if states[(row.odds_type, row.side)].state == "evaluated"
    }
    check = RankingCheck(
        {key: SliceResult(row.verdict, row.n, row.weeks, row.hits, row.break_even) for key, row in evaluated.items()},
        record.funnel,
    )
    coverage = {item.week: (item.lines, item.frozen) for item in record.coverage}
    text = ranking_report(
        "NFL", record.season, check, record.frozen_rows, record.excluded, coverage,
        record.model_version, record.over_probability_version or "not served",
        coverage_label="eligible standard receptions props with a volume-version frozen row",
    )
    lines = [
        text, "",
        "Volume model (receptions only). 49b adds a second clause to 27i's rule: the blend's log loss must beat both"
        " the raw projection and a coin flip, each by 2 SE (clustered by game) and in enough sample weeks.",
        f"A verdict needs {MIN_PICKS} picks over {MIN_PERIODS}+ weeks; until then a slice only shows progress,"
        " and log-loss progress below is not a verdict.",
        "log loss, standard lines of finished weeks:",
        _log_loss_line("all lines so far", volume.log_loss_progress),
    ]
    for key in evaluated:
        lines.append(_log_loss_line(f"{key[0]} {key[1]}, verdict sample", states[key].log_loss))
    not_frozen = ", ".join(f"{odds_type} {side}" for (odds_type, side), item in states.items() if item.state == "not_frozen")
    if not_frozen:
        lines.append(f"Not frozen yet: {not_frozen} (no frozen row for that payout).")
    return "\n".join(lines)


def model_versions(selector: str) -> tuple[str, ...]:
    if selector == "all":
        return NFL_PROJECTION_MODEL_VERSION, NFL_TARGETS_MODEL_VERSION, NFL_VOLUME_MODEL_VERSION
    if selector in (NFL_PROJECTION_MODEL_VERSION, NFL_TARGETS_MODEL_VERSION, NFL_VOLUME_MODEL_VERSION):
        return (selector,)
    raise ValueError(f"Unknown NFL ranking model: {selector}")


async def run(season: int, model_version: str = NFL_PROJECTION_MODEL_VERSION) -> str:
    versions = model_versions(model_version)
    from app.services.nfl.track_record import load_ranking_calls, ranking_source
    from app.services.nfl.volume_ranking import build_volume_record, load_volume_inputs
    from app.db.pool import SessionLocal

    reports: list[str] = []
    async with SessionLocal() as db:
        for version in versions:
            if version == NFL_VOLUME_MODEL_VERSION:
                # Straight to the loaders: the cached getter turns a failure into None, and a failed report must fail the command.
                reports.append(volume_report(build_volume_record(await load_volume_inputs(db, season), season, datetime.now(UTC))))
                continue
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
        "--model-version",
        choices=(NFL_PROJECTION_MODEL_VERSION, NFL_TARGETS_MODEL_VERSION, NFL_VOLUME_MODEL_VERSION, "all"),
        default=NFL_PROJECTION_MODEL_VERSION,
        help="default: v4 only; all prints v4, then Rec Targets, then the volume model, each separately",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print(asyncio.run(run(args.season, args.model_version)))


if __name__ == "__main__":
    main()
