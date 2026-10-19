"""Fit Rec Targets P(over) on 2024 and score it once on the 2025 holdout (item 39b).

    python -m app.backtest.nfl_targets_over_probability_fit [--write]

Replays `nfl-targets-v1`, fits each position's actual / projection distribution on
2024, and scores 2025 at synthetic x.5 lines under the pre-registered display rule.
Seasons are fixed: there is no option to fit or score anything else. `--write`
freezes the verdict and, when shown, the 2024 tables exactly as scored.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping, Sequence
from math import floor
from pathlib import Path
from time import perf_counter

from app.core.nfl_over_probability_calibration import CalibrationPair, CalibrationReport, calibrate
from app.core.nfl_targets_over_probability import (
    MAX_BIN_GAP,
    MAX_ECE,
    MIN_BIN_PAIRS,
    MIN_CASES,
    NFL_TARGETS_OVER_PROBABILITY_VERSION,
    REGULAR_SEASON_WEEKS,
    TARGETS_MARKET,
    TARGETS_POSITIONS,
    ScoredLine,
    TargetsCaseCoverage,
    TargetsCaseSet,
    TargetsDisplayVerdict,
    fit_positions,
    score_cases,
    targets_cases,
    targets_display_verdict,
)
from app.core.nfl_targets_projection import NFL_TARGETS_MODEL_VERSION

FIT_SEASON = 2024
SCORED_SEASON = 2025
HOLDOUT_READ = 8

FIT_MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "nfl_targets_over_probability_fit.py"

RULE_TEXT = (
    f"Show Rec Targets only with >= {MIN_CASES} cases, ECE <= {MAX_ECE}, no bin of {MIN_BIN_PAIRS}+ pairs off by "
    f"more than {MAX_BIN_GAP}, and Brier no worse than a normal on the same pairs, positions pooled "
    "(pre-registered 2026-10-18)."
)


def _calibrate(lines: Sequence[ScoredLine]) -> CalibrationReport:
    return calibrate(CalibrationPair(line.p_over, line.over) for line in lines)


def _normal_brier(lines: Sequence[ScoredLine]) -> float:
    return sum((line.normal_p_over - line.over) ** 2 for line in lines) / len(lines)


def _case_count(lines: Sequence[ScoredLine]) -> int:
    return len({line.case.key for line in lines})


def _worst_gap(report: CalibrationReport) -> float | None:
    gaps = [b.gap for b in report.bins if b.n >= MIN_BIN_PAIRS]
    return max(gaps) if gaps else None


def _failed(cases_n: int, report: CalibrationReport, normal_brier: float) -> str:
    if cases_n < MIN_CASES:
        return "cases"
    worst = _worst_gap(report)
    checks = [
        ("ECE", report.ece > MAX_ECE),
        ("worst gap", worst is not None and worst > MAX_BIN_GAP),
        ("Brier", report.brier > normal_brier),
    ]
    return ", ".join(name for name, failed in checks if failed)


def verdict(scored: Sequence[ScoredLine]) -> TargetsDisplayVerdict:
    """The one pre-registered verdict, on every scored pair with positions pooled."""
    if not scored:
        return "insufficient"
    return targets_display_verdict(_case_count(scored), _calibrate(scored), _normal_brier(scored))


def _row(label: str, group: Sequence[ScoredLine], verdict_text: str) -> str:
    report = _calibrate(group)
    normal = _normal_brier(group)
    worst = _worst_gap(report)
    worst_text = f"{worst:>8.3f}" if worst is not None else f"{'--':>8}"
    cases_n = _case_count(group)
    return (
        f"  {label:<24}{cases_n:>7}{report.n:>8}{report.ece:>8.3f}{worst_text}{report.brier:>8.4f}"
        f"{normal:>8.4f}  {verdict_text:<9} {_failed(cases_n, report, normal) if verdict_text else ''}"
    ).rstrip()


def _header() -> str:
    return f"  {'group':<24}{'cases':>7}{'pairs':>8}{'ECE':>8}{'worst':>8}{'Brier':>8}{'normal':>8}  verdict   failed on"


def _coverage_table(coverage: Sequence[TargetsCaseCoverage]) -> list[str]:
    lines = [
        "Coverage (driver rows, then what was dropped)",
        f"  {'season':<8}{'rows':>7}{'no actual':>11}{'invalid':>9}{'no base':>9}{'thin':>7}{'zero proj':>11}{'cases':>7}",
    ]
    lines += [
        f"  {c.season:<8}{c.total:>7}{c.missing_actual:>11}{c.invalid_actual:>9}{c.no_baseline:>9}"
        f"{c.thin_baseline:>7}{c.zero_projection:>11}{c.cases:>7}"
        for c in coverage
    ]
    return lines


def _tercile_cuts(scored: Sequence[ScoredLine]) -> tuple[float, float]:
    projections = sorted({line.case.key: line.case.projection for line in scored}.values())
    last = len(projections) - 1
    return projections[round(last / 3)], projections[round(2 * last / 3)]


def _information_rows(scored: Sequence[ScoredLine]) -> list[str]:
    lines = ["Information only; the verdict pools positions", _header()]
    for position in TARGETS_POSITIONS:
        group = [line for line in scored if line.case.position == position]
        if group:
            lines.append(_row(position, group, ""))
    low, high = _tercile_cuts(scored)
    terciles = (
        (f"projection <= {low:.2f}", lambda p: p <= low),
        (f"projection {low:.2f}-{high:.2f}", lambda p: low < p <= high),
        (f"projection > {high:.2f}", lambda p: p > high),
    )
    for label, keep in terciles:
        group = [line for line in scored if keep(line.case.projection)]
        if group:
            lines.append(_row(label, group, ""))
    return lines


def _at_projection(line: ScoredLine) -> bool:
    """The 1.0-multiple synthetic line, the x.5 just above the projection's floor."""
    return line.line == floor(line.case.projection) + 0.5


