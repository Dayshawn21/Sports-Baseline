"""Read-only gap-bucket diagnostic for the pre-registered shrink-v1 rule (66a).

Exploration, not a verdict. It reads only data outside the motivating sample (the
`ensemble-v3` predictions on /tennis/model), all of it already read by earlier
items, and its only use is to let the owner drop a slice before the shadow is
built. It never retunes the rule in app/core/tennis_shrink.py.

Run from api/: python -m app.backtest.tennis_shrink_diagnostic --live | --history [--data-dir DIR]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.backtest.tennis_closing_lines import DATA_DIR, ClosingLineCase, build_cases, load_valuebetennis
from app.backtest.tennis_market_blend import coefficients_for, live_fitted_prob, live_rows
from app.backtest.tennis_market_blend_fit import in_group
from app.core.tennis_grading import PairedDifference, clv_summary, paired_loss_difference, score_component
from app.core.tennis_market_blend import market_anchored_prob
from app.core.tennis_shrink import gap_bucket, is_affected, shrink_toward_market
from app.services.tennis.ensemble import elo_is_unreliable
from app.repositories.predictions import GradedPrediction

V3_PREFIX = "ensemble-v3"
# 2022 is the season v3's coefficients were fitted on, so it is in-sample.
HISTORY_FIRST_SEASON = 2023
# The motivating sample is every match since v3 went live; the same matches can
# appear in Valuebetennis with Pinnacle prices, so they stay out here too.
MOTIVATING_SAMPLE_START = date(2026, 10, 1)
HISTORY_GROUPS = ("ATP", "WTA", "CHALLENGER")
BUCKETS = ("<1", "1-3", "3-5", "5+")
AFFECTED_BUCKETS = ("3-5", "5+")
GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ATP", ("ATP",)),
    ("WTA", ("WTA",)),
    ("ATP+WTA", ("ATP", "WTA")),
    ("CHALLENGER", ("CHALLENGER",)),
)


@dataclass(frozen=True)
class DiagnosticRow:
    """One match: the served-v3 forecast, the market it saw, the close, the result (all for p1)."""
    tour: str
    model: float
    market: float
    close: float | None
    p1_won: bool

    @property
    def gap(self) -> float:
        return self.model - self.market

    @property
    def shadow(self) -> float:
        return shrink_toward_market(self.model, self.market)


def outside_motivating_sample(rows: Iterable[GradedPrediction], v3_match_ids: set[int]) -> list[GradedPrediction]:
    """26d's scorable live rows for matches that never had an ensemble-v3 prediction."""
    return [r for r in live_rows(rows) if r.match_id not in v3_match_ids]


def live_diagnostic_rows(rows: list[GradedPrediction]) -> list[DiagnosticRow]:
    return [
        DiagnosticRow(r.tour, live_fitted_prob(r), r.market_prob, r.closing_market_prob, r.p1_won)  # type: ignore[arg-type]
        for r in rows
    ]


def history_cases(cases: Iterable[ClosingLineCase]) -> list[tuple[str, ClosingLineCase]]:
    """26c's scored sets with an opening price, 2023 onward and before the motivating sample."""
    kept: list[tuple[str, ClosingLineCase]] = []
    for c in cases:
        if c.season < HISTORY_FIRST_SEASON or c.match_date >= MOTIVATING_SAMPLE_START or c.open_prob is None:
            continue
        group = next((g for g in HISTORY_GROUPS if in_group(c, g)), None)
        if group is not None:
            kept.append((group, c))
    return kept


def history_v3_prob(case: ClosingLineCase) -> float:
    """v3 on the Pinnacle open, as the live blend sees a price earlier than the close."""
    elo = None if elo_is_unreliable(case.elo_prob, case.open_prob, None) else case.elo_prob
    return market_anchored_prob(coefficients_for(case), case.open_prob, elo)  # type: ignore[arg-type]


def history_diagnostic_rows(kept: list[tuple[str, ClosingLineCase]]) -> list[DiagnosticRow]:
    return [DiagnosticRow(g, history_v3_prob(c), c.open_prob, c.market_prob, c.p1_won)  # type: ignore[arg-type]
            for g, c in kept]


def _close_lines(kept: list[tuple[str, ClosingLineCase]]) -> list[str]:
    lines = ["Reference: v3 on the open minus the Pinnacle close, 3+ point gaps (negative = v3 better)"]
    for name, tours in GROUPS:
        subset = [c for g, c in kept if g in tours and is_affected(history_v3_prob(c), c.open_prob)]  # type: ignore[arg-type]
        if len(subset) < 2:
            lines.append(f"  {name:<11}n={len(subset)} (too few)")
            continue
        difference = paired_loss_difference([history_v3_prob(c) for c in subset],
                                            [c.market_prob for c in subset], [c.p1_won for c in subset])  # type: ignore[misc]
        lines.append(f"  {name:<11}n={len(subset):<6} {_pm(difference)}")
    return lines


def _pm(d: PairedDifference) -> str:
    return f"{d.mean:+.4f} +/- {d.standard_error or 0.0:.4f}"


