"""Grade stored tennis predictions against results and the closing market (26a).

Read-only: it changes no model and calls no odds API. Every comparison is made on
the matches where all compared components exist, so no component is flattered by
being scored on an easier subset.

Run from api/: python -m app.backtest.tennis_predictions
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Callable, Optional

from app.core.tennis_grading import calibration_bins, clv_summary, paired_loss_difference, score_component
from app.repositories.predictions import GradedPrediction
from app.services.tennis.ensemble import ENSEMBLE_VERSION

DEFAULT_MODEL_VERSION = f"{ENSEMBLE_VERSION}+lgbm-v6"
CLV_MIN_GAP = 0.03

Component = tuple[str, Callable[[GradedPrediction], Optional[float]]]
MODEL_COMPONENTS: tuple[Component, ...] = (
    ("elo", lambda r: r.elo_prob),
    ("ml", lambda r: r.ml_prob),
    ("ensemble", lambda r: r.ensemble_prob),
)
MARKET_COMPONENTS: tuple[Component, ...] = MODEL_COMPONENTS + (("market", lambda r: r.market_prob),)

# Challenger ML probabilities before 2026-09-25 came from the WTA model, so
# Challenger is never pooled with the tours the models were trained on.
GROUPS: tuple[tuple[str, frozenset[str]], ...] = (
    ("ATP", frozenset({"ATP"})),
    ("WTA", frozenset({"WTA"})),
    ("ATP+WTA", frozenset({"ATP", "WTA"})),
    ("CHALLENGER", frozenset({"CHALLENGER"})),
)


def _common(rows: list[GradedPrediction], components: tuple[Component, ...]) -> list[GradedPrediction]:
    return [r for r in rows if all(get(r) is not None for _, get in components)]


def _score_table(title: str, rows: list[GradedPrediction], components: tuple[Component, ...]) -> list[str]:
    lines = [title, f"  {'group':<11}{'n':>6}  " + "  ".join(f"{name:>17}" for name, _ in components),
             f"  {'':<11}{'':>6}  " + "  ".join(f"{'logloss  brier':>17}" for _ in components)]
    for group, tours in GROUPS:
        subset = _common([r for r in rows if r.tour in tours], components)
        if not subset:
            lines.append(f"  {group:<11}{0:>6}  (no matches with every component)")
            continue
        outcomes = [r.p1_won for r in subset]
        cells = []
        for _, get in components:
            score = score_component([get(r) for r in subset], outcomes)
            cells.append(f"{score.log_loss:>8.4f} {score.brier:>8.4f}")
        lines.append(f"  {group:<11}{len(subset):>6}  " + "  ".join(cells))
    return lines


def _paired_section(rows: list[GradedPrediction]) -> list[str]:
    lines = ["Paired log-loss difference vs market (negative = beats the market; +/- one standard error)"]
    for group, tours in GROUPS:
        subset = _common([r for r in rows if r.tour in tours], MARKET_COMPONENTS)
        if len(subset) < 2:
            lines.append(f"  {group:<11}n={len(subset)} (too few)")
            continue
        outcomes = [r.p1_won for r in subset]
        market = [r.market_prob for r in subset]
        cells = []
        for name, get in MODEL_COMPONENTS:
            diff = paired_loss_difference([get(r) for r in subset], market, outcomes)
            cells.append(f"{name} {diff.mean:+.4f} +/- {diff.standard_error:.4f}")
        lines.append(f"  {group:<11}n={len(subset):<5} " + "   ".join(cells))
    return lines


def _calibration_section(rows: list[GradedPrediction]) -> list[str]:
    lines = ["Calibration (predicted vs actual p1 win rate, matches with every component)"]
    for group, tours in (GROUPS[2], GROUPS[3]):
        subset = _common([r for r in rows if r.tour in tours], MARKET_COMPONENTS)
        if not subset:
            continue
        outcomes = [r.p1_won for r in subset]
        for name, get in (("ensemble", lambda r: r.ensemble_prob), ("market", lambda r: r.market_prob)):
            bins = calibration_bins([get(r) for r in subset], outcomes)
            cells = "  ".join(f"{b.low:.1f}-{b.high:.1f}: {b.mean_predicted:.2f}/{b.actual_rate:.2f} (n={b.n})" for b in bins)
            lines.append(f"  {group:<11}{name:<9} {cells}")
    return lines


def _clv_line(label: str, rows: list[GradedPrediction], min_gap: float) -> str:
    summary = clv_summary([(r.ensemble_prob, r.market_prob, r.closing_market_prob) for r in rows], min_gap)
    rate = f"{summary.toward_rate:.1%}" if summary.toward_rate is not None else "n/a"
    return (f"  {label:<27}eligible {summary.eligible:>4}  moved {summary.moved:>4}  "
            f"toward model {summary.toward:>4} ({rate})  mean move toward {summary.mean_move_toward * 100:+.2f} pts")


def _clv_section(rows: list[GradedPrediction]) -> list[str]:
    lines = ["Closing-line value (did the same book's price move toward the ensemble before the start?)"]
    lines.append(_clv_line("all", rows, 0.0))
    lines.append(_clv_line(f"all, gap >= {CLV_MIN_GAP * 100:.0f} pts", rows, CLV_MIN_GAP))
    for group, tours in GROUPS:
        subset = [r for r in rows if r.tour in tours]
        lines.append(_clv_line(group, subset, 0.0))
        lines.append(_clv_line(f"{group}, gap >= {CLV_MIN_GAP * 100:.0f} pts", subset, CLV_MIN_GAP))
    return lines


def report(rows: list[GradedPrediction], model_version: str = DEFAULT_MODEL_VERSION) -> str:
    versioned = [r for r in rows if r.model_version == model_version]
    graded = [r for r in versioned if r.completed_score]
    with_market = sum(r.market_prob is not None for r in graded)
    with_close = sum(r.closing_market_prob is not None for r in graded)
    sections = [
        [
            f"Tennis prediction grading - {model_version}",
            f"  settled matches with a pre-start prediction: {len(rows)}",
            f"  excluded, other model versions:              {len(rows) - len(versioned)}",
            f"  excluded, retirements and walkovers:         {len(versioned) - len(graded)}",
            f"  graded:                                      {len(graded)}"
            f"  (market price at prediction: {with_market}, same-book close: {with_close})",
        ],
        _score_table("Model components (log loss, Brier; lower is better)", graded, MODEL_COMPONENTS),
        _score_table("Against the market (same matches for every column)", graded, MARKET_COMPONENTS),
        _paired_section(graded),
        _calibration_section(graded),
        _clv_section(graded),
    ]
    return "\n\n".join("\n".join(section) for section in sections)


async def _main() -> None:
    from app.db.pool import SessionLocal
    from app.repositories.predictions import get_graded_predictions

    parser = argparse.ArgumentParser(description="Grade stored tennis predictions against results and the close")
    parser.add_argument("--model-version", default=DEFAULT_MODEL_VERSION)
    args = parser.parse_args()
    async with SessionLocal() as db:
        rows = await get_graded_predictions(db)
    print(report(rows, args.model_version))


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