def _nearest_line_table(scored: Sequence[ScoredLine]) -> list[str]:
    lines = [
        "At the line nearest the projection (1.0 multiple): the median gap as a probability",
        f"  {'group':<24}{'n':>7}{'predicted':>11}{'observed':>10}{'normal':>8}",
    ]
    groups = [("all positions", list(scored))] + [
        (position, [line for line in scored if line.case.position == position]) for position in TARGETS_POSITIONS
    ]
    for label, group in groups:
        at = [line for line in group if _at_projection(line)]
        if at:
            lines.append(
                f"  {label:<24}{len(at):>7}{sum(a.p_over for a in at) / len(at):>11.3f}"
                f"{sum(a.over for a in at) / len(at):>10.3f}{sum(a.normal_p_over for a in at) / len(at):>8.3f}"
            )
    return lines


def _reliability(scored: Sequence[ScoredLine]) -> list[str]:
    lines = ["Reliability, all positions", f"  {'bin n':>8}{'predicted':>11}{'observed':>10}"]
    return lines + [f"  {b.n:>8}{b.mean_predicted:>11.3f}{b.observed:>10.3f}" for b in _calibrate(scored).bins]


def report(fit_coverage: TargetsCaseCoverage, scored_coverage: TargetsCaseCoverage, scored: Sequence[ScoredLine]) -> str:
    lines = [
        f"NFL Rec Targets over probability fit: fitted on {FIT_SEASON}, scored on the {SCORED_SEASON} holdout",
        f"Projection {NFL_TARGETS_MODEL_VERSION}, P(over) {NFL_TARGETS_OVER_PROBABILITY_VERSION}; "
        f"{SCORED_SEASON} holdout read {HOLDOUT_READ} (no projection verdict)",
        "", RULE_TEXT, "", *_coverage_table((fit_coverage, scored_coverage)), "",
    ]
    if not scored:
        lines += [f"Verdict: insufficient (no {SCORED_SEASON} pairs scored)"]
        return "\n".join(lines)
    lines += [
        "Verdict (positions pooled)", _header(), _row(TARGETS_MARKET, scored, verdict(scored)),
        "", *_information_rows(scored),
        "", *_nearest_line_table(scored),
        "", *_reliability(scored),
    ]
    return "\n".join(lines)


async def _load(season: int) -> TargetsCaseSet:
    from app.db.pool import SessionLocal
    from app.repositories.nfl_targets import get_targets_replay_rows

    rows = []
    async with SessionLocal() as db:
        for week in REGULAR_SEASON_WEEKS:
            rows.extend(await get_targets_replay_rows(db, season, week))
    return targets_cases(rows, season)


def render_module(shown: bool, tables: Mapping[str, Sequence[float]]) -> str:
    lines = [
        '"""Generated by `python -m app.backtest.nfl_targets_over_probability_fit --write`. Do not edit.',
        "",
        f"Ratio quantiles of actual / projection per position for Rec Targets, fitted on the {FIT_SEASON}",
        f"replay of projection model {NFL_TARGETS_MODEL_VERSION} and scored once on the {SCORED_SEASON} holdout",
        "(item 39b). Tables are included only when the pre-registered display rule passed.",
        '"""',
        "from __future__ import annotations",
        "",
        f"FIT_SEASON = {FIT_SEASON}",
        f"SCORED_SEASON = {SCORED_SEASON}",
        f'FIT_PROJECTION_MODEL_VERSION = "{NFL_TARGETS_MODEL_VERSION}"',
        f'OVER_PROBABILITY_VERSION = "{NFL_TARGETS_OVER_PROBABILITY_VERSION}"',
        f"SHOWN = {shown}",
        "QUANTILES_BY_POSITION: dict[str, tuple[float, ...]] = {",
    ]
    for position, quantiles in sorted(tables.items()):
        lines.append(f"    {position!r}: (")
        values = [f"{q:.4f}" for q in quantiles]
        lines += ["        " + ", ".join(values[i:i + 8]) + "," for i in range(0, len(values), 8)]
        lines.append("    ),")
    lines.append("}")
    return "\n".join(lines) + "\n"


async def run(write: bool) -> str:
    # The fit is built before any 2025 row is loaded, so nothing scored can shape it.
    fit_set = await _load(FIT_SEASON)
    fits = fit_positions(fit_set.cases)
    scored_set = await _load(SCORED_SEASON)
    scored = score_cases(fits, scored_set.cases)
    text = report(fit_set.coverage, scored_set.coverage, scored)
    if write:
        shown = verdict(scored) == "show"
        tables = {position: fit.quantiles for position, fit in fits.items()} if shown else {}
        FIT_MODULE_PATH.write_text(render_module(shown, tables), encoding="utf-8")
        text += f"\n\nWrote {FIT_MODULE_PATH} (SHOWN = {shown})."
    return text


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Fit Rec Targets P(over) on {FIT_SEASON} and score it once on the {SCORED_SEASON} holdout",
    )
    parser.add_argument("--write", action="store_true", help="freeze the verdict and the shown 2024 tables")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    started = perf_counter()
    print(asyncio.run(run(args.write)))
    print(f"Elapsed seconds: {perf_counter() - started:.2f}")


if __name__ == "__main__":
    main()
