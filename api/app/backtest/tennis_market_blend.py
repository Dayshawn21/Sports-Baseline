"""Score the frozen market-anchored tennis blend (26d) under its pre-registered rule.

H1 (beats the hand-set blend) and H2 (no worse than the close) are scored on the
26c holdout, once. L1 (no worse than the market on the app's own inputs) is scored
on 26a's settled live predictions with --live. The default run scores the 2022
development season, which the coefficients were fitted on, so it is in-sample.

Data: Valuebetennis open data (https://www.valuebetennis.com), CC BY 4.0.

Run from api/: python -m app.backtest.tennis_market_blend [--holdout | --live]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Literal

from app.backtest.tennis_closing_lines import (
    CHALLENGER_CATEGORIES, DATA_DIR, DEVELOPMENT_SEASONS, HOLDOUT_SEASONS, ROI_MIN_EDGE, ClosingLineCase,
    build_cases, flat_stake, load_valuebetennis,
)
from app.backtest.tennis_market_blend_fit import in_group, served_prob
from app.core.tennis_grading import PairedDifference, calibration_bins, paired_loss_difference, score_component
from app.core.tennis_market_blend import BlendCoefficients, market_anchored_prob
from app.core.tennis_market_blend_fit import FIT_COEFFICIENTS, FIT_SEASONS
from app.repositories.predictions import GradedPrediction
from app.services.tennis.ensemble import elo_is_unreliable

# Pre-registered in the 26d spec (approved 2026-10-01, before the fit was run). Do not
# edit after the holdout run: a changed rule invalidates the verdict.
GATE_STANDARD_ERRORS = 2.0
VERDICT_GROUPS = ("ATP+WTA", "CHALLENGER")
REPORT_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ATP", ("ATP",)),
    ("WTA", ("WTA",)),
    ("ATP+WTA", ("ATP", "WTA")),
    ("CHALLENGER", ("CHALLENGER",)),
)

Gate = Literal["pass", "fail"]
CoefficientTable = Mapping[str, BlendCoefficients]


def verdict_h1(difference: PairedDifference) -> Gate:
    """Fitted minus the hand-set blend: passes only when better by more than 2 SE."""
    return "pass" if difference.mean + GATE_STANDARD_ERRORS * (difference.standard_error or 0.0) < 0 else "fail"


def verdict_h2(difference: PairedDifference) -> Gate:
    """Fitted minus the close: fails only when worse by more than 2 SE."""
    return "pass" if difference.mean - GATE_STANDARD_ERRORS * (difference.standard_error or 0.0) <= 0 else "fail"


def verdict_l1(difference: PairedDifference) -> Gate:
    """Fitted minus the live market at prediction: fails only when worse by more than 2 SE."""
    return verdict_h2(difference)


def coefficients_for(case: ClosingLineCase, table: CoefficientTable = FIT_COEFFICIENTS) -> BlendCoefficients:
    return table["CHALLENGER" if case.category in CHALLENGER_CATEGORIES else case.tour]


def fitted_prob(case: ClosingLineCase, table: CoefficientTable = FIT_COEFFICIENTS) -> float | None:
    return served_prob(case, coefficients_for(case, table))


def group_cases(cases: list[ClosingLineCase], seasons: frozenset[int], fit_groups: tuple[str, ...]) -> list[ClosingLineCase]:
    """26c's eligible cases in the seasons, with every compared probability present."""
    return [
        c for c in cases
        if c.season in seasons and any(in_group(c, g) for g in fit_groups)
        and c.market_prob is not None and c.blend_prob is not None
    ]


def differences(cases: list[ClosingLineCase], table: CoefficientTable) -> tuple[PairedDifference, PairedDifference]:
    """(fitted minus the hand-set blend, fitted minus the close): H1's and H2's inputs."""
    fitted = [fitted_prob(c, table) for c in cases]
    outcomes = [c.p1_won for c in cases]
    return (
        paired_loss_difference(fitted, [c.blend_prob for c in cases], outcomes),  # type: ignore[arg-type,misc]
        paired_loss_difference(fitted, [c.market_prob for c in cases], outcomes),  # type: ignore[arg-type,misc]
    )


def _pm(d: PairedDifference) -> str:
    return f"{d.mean:+.4f} +/- {d.standard_error or 0.0:.4f}"


