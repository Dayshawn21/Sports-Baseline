"""Fit NBA P(over) on the development season and score it on the holdout (item 20g1).

    python -m app.backtest.nba_over_probability_fit [--write]

Replays 20f's reference arm, fits each market's actual / projection distribution on
2024-25, and scores it on 2025-26 at synthetic x.5 lines under the pre-registered
display rule. `--write` freezes the shown markets' 2024-25 tables, exactly as scored.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Iterable, Mapping, Sequence
from math import floor
from pathlib import Path

from app.core.nba_over_probability import (
    MAX_BIN_GAP,
    MAX_ECE,
    MIN_BIN_PAIRS,
    MIN_CASES,
    NBA_OVER_PROBABILITY_VERSION,
    NbaDisplayVerdict,
    ScoredLine,
    nba_display_verdict,
)
from app.core.nba_projection_backtest import (
    BACKTEST_MARKETS,
    DEVELOPMENT_SEASON,
    HOLDOUT_SEASON,
    NBA_PROJECTION_MODEL_VERSION,
)
from app.core.nfl_over_probability_calibration import CalibrationPair, CalibrationReport, calibrate

RULE_TEXT = (
    f"Show a market only with >= {MIN_CASES} cases, ECE <= {MAX_ECE}, no bin of {MIN_BIN_PAIRS}+ pairs off by "
    f"more than {MAX_BIN_GAP}, and Brier no worse than a normal on the same pairs (pre-registered 2026-10-06)."
)

MINUTES_BUCKETS: tuple[tuple[str, float, float], ...] = (("20-28 min", 20.0, 28.0), ("28+ min", 28.0, float("inf")))

_MARKET_ORDER = [market.value for market in BACKTEST_MARKETS]

FIT_MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "nba_over_probability_fit.py"


def _calibrate(lines: Sequence[ScoredLine]) -> CalibrationReport:
    return calibrate(CalibrationPair(line.p_over, line.over) for line in lines)


def _normal_brier(lines: Sequence[ScoredLine]) -> float:
    return sum((line.normal_p_over - line.over) ** 2 for line in lines) / len(lines)


def _case_count(lines: Iterable[ScoredLine]) -> int:
    return len({line.case.key for line in lines})


def _by_market(scored: Sequence[ScoredLine]) -> dict[str, list[ScoredLine]]:
    grouped: dict[str, list[ScoredLine]] = {}
    for market in _MARKET_ORDER:
        lines = [line for line in scored if line.case.market == market]
        if lines:
            grouped[market] = lines
    return grouped


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


def verdicts(scored: Sequence[ScoredLine]) -> dict[str, NbaDisplayVerdict]:
    return {
        market: nba_display_verdict(_case_count(lines), _calibrate(lines), _normal_brier(lines))
        for market, lines in _by_market(scored).items()
    }


def _at_projection(line: ScoredLine) -> bool:
    """The 1.0-multiple synthetic line, the x.5 just above the projection's floor."""
    return line.line == floor(line.case.projection) + 0.5


def _verdict_table(scored: Sequence[ScoredLine], by_verdict: Mapping[str, NbaDisplayVerdict]) -> list[str]:
    lines = [f"  {'market':<26}{'cases':>7}{'pairs':>8}{'ECE':>8}{'worst':>8}{'Brier':>8}{'normal':>8}  verdict   failed on"]
    for market, group in _by_market(scored).items():
        report = _calibrate(group)
        normal = _normal_brier(group)
        worst = _worst_gap(report)
        worst_text = f"{worst:>8.3f}" if worst is not None else f"{'--':>8}"
        cases_n = _case_count(group)
        lines.append(
            f"  {market:<26}{cases_n:>7}{report.n:>8}{report.ece:>8.3f}{worst_text}{report.brier:>8.4f}"
            f"{normal:>8.4f}  {by_verdict[market]:<9} {_failed(cases_n, report, normal)}"
        )
    return lines


def _nearest_line_table(scored: Sequence[ScoredLine]) -> list[str]:
    lines = [
        "At the line nearest the projection (1.0 multiple): the median gap as a probability",
        f"  {'market':<26}{'n':>7}{'predicted':>11}{'observed':>10}{'normal':>8}",
    ]
    for market, group in _by_market(scored).items():
        at = [line for line in group if _at_projection(line)]
        if at:
            lines.append(
                f"  {market:<26}{len(at):>7}{sum(a.p_over for a in at) / len(at):>11.3f}"
                f"{sum(a.over for a in at) / len(at):>10.3f}{sum(a.normal_p_over for a in at) / len(at):>8.3f}"
            )
    return lines


