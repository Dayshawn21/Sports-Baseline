"""Fit per-market P(over) distributions on a replayed season, and judge which markets may show it.

Replays the season through the 27b harness's `production` arm, so the cases are
exactly the rated projections it scores. Each case's P(over) comes from a
distribution fitted on the other week parity (odd weeks score even, and the
reverse), so no case is scored by a fit that saw it. Every case is scored at
its synthetic lines against a normal baseline, and each market gets the
pre-registered display verdict.

`--write` freezes full-season tables for the markets that show into
`app/core/nfl_over_probability_fit.py`.

Run from api/: python -m app.backtest.nfl_over_probability_fit [--season 2025] [--write]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import floor
from pathlib import Path
from statistics import stdev

from app.core.nfl_over_probability import ratio_quantiles, over_probability
from app.core.nfl_over_probability_calibration import (
    MAX_BIN_GAP, MAX_ECE, MIN_BIN_PAIRS, MIN_CASES, CalibrationPair, DisplayVerdict, calibrate,
    display_verdict, normal_over_probability, synthetic_lines,
)
from app.core.nfl_projection import NFL_PROJECTION_MODEL_VERSION
from app.core.nfl_projection_backtest import ReplayCase

Group = tuple[str, str]
FIT_MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "nfl_over_probability_fit.py"
RULE_TEXT = (
    f"Show a market only with >= {MIN_CASES} cases, ECE <= {MAX_ECE}, no bin of >= {MIN_BIN_PAIRS} pairs "
    f"off by more than {MAX_BIN_GAP}, and Brier no worse than the normal baseline (pre-registered 2026-09-26)."
)


@dataclass(frozen=True)
class ScoredPair:
    case: ReplayCase
    line: float
    predicted: float
    normal: float

    @property
    def over(self) -> bool:
        return self.case.actual > self.line

    @property
    def at_projection(self) -> bool:
        return self.line == floor(self.case.projection) + 0.5


def _group(case: ReplayCase) -> Group:
    return (case.market, case.position)


def _fits(cases: Iterable[ReplayCase]) -> dict[Group, tuple[tuple[float, ...], float]]:
    """Quantiles and residual standard deviation per group, for groups with at least two cases."""
    by_group: dict[Group, list[ReplayCase]] = {}
    for case in cases:
        by_group.setdefault(_group(case), []).append(case)
    fits = {}
    for group, members in by_group.items():
        positive = [(c.projection, c.actual) for c in members if c.projection > 0]
        if len(positive) >= 2:
            sigma = stdev(c.actual - c.projection for c in members)
            fits[group] = (ratio_quantiles(positive), sigma)
    return fits


def cross_fit(cases: Sequence[ReplayCase]) -> list[ScoredPair]:
    scored = []
    for parity in (0, 1):
        fits = _fits(c for c in cases if c.week % 2 != parity)
        for case in (c for c in cases if c.week % 2 == parity):
            fit = fits.get(_group(case))
            if fit is None or fit[1] <= 0:
                continue
            quantiles, sigma = fit
            for line in synthetic_lines(case.projection):
                probability = over_probability(quantiles, case.projection, line)
                if probability is not None:
                    scored.append(ScoredPair(
                        case, line, probability.p_over, normal_over_probability(case.projection, sigma, line),
                    ))
    return scored


def _brier(pairs: Sequence[ScoredPair], normal: bool) -> float:
    return sum(((p.normal if normal else p.predicted) - p.over) ** 2 for p in pairs) / len(pairs)


def _case_count(pairs: Iterable[ScoredPair]) -> int:
    return len({(p.case.player_id, p.case.game_id, p.case.market) for p in pairs})


def verdicts(scored: Sequence[ScoredPair]) -> dict[str, DisplayVerdict]:
    result = {}
    for market in sorted({p.case.market for p in scored}):
        pairs = [p for p in scored if p.case.market == market]
        report = calibrate(CalibrationPair(p.predicted, p.over) for p in pairs)
        result[market] = display_verdict(_case_count(pairs), report, _brier(pairs, normal=True))
    return result


def _summary_row(label: str, pairs: Sequence[ScoredPair]) -> str:
    report = calibrate(CalibrationPair(p.predicted, p.over) for p in pairs)
    return (
        f"  {label:<28}{report.n:>7}{report.ece:>8.3f}{report.brier:>8.4f}{_brier(pairs, normal=True):>8.4f}"
    )


def _tercile_label(case: ReplayCase, cuts: tuple[float, float]) -> str:
    return "low" if case.projection < cuts[0] else "mid" if case.projection < cuts[1] else "high"


def _market_section(market: str, pairs: Sequence[ScoredPair]) -> list[str]:
    report = calibrate(CalibrationPair(p.predicted, p.over) for p in pairs)
    lines = [f"Reliability, {market}", f"  {'bin n':>8}{'predicted':>11}{'observed':>10}"]
    lines += [f"  {b.n:>8}{b.mean_predicted:>11.3f}{b.observed:>10.3f}" for b in report.bins]
    lines += [f"  {'group':<28}{'pairs':>7}{'ECE':>8}{'Brier':>8}{'normal':>8}"]
    for position in sorted({p.case.position for p in pairs}):
        lines.append(_summary_row(f"position {position}", [p for p in pairs if p.case.position == position]))
    projections = sorted(p.case.projection for p in pairs)
    cuts = (projections[len(projections) // 3], projections[2 * len(projections) // 3])
    for tercile in ("low", "mid", "high"):
        group = [p for p in pairs if _tercile_label(p.case, cuts) == tercile]
        if group:
            lines.append(_summary_row(f"projection {tercile}", group))
    return lines


def report(season: int, scored: Sequence[ScoredPair]) -> str:
    lines = [
        f"NFL over probability fit, {season} (model {NFL_PROJECTION_MODEL_VERSION}), cross-fitted by week parity",
        "", RULE_TEXT, "",
        f"  {'market':<22}{'cases':>7}{'pairs':>7}{'ECE':>8}{'worst':>8}{'Brier':>8}{'normal':>8}  verdict",
    ]
    by_verdict = verdicts(scored)
    markets = sorted(by_verdict)
    for market in markets:
        pairs = [p for p in scored if p.case.market == market]
        r = calibrate(CalibrationPair(p.predicted, p.over) for p in pairs)
        worst = f"{r.worst_gap:>8.3f}" if r.worst_gap is not None else f"{'--':>8}"
        lines.append(
            f"  {market:<22}{_case_count(pairs):>7}{r.n:>7}{r.ece:>8.3f}{worst}{r.brier:>8.4f}"
            f"{_brier(pairs, normal=True):>8.4f}  {by_verdict[market]}"
        )
    lines += ["", "At the line nearest the projection (1.0 multiple): the OVER lean as a probability",
              f"  {'market':<22}{'n':>7}{'predicted':>11}{'observed':>10}{'normal':>8}"]
    for market in markets:
        at = [p for p in scored if p.case.market == market and p.at_projection]
        if at:
            lines.append(
                f"  {market:<22}{len(at):>7}{sum(p.predicted for p in at) / len(at):>11.3f}"
                f"{sum(p.over for p in at) / len(at):>10.3f}{sum(p.normal for p in at) / len(at):>8.3f}"
            )
    for market in markets:
        lines += ["", *_market_section(market, [p for p in scored if p.case.market == market])]
    return "\n".join(lines)


def fit_tables(cases: Iterable[ReplayCase], markets: Iterable[str]) -> dict[Group, tuple[float, ...]]:
    shown = set(markets)
    return {group: fit[0] for group, fit in sorted(_fits(c for c in cases if c.market in shown).items())}


def render_module(
    season: int, model_version: str, shown: Iterable[str], tables: Mapping[Group, Sequence[float]],
) -> str:
    lines = [
        f'"""Generated by `python -m app.backtest.nfl_over_probability_fit --season {season} --write`. Do not edit.',
        "",
        f"Ratio quantiles of actual / projection per (market, position), fitted on the {season}",
        f"regular-season replay of projection model {model_version}. Only markets that passed",
        "the pre-registered display rule are included.",
        '"""',
        "from __future__ import annotations",
        "",
        f"FIT_SEASON = {season}",
        f'FIT_PROJECTION_MODEL_VERSION = "{model_version}"',
        f"SHOWN_MARKETS: frozenset[str] = frozenset({{{', '.join(repr(m) for m in sorted(shown))}}})",
        "QUANTILES_BY_GROUP: dict[tuple[str, str], tuple[float, ...]] = {",
    ]
    for (market, position), quantiles in sorted(tables.items()):
        lines.append(f"    ({market!r}, {position!r}): (")
        values = [f"{q:.4f}" for q in quantiles]
        lines += ["        " + ", ".join(values[i:i + 8]) + "," for i in range(0, len(values), 8)]
        lines.append("    ),")
    lines.append("}")
    return "\n".join(lines) + "\n"


async def _main(season: int, write: bool) -> None:
    from app.backtest.nfl_projections import PRODUCTION_ARM, REGULAR_SEASON_WEEKS, replay_cases
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    cases: list[ReplayCase] = []
    async with SessionLocal() as db:
        for week in REGULAR_SEASON_WEEKS:
            rows = await nfl_repo.get_replay_rows(db, season, week)
            cases += replay_cases(rows, PRODUCTION_ARM, season, week)
    scored = cross_fit(cases)
    print(report(season, scored))
    if write:
        shown = [market for market, verdict in verdicts(scored).items() if verdict == "show"]
        FIT_MODULE_PATH.write_text(
            render_module(season, NFL_PROJECTION_MODEL_VERSION, shown, fit_tables(cases, shown)), encoding="utf-8",
        )
        print(f"\nWrote {FIT_MODULE_PATH} with {len(shown)} shown market(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fit and judge NFL P(over) distributions on a replayed season")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.season, args.write))