def _score_lines(grouped: list[tuple[str, list[ClosingLineCase]]], table: CoefficientTable) -> list[str]:
    lines = ["Log loss and Brier (lower is better; same matches in every column)",
             f"  {'group':<11}{'n':>7}  {'fitted':>17}  {'hand-set blend':>17}  {'close':>17}"]
    for name, subset in grouped:
        if not subset:
            lines.append(f"  {name:<11}{0:>7}  (no eligible matches)")
            continue
        outcomes = [c.p1_won for c in subset]
        columns = ([fitted_prob(c, table) for c in subset], [c.blend_prob for c in subset],
                   [c.market_prob for c in subset])
        cells = [score_component(list(col), outcomes) for col in columns]  # type: ignore[arg-type]
        lines.append(f"  {name:<11}{len(subset):>7}  " + "  ".join(f"{s.log_loss:>8.4f} {s.brier:>8.4f}" for s in cells))
    return lines


def _difference_lines(grouped: list[tuple[str, list[ClosingLineCase]]], table: CoefficientTable) -> list[str]:
    lines = ["Paired log-loss difference (negative = the fitted blend is better; +/- one standard error)"]
    for name, subset in grouped:
        if len(subset) < 2:
            lines.append(f"  {name:<11}n={len(subset)} (too few)")
            continue
        vs_blend, vs_close = differences(subset, table)
        lines.append(f"  {name:<11}n={len(subset):<6} vs hand-set blend {_pm(vs_blend)}   vs close {_pm(vs_close)}")
    return lines


def _calibration_lines(cases: list[ClosingLineCase], table: CoefficientTable) -> list[str]:
    lines = ["Calibration, ATP+WTA (bin: mean predicted / actual p1 win rate)"]
    outcomes = [c.p1_won for c in cases]
    for name, values in (("fitted", [fitted_prob(c, table) for c in cases]), ("close", [c.market_prob for c in cases])):
        bins = calibration_bins(values, outcomes)  # type: ignore[arg-type]
        lines.append(f"  {name:<8}" + "  ".join(
            f"{b.low:.1f}-{b.high:.1f}: {b.mean_predicted:.2f}/{b.actual_rate:.2f} (n={b.n})" for b in bins))
    return lines


def _roi_lines(grouped: list[tuple[str, list[ClosingLineCase]]], table: CoefficientTable) -> list[str]:
    lines = [f"Flat-stake ROI at the close (fitted - close >= {ROI_MIN_EDGE * 100:.0f} pts, either side; never decisive)"]
    for name, subset in grouped:
        results = [r for r in (flat_stake(replace(c, blend_prob=fitted_prob(c, table))) for c in subset) if r is not None]
        if not results:
            lines.append(f"  {name:<11}picks 0")
            continue
        profit = sum(results)
        lines.append(f"  {name:<11}picks {len(results):>5}  won {sum(r > 0 for r in results):>5}  "
                     f"units {profit:+9.2f}  ROI {profit / len(results):+.1%}")
    return lines


def _verdict_lines(grouped: dict[str, list[ClosingLineCase]], table: CoefficientTable) -> list[str]:
    lines = [f"Holdout gates (pre-registered at {GATE_STANDARD_ERRORS:.0f} standard errors; L1 comes from --live)"]
    for name in VERDICT_GROUPS:
        vs_blend, vs_close = differences(grouped[name], table)
        lines.append(f"  {name:<11}H1 vs hand-set blend {_pm(vs_blend)} -> {verdict_h1(vs_blend)}"
                     f"   H2 vs close {_pm(vs_close)} -> {verdict_h2(vs_close)}")
    return lines


def _coefficient_lines(table: CoefficientTable) -> list[str]:
    return ["Frozen coefficients (logit(p) = a * logit(close) + b * logit(elo))"] + [
        f"  {name:<11}a {c.market:.4f}   b {c.elo:+.4f}" for name, c in sorted(table.items())
    ]


def report(cases: list[ClosingLineCase], holdout: bool, table: CoefficientTable = FIT_COEFFICIENTS) -> str:
    seasons = HOLDOUT_SEASONS if holdout else DEVELOPMENT_SEASONS
    grouped = {name: group_cases(cases, seasons, fit_groups) for name, fit_groups in REPORT_GROUPS}
    ordered = list(grouped.items())
    header = [
        f"Tennis market-anchored blend (26d) - {'HOLDOUT' if holdout else 'development'} seasons "
        + ", ".join(str(s) for s in sorted(seasons)),
        "  Data: Valuebetennis open data (valuebetennis.com), CC BY 4.0. Pinnacle closing odds.",
        f"  Coefficients fitted on {list(FIT_SEASONS)}; gated or missing ELO is served as the close.",
        "  HOLDOUT: scored once, the second read of 2023-2025 (26c was the first)." if holdout else
        "  IN-SAMPLE: these are the fit seasons. Holdout seasons are neither scored nor shown.",
    ]
    sections = [
        header,
        _coefficient_lines(table),
        _score_lines(ordered, table),
        _difference_lines(ordered, table),
        _calibration_lines(grouped["ATP+WTA"], table),
        _roi_lines(ordered, table),
    ]
    if holdout:
        sections.append(_verdict_lines(grouped, table))
    return "\n\n".join("\n".join(section) for section in sections)