def _minutes_table(scored: Sequence[ScoredLine]) -> list[str]:
    lines = ["ECE by prior minutes (information only; the verdict pools them)",
             f"  {'market / prior minutes':<36}{'pairs':>8}{'ECE':>8}"]
    for market, group in _by_market(scored).items():
        for label, low, high in MINUTES_BUCKETS:
            bucket = [line for line in group if low <= line.case.prior_minutes < high]
            if bucket:
                lines.append(f"  {market + ' / ' + label:<36}{len(bucket):>8}{_calibrate(bucket).ece:>8.3f}")
    return lines


def _reliability(scored: Sequence[ScoredLine]) -> list[str]:
    lines: list[str] = []
    for market, group in _by_market(scored).items():
        lines += ["", f"Reliability, {market}", f"  {'bin n':>8}{'predicted':>11}{'observed':>10}"]
        lines += [f"  {b.n:>8}{b.mean_predicted:>11.3f}{b.observed:>10.3f}" for b in _calibrate(group).bins]
    return lines


def report(scored: Sequence[ScoredLine]) -> str:
    by_verdict = verdicts(scored)
    lines = [
        f"NBA over probability fit: fitted on {DEVELOPMENT_SEASON}-{(DEVELOPMENT_SEASON + 1) % 100:02d}, "
        f"scored on the {HOLDOUT_SEASON}-{(HOLDOUT_SEASON + 1) % 100:02d} holdout",
        f"Projection {NBA_PROJECTION_MODEL_VERSION}, P(over) {NBA_OVER_PROBABILITY_VERSION}; "
        "holdout read 2 (no projection verdict)",
        "", RULE_TEXT, "", *_verdict_table(scored, by_verdict),
        "", *_nearest_line_table(scored),
        "", *_minutes_table(scored),
        *_reliability(scored),
    ]
    return "\n".join(lines)


def render_module(shown: Iterable[str], tables: Mapping[str, Sequence[float]]) -> str:
    lines = [
        '"""Generated by `python -m app.backtest.nba_over_probability_fit --write`. Do not edit.',
        "",
        f"Ratio quantiles of actual / projection per market, fitted on the {DEVELOPMENT_SEASON} replay of",
        f"projection model {NBA_PROJECTION_MODEL_VERSION} and scored once on the {HOLDOUT_SEASON} holdout",
        "(item 20g1). Only markets that passed the pre-registered display rule are included.",
        '"""',
        "from __future__ import annotations",
        "",
        f"FIT_SEASON = {DEVELOPMENT_SEASON}",
        f"SCORED_SEASON = {HOLDOUT_SEASON}",
        f'FIT_PROJECTION_MODEL_VERSION = "{NBA_PROJECTION_MODEL_VERSION}"',
        f'OVER_PROBABILITY_VERSION = "{NBA_OVER_PROBABILITY_VERSION}"',
        f"SHOWN_MARKETS: frozenset[str] = frozenset({{{', '.join(repr(m) for m in sorted(shown))}}})",
        "QUANTILES_BY_MARKET: dict[str, tuple[float, ...]] = {",
    ]
    for market, quantiles in sorted(tables.items()):
        lines.append(f"    {market!r}: (")
        values = [f"{q:.4f}" for q in quantiles]
        lines += ["        " + ", ".join(values[i:i + 8]) + "," for i in range(0, len(values), 8)]
        lines.append("    ),")
    lines.append("}")
    return "\n".join(lines) + "\n"


async def _main(write: bool) -> None:
    from app.core.nba_over_probability import fit_markets, score_cases
    from app.core.nba_projection_backtest import ARMS, REFERENCE_ARM, replay_cases
    from app.db.pool import SessionLocal
    from app.repositories.nba import get_projection_history

    async with SessionLocal() as db:
        history = await get_projection_history(db, (DEVELOPMENT_SEASON - 1, DEVELOPMENT_SEASON, HOLDOUT_SEASON))
    arm = ARMS[REFERENCE_ARM]
    fits = fit_markets(replay_cases(history, DEVELOPMENT_SEASON, arm))
    scored = score_cases(fits, replay_cases(history, HOLDOUT_SEASON, arm))
    print(report(scored))
    if write:
        shown = [market for market, verdict in verdicts(scored).items() if verdict == "show"]
        tables = {market: fits[market].quantiles for market in shown}
        FIT_MODULE_PATH.write_text(render_module(shown, tables), encoding="utf-8")
        print(f"\nWrote {FIT_MODULE_PATH} with {len(shown)} shown market(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fit NBA P(over) on 2024-25 and score it on the 2025-26 holdout")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.write))