def _bucket_line(label: str, rows: list[DiagnosticRow], with_shrink: bool) -> str:
    if len(rows) < 2:
        return f"    {label:<4} n={len(rows):<5} (too few)"
    outcomes = [r.p1_won for r in rows]
    models, markets = [r.model for r in rows], [r.market for r in rows]
    model_ll = score_component(models, outcomes).log_loss
    market_ll = score_component(markets, outcomes).log_loss
    vs_market = paired_loss_difference(models, markets, outcomes)
    shrink = (f"  shrink-v3 {_pm(paired_loss_difference([r.shadow for r in rows], models, outcomes))}"
              if with_shrink else f"  {'':>27}")
    clv = clv_summary((r.model, r.market, r.close) for r in rows)
    toward = f"{clv.toward_rate:.1%}" if clv.toward_rate is not None else "-"
    return (f"    {label:<4} n={len(rows):<5} LL v3 {model_ll:.4f} mkt {market_ll:.4f}  v3-mkt {_pm(vs_market)}"
            f"{shrink}  CLV moved {clv.moved:>4} toward {toward:>6} mean {clv.mean_move_toward * 100:+.2f}")


def bucket_lines(rows: list[DiagnosticRow]) -> list[str]:
    lines = [
        "By gap bucket (|v3 - market| in points). LL = log loss; differences are paired, negative = first is better,",
        "+/- one standard error. shrink-v3 = the frozen rule minus v3 (zero below 3 points, so shown at 3+ only).",
        "CLV: moved prices, share that moved toward v3, mean move toward v3 in points.",
    ]
    for name, tours in GROUPS:
        subset = [r for r in rows if r.tour in tours]
        lines.append(f"  {name} (n={len(subset)})")
        for bucket in BUCKETS:
            in_bucket = [r for r in subset if gap_bucket(r.gap) == bucket]
            lines.append(_bucket_line(bucket, in_bucket, bucket in AFFECTED_BUCKETS))
        affected = [r for r in subset if is_affected(r.model, r.market)]
        lines.append(_bucket_line("3+", affected, True))
    return lines


def live_report(rows: list[GradedPrediction], v3_match_ids: set[int]) -> str:
    scorable = live_rows(rows)
    kept = outside_motivating_sample(rows, v3_match_ids)
    starts = sorted(r.start_utc for r in kept)
    span = f"{starts[0]:%Y-%m-%d} to {starts[-1]:%Y-%m-%d}" if starts else "no matches"
    header = [
        "Tennis shrink-v1 diagnostic (66a) - LIVE rows outside the motivating sample",
        "  EXPLORATION, NOT A VERDICT. These rows were read by 26a and 26d. It can only stop a slice.",
        "  v3 replayed with 26d's live_fitted_prob (15-point ELO gate only); market = the one-book price at prediction.",
        f"  Settled graded matches {len(rows)}; scorable by 26d's live filter {len(scorable)}; "
        f"dropped for any ensemble-v3 prediction {len(scorable) - len(kept)}; kept {len(kept)} ({span}).",
    ]
    return "\n".join(header + [""] + bucket_lines(live_diagnostic_rows(kept)))


def history_report(cases: list[ClosingLineCase]) -> str:
    kept = history_cases(cases)
    seasons = sorted({c.season for _, c in kept})
    header = [
        "Tennis shrink-v1 diagnostic (66a) - Valuebetennis HISTORY, v3 applied to the Pinnacle opening price",
        "  EXPLORATION, NOT A VERDICT. 2023-2025 were read twice (26c, 26d); 2026 was read by 40a. 2022 (fit season)",
        f"  and matches from {MOTIVATING_SAMPLE_START} (the motivating sample's dates) are excluded.",
        "  market = the de-vigged Pinnacle open; CLV = open to close; ELO dropped at a 15-point gap to the open.",
        "  Data: Valuebetennis open data (valuebetennis.com), CC BY 4.0.",
        f"  Cases {len(cases)}; kept {len(kept)} (seasons {', '.join(str(s) for s in seasons) or 'none'}).",
    ]
    rows = history_diagnostic_rows(kept)
    return "\n".join(header + [""] + bucket_lines(rows) + [""] + _close_lines(kept))


async def _load_live() -> tuple[list[GradedPrediction], set[int]]:
    from app.db.pool import SessionLocal
    from app.repositories.predictions import get_graded_predictions, get_match_ids_with_model_prefix

    async with SessionLocal() as db:
        return await get_graded_predictions(db), await get_match_ids_with_model_prefix(db, V3_PREFIX)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gap-bucket diagnostic for the shrink-v1 rule (read-only)")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--live", action="store_true", help="live rows with no ensemble-v3 prediction")
    source.add_argument("--history", action="store_true", help="Valuebetennis 2023 onward, v3 on the open")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    if args.history:
        matches, _ = load_valuebetennis(args.data_dir)
        print(history_report(build_cases(matches)))
        return
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    rows, v3_ids = asyncio.run(_load_live())
    print(live_report(rows, v3_ids))


if __name__ == "__main__":
    main()
