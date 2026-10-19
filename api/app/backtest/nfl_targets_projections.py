"""Read-only Rec Targets development replay: python -m app.backtest.nfl_targets_projections --season 2024."""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from time import perf_counter

from app.core.nfl_projection_backtest import (
    MIN_PAIRED_CASES, MIN_RELATIVE_MAE_IMPROVEMENT, STANDARD_ERRORS_REQUIRED, ReplayCase, market_metrics,
)
from app.core.nfl_targets_backtest import (
    DEVELOPMENT_SEASON, REGULAR_SEASON_WEEKS, TargetsBacktest, TargetsCoverage,
    select_baseline, validate_development_season,
)
from app.core.nfl_targets_projection import NFL_TARGETS_MODEL_VERSION, TargetsReplayRow

RULE_TEXT = (
    f"Accept only with >= {MIN_PAIRED_CASES} paired 2024 cases, MAE at least "
    f"{MIN_RELATIVE_MAE_IMPROVEMENT:.1%} lower than the incumbent, and paired mean |error| difference "
    f"below zero by more than {STANDARD_ERRORS_REQUIRED:g} SE (pre-registered 2026-10-18)."
)


def _coverage_counts(row: TargetsCoverage) -> tuple[int, ...]:
    return (row.total, row.missing_actual, row.invalid_actual, row.no_baseline, row.thin_baseline,
            row.scored, row.missing_moneyline, row.unresolved_side, row.missing_history, row.invalid_history)


def _coverage_table(coverage: Sequence[TargetsCoverage]) -> list[str]:
    columns = ("rows", "missA", "badA", "noBase", "thin", "score", "noML", "noSide", "histNull", "histBad")
    lines = [
        "Weekly coverage: rows = missA + badA + noBase + thin + score.",
        "noML/noSide count all driver rows and may overlap; histNull/histBad count pre-week observations per input.",
        f"{'week':<6}" + "".join(f"{column:>9}" for column in columns),
    ]
    counts = [_coverage_counts(row) for row in coverage]
    for row, values in zip(coverage, counts):
        lines.append(f"{row.week:<6}" + "".join(f"{value:>9}" for value in values))
    totals = tuple(sum(column) for column in zip(*counts))
    lines.append(f"{'all':<6}" + "".join(f"{value:>9}" for value in totals))
    return lines


def _metrics_table(arm: str, cases: Sequence[ReplayCase]) -> list[str]:
    lines = [f"Arm {arm}: bias = projection minus actual; share-below excludes ties.",
             f"  {'market / position':<26}{'n':>7}{'MAE':>10}{'RMSE':>10}{'bias':>10}{'below':>9}"]
    if not cases:
        return lines + ["  No eligible cases."]
    groups = [("all", list(cases))] + [
        (position, [case for case in cases if case.position == position])
        for position in sorted({case.position for case in cases})
    ]
    for position, group in groups:
        metrics = market_metrics(group)
        below = f"{metrics.share_below:.1%}" if metrics.share_below is not None else "--"
        lines.append(
            f"  {'receiving_targets / ' + position:<26}{metrics.n:>7}{metrics.mae:>10.3f}"
            f"{metrics.rmse:>10.3f}{metrics.bias:>+10.3f}{below:>9}"
        )
    return lines


def report(result: TargetsBacktest) -> str:
    lines = [
        f"Rec Targets baseline, {DEVELOPMENT_SEASON} (model {NFL_TARGETS_MODEL_VERSION})",
        "Development selection only, not holdout validation. 2025 holdout reads: 0.",
        "Synthetic full-game standard slots, not historical PrizePicks listings.",
        "Moneyline proxy: de-vigged NFLverse pre-kickoff closing prices, not week-start snapshots.",
        "Team side uses as-of rosters; the never-rostered player-team fallback is mutable.",
        RULE_TEXT,
        "Order: reference, moneyline vs reference, recent_form vs the last accepted arm (pooled positions).",
        "B = chosen-season mean; R = last five known pre-week counts (four if only four exist).",
        "factor = 1 + clamp(team_probability - 0.5, -0.08, +0.08); 1 if probability/side unknown.",
        "reference = round(B, 2); moneyline = round(B * factor, 2).",
        "recent_form = round((0.5 * B + 0.5 * R) * accepted_factor, 2).",
        "accepted_factor = factor only if moneyline was accepted; otherwise 1.",
        "", *_coverage_table(result.coverage),
    ]
    for arm, cases in result.cases_by_arm.items():
        lines += ["", *_metrics_table(arm, cases)]
    lines += ["", "Sequential comparisons (MAE change is relative to the named incumbent):",
              f"  {'candidate vs incumbent':<34}{'n':>7}{'inc MAE':>10}{'arm MAE':>10}"
              f"{'change':>10}{'diff':>10}{'SE':>10}  verdict"]
    for comparison in result.comparisons:
        label = f"{comparison.arm} vs {comparison.incumbent}"
        diff = comparison.diff
        if diff is None:
            lines.append(f"  {label:<34}{0:>7}  -- no paired cases --  {comparison.verdict}")
        else:
            lines.append(
                f"  {label:<34}{diff.n:>7}{diff.production_mae:>10.3f}{diff.variant_mae:>10.3f}"
                f"{diff.relative_mae_change:>+10.2%}{diff.mean_diff:>+10.3f}{diff.standard_error:>10.3f}"
                f"  {comparison.verdict}"
            )
    if result.selected_arm is None:
        lines += ["", "NO SELECTION: no eligible cases; a usable model has not been established."]
    else:
        lines += ["", f"Selected development arm: {result.selected_arm}",
                  f"SELECTED_MONEYLINE_SCALING = {result.moneyline_scaled}",
                  f"SELECTED_RECENT_FORM = {result.recent_form}",
                  "Selection is reported only; no settings or production predictions were written."]
    return "\n".join(lines)


async def run_replay(season: int) -> TargetsBacktest:
    validate_development_season(season)
    from app.db.pool import SessionLocal
    from app.repositories.nfl_targets import get_targets_replay_rows

    rows: list[TargetsReplayRow] = []
    async with SessionLocal() as db:
        for week in REGULAR_SEASON_WEEKS:
            rows.extend(await get_targets_replay_rows(db, season, week))
    return select_baseline(rows)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select the Rec Targets development baseline on 2024 only")
    parser.add_argument("--season", type=int, choices=(DEVELOPMENT_SEASON,), default=DEVELOPMENT_SEASON)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    started = perf_counter()
    print(report(asyncio.run(run_replay(args.season))))
    print(f"Elapsed seconds: {perf_counter() - started:.2f}")


if __name__ == "__main__":
    main()