# The live predictor's ATP and WTA blends share one verdict; Challenger and WTA 125
# matches are stored as CHALLENGER.
LIVE_VERDICT_GROUP = {"ATP": "ATP+WTA", "WTA": "ATP+WTA", "CHALLENGER": "CHALLENGER"}
LIVE_MODEL_PREFIX = "ensemble-v"


def live_rows(rows: Iterable[GradedPrediction]) -> list[GradedPrediction]:
    """26a's graded rows L1 can score: any ensemble version, the latest pre-start row per match."""
    latest: dict[int, GradedPrediction] = {}
    for r in rows:
        if not (r.model_version.startswith(LIVE_MODEL_PREFIX) and r.completed_score and r.tour in LIVE_VERDICT_GROUP
                and r.elo_prob is not None and r.market_prob is not None and r.generated_at < r.start_utc):
            continue
        if r.match_id not in latest or r.generated_at > latest[r.match_id].generated_at:
            latest[r.match_id] = r
    return sorted(latest.values(), key=lambda r: (r.start_utc, r.match_id))


def live_fitted_prob(row: GradedPrediction, table: CoefficientTable = FIT_COEFFICIENTS) -> float:
    """The frozen blend on TennisAbstract ELO and the market at prediction.

    Graded rows carry no prior-match counts, so only the gate's 15-point gap check applies.
    """
    elo = None if elo_is_unreliable(row.elo_prob, row.market_prob, None) else row.elo_prob
    return market_anchored_prob(table[row.tour], row.market_prob, elo)  # type: ignore[arg-type]


def _live_difference(rows: list[GradedPrediction], baseline: list[float], table: CoefficientTable) -> PairedDifference:
    return paired_loss_difference([live_fitted_prob(r, table) for r in rows], baseline, [r.p1_won for r in rows])


def live_report(rows: list[GradedPrediction], table: CoefficientTable = FIT_COEFFICIENTS) -> str:
    scored = live_rows(rows)
    groups = [(name, [r for r in scored if r.tour in tours]) for name, tours in REPORT_GROUPS]
    lines = [
        "Tennis market-anchored blend (26d) - LIVE gate L1 on 26a's settled predictions",
        "  TennisAbstract ELO and the one-book market at prediction time; any ensemble version, latest pre-start row.",
        "  Gate: the 15-point ELO-market gap only (graded rows carry no prior-match counts).",
        "",
        "Fitted minus the market at prediction (negative = fitted better; +/- one standard error)",
    ]
    for name, subset in groups:
        if len(subset) < 2:
            lines.append(f"  {name:<11}n={len(subset)} (too few)")
            continue
        vs_market = _live_difference(subset, [r.market_prob for r in subset], table)  # type: ignore[misc]
        with_ensemble = [r for r in subset if r.ensemble_prob is not None]
        context = ""
        if len(with_ensemble) >= 2:
            vs_stored = _live_difference(with_ensemble, [r.ensemble_prob for r in with_ensemble], table)  # type: ignore[misc]
            context = f"   context: vs stored ensemble {_pm(vs_stored)} (n={len(with_ensemble)})"
        lines.append(f"  {name:<11}n={len(subset):<6} vs market {_pm(vs_market)}{context}")
    lines += ["", f"Live gate (pre-registered at {GATE_STANDARD_ERRORS:.0f} standard errors)"]
    for name in VERDICT_GROUPS:
        subset = dict(groups)[name]
        if len(subset) < 2:
            lines.append(f"  {name:<11}L1 n={len(subset)} (too few) -> fail")
            continue
        vs_market = _live_difference(subset, [r.market_prob for r in subset], table)  # type: ignore[misc]
        lines.append(f"  {name:<11}L1 vs market {_pm(vs_market)} -> {verdict_l1(vs_market)}")
    return "\n".join(lines)


async def _load_live_rows() -> list[GradedPrediction]:
    from app.db.pool import SessionLocal
    from app.repositories.predictions import get_graded_predictions

    async with SessionLocal() as db:
        return await get_graded_predictions(db)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the 26d market-anchored tennis blend")
    parser.add_argument("--holdout", action="store_true", help="score the pre-registered holdout; run once")
    parser.add_argument("--live", action="store_true", help="score L1 on 26a's settled live predictions (read-only)")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    if args.live:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        print(live_report(asyncio.run(_load_live_rows())))
        return
    matches, _ = load_valuebetennis(args.data_dir)
    print(report(build_cases(matches), holdout=args.holdout))


if __name__ == "__main__":
    main()
