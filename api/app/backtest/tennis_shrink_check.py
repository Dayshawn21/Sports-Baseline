"""Forward check `tennis-shrink-check-v1` for the pre-registered shrink-v1 shadow (66a).

Count mode (the default) reads no winner, score or loss: per slice it prints the
start date, coverage, affected counts, days and whether the floors are met.
`--score --slice X` reads results only after those floors are met, locks the
sample on the first whole UTC day reaching both floors and prints the verdict once.
The rule and gate live in app/core/tennis_shrink.py (pre-registered in `5d99a7f0`);
the per-slice pins and the never-resolved drop are amendments A1 and A2 in the spec.

Run from api/: python -m app.backtest.tennis_shrink_check [--as-of YYYY-MM-DD] [--score --slice ATP+WTA]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal, Optional

from app.core.tennis_grading import paired_loss_difference, score_component
from app.core.tennis_shrink import (
    CHECK_VERSION, MIN_AFFECTED, MIN_COVERAGE, MIN_DAYS, SETTLEMENT_LAG_DAYS, SHRINK_VERSION, SLICES,
    gap_bucket, is_affected, slice_for, verdict,
)
from app.repositories.predictions import MatchResult, ShadowCheckRow

PINNED_VERSIONS = {"ATP+WTA": "ensemble-v3+lgbm-v6", "CHALLENGER": "ensemble-v3+lgbm-none"}
NEVER_RESOLVED_DAYS = 14
EXCLUDED_STATUSES = frozenset({"cancelled", "retired"})
SHADOW_SUFFIX = f"+{SHRINK_VERSION}"
ENSEMBLE_PREFIX = "ensemble-"

Resolution = Literal["included", "excluded", "unresolved", "never resolved"]
Resolver = Callable[[ShadowCheckRow], Resolution]


def check_start(first_shadow_at: datetime) -> date:
    """The first full UTC day after the first production shadow row."""
    return first_shadow_at.astimezone(timezone.utc).date() + timedelta(days=1)


def start_day(row: ShadowCheckRow) -> date:
    return row.start_utc.astimezone(timezone.utc).date()


def is_mature(day: date, as_of: date) -> bool:
    """Day D closes at D+1 midnight UTC, then needs three full settlement days."""
    return as_of >= day + timedelta(days=1 + SETTLEMENT_LAG_DAYS)


def _settled_or_stale(row: ShadowCheckRow, as_of: date) -> Resolution:
    return "never resolved" if as_of >= start_day(row) + timedelta(days=NEVER_RESOLVED_DAYS) else "unresolved"


def count_resolver(as_of: date) -> Resolver:
    """Status only: a completed match counts provisionally until score mode reads it."""
    def resolve(row: ShadowCheckRow) -> Resolution:
        if row.status in EXCLUDED_STATUSES:
            return "excluded"
        return "included" if row.status == "completed" else _settled_or_stale(row, as_of)
    return resolve


def score_resolver(as_of: date, results: dict[int, MatchResult]) -> Resolver:
    def resolve(row: ShadowCheckRow) -> Resolution:
        if row.status in EXCLUDED_STATUSES:
            return "excluded"
        result = results.get(row.match_id)
        if row.status != "completed" or result is None or result.p1_won is None:
            return _settled_or_stale(row, as_of)
        return "included" if result.completed_score else "excluded"
    return resolve


@dataclass
class SliceState:
    name: str
    pinned_version: str
    start: date
    eligible: int = 0
    with_shadow: int = 0
    affected: int = 0
    included: list[ShadowCheckRow] = field(default_factory=list)
    excluded: int = 0
    never_resolved: int = 0
    days: int = 0
    interrupted_on: Optional[date] = None
    stopped_on: Optional[date] = None
    stop_reason: str = ""
    locked_on: Optional[date] = None

    @property
    def coverage(self) -> Optional[float]:
        return self.with_shadow / self.eligible if self.eligible else None

    @property
    def coverage_ok(self) -> bool:
        return self.coverage is not None and self.coverage >= MIN_COVERAGE

    @property
    def status(self) -> str:
        if self.eligible and not self.coverage_ok:
            return "blocked: coverage"
        if self.locked_on is not None:
            return "floors met"
        return "accruing (interrupted)" if self.interrupted_on is not None else "accruing"


def _interruption(rows: list[ShadowCheckRow], pinned: str) -> Optional[date]:
    changed = [start_day(r) for r in rows if r.served_version != pinned and r.served_version.startswith(ENSEMBLE_PREFIX)]
    return min(changed) if changed else None


def slice_state(rows: list[ShadowCheckRow], name: str, start: date, as_of: date, resolve: Resolver) -> SliceState:
    """Walk mature UTC start days in order until the floors are met, a day is not
    yet mature, an affected match is unresolved, or the served version changes."""
    pinned = PINNED_VERSIONS[name]
    state = SliceState(name, pinned, start)
    in_slice = [r for r in rows if slice_for(r.tour) == name and start_day(r) >= start]
    state.interrupted_on = _interruption(in_slice, pinned)
    eligible = [r for r in in_slice if r.served_version == pinned and r.ensemble_prob is not None
                and r.market_prob is not None
                and (state.interrupted_on is None or start_day(r) < state.interrupted_on)]
    affected = [r for r in eligible if r.shadow_prob is not None and is_affected(r.ensemble_prob, r.market_prob)]  # type: ignore[arg-type]
    state.affected = len(affected)
    by_day: dict[date, list[ShadowCheckRow]] = {}
    for r in affected:
        by_day.setdefault(start_day(r), []).append(r)
    last_day: Optional[date] = None
    for day in sorted(by_day):
        if not is_mature(day, as_of):
            state.stopped_on, state.stop_reason = day, "not yet mature"
            break
        resolutions = [(r, resolve(r)) for r in by_day[day]]
        if any(res == "unresolved" for _, res in resolutions):
            state.stopped_on, state.stop_reason = day, "unresolved match"
            break
        kept = [r for r, res in resolutions if res == "included"]
        state.excluded += sum(res == "excluded" for _, res in resolutions)
        state.never_resolved += sum(res == "never resolved" for _, res in resolutions)
        state.included += kept
        state.days += bool(kept)
        last_day = day
        if len(state.included) >= MIN_AFFECTED and state.days >= MIN_DAYS:
            state.locked_on = day
            break
    window_end = state.locked_on or last_day
    counted = [r for r in eligible if window_end is None or start_day(r) <= window_end]
    state.eligible = len(counted)
    state.with_shadow = sum(r.shadow_prob is not None for r in counted)
    return state


def score_candidates(rows: list[ShadowCheckRow], name: str, start: date, as_of: date) -> list[int]:
    """Only affected, shadowed matches on mature days: score mode reads no other result."""
    return [
        r.match_id for r in rows
        if slice_for(r.tour) == name and start_day(r) >= start and is_mature(start_day(r), as_of)
        and r.served_version == PINNED_VERSIONS[name] and r.shadow_prob is not None
        and r.ensemble_prob is not None and r.market_prob is not None and is_affected(r.ensemble_prob, r.market_prob)
    ]


def _pct(value: Optional[float]) -> str:
    return f"{value:.1%}" if value is not None else "-"


def count_lines(states: list[SliceState], as_of: date) -> list[str]:
    lines = [
        f"Tennis shrink-v1 forward check ({CHECK_VERSION}) - COUNTS ONLY, as of {as_of}",
        f"  Floors per slice: {MIN_AFFECTED} affected settled matches and {MIN_DAYS} UTC days, "
        f"{SETTLEMENT_LAG_DAYS}-day lag, coverage >= {MIN_COVERAGE:.0%}. Completed status counts provisionally;",
        "  retirements are known only in score mode. No outcome or loss is read here.",
    ]
    for s in states:
        stop = f"; stopped {s.stopped_on} ({s.stop_reason})" if s.stopped_on else ""
        interrupted = f"; served version changed {s.interrupted_on}" if s.interrupted_on else ""
        lines.append(
            f"  {s.name:<11}pin {s.pinned_version}  start {s.start}  coverage {s.with_shadow}/{s.eligible} "
            f"({_pct(s.coverage)})  affected {s.affected}  counted {len(s.included)}  days {s.days}  "
            f"excluded {s.excluded}  never resolved {s.never_resolved}  -> {s.status}{stop}{interrupted}"
        )
    return lines


def score_lines(state: SliceState, results: dict[int, MatchResult]) -> list[str]:
    sample = state.included
    outcomes = [bool(results[r.match_id].p1_won) for r in sample]
    shadows = [r.shadow_prob for r in sample]
    served = [r.ensemble_prob for r in sample]
    markets = [r.market_prob for r in sample]
    difference = paired_loss_difference(shadows, served, outcomes)  # type: ignore[arg-type]
    result = verdict(difference, len(sample), state.days)
    vs_market = paired_loss_difference(shadows, markets, outcomes)  # type: ignore[arg-type]
    lines = [
        f"Tennis shrink-v1 forward check ({CHECK_VERSION}) - {state.name} VERDICT, sample locked on {state.locked_on}",
        f"  n {len(sample)}  days {state.days}  start {state.start}  excluded {state.excluded}  "
        f"never resolved {state.never_resolved}  coverage {_pct(state.coverage)}",
        f"  Shadow minus served (paired log loss): {difference.mean:+.4f} +/- {difference.standard_error or 0.0:.4f}"
        f"  -> {result}",
        "  Context (never changes the verdict):",
        f"    shadow minus market at prediction {vs_market.mean:+.4f} +/- {vs_market.standard_error or 0.0:.4f}",
        f"    Brier served {score_component(served, outcomes).brier:.4f}  "  # type: ignore[arg-type]
        f"shadow {score_component(shadows, outcomes).brier:.4f}",  # type: ignore[arg-type]
    ]
    for bucket in ("3-5", "5+"):
        part = [i for i, r in enumerate(sample) if gap_bucket(r.ensemble_prob - r.market_prob) == bucket]  # type: ignore[operator]
        if len(part) >= 2:
            d = paired_loss_difference([shadows[i] for i in part], [served[i] for i in part],  # type: ignore[misc]
                                       [outcomes[i] for i in part])
            lines.append(f"    bucket {bucket:<4} n {len(part):<5} shadow minus served {d.mean:+.4f} +/- "
                         f"{d.standard_error or 0.0:.4f}")
    return lines


async def _load(score_slice: Optional[str], as_of: date) -> str:
    from app.db.pool import SessionLocal
    from app.repositories.predictions import get_first_shadow_at, get_match_results, get_shadow_check_rows

    async with SessionLocal() as db:
        first = await get_first_shadow_at(db, SHADOW_SUFFIX)
        if first is None:
            return f"{CHECK_VERSION}: no {SHRINK_VERSION} shadow rows yet; nothing is active. Affected 0."
        start = check_start(first)
        since = datetime.combine(start, time.min, tzinfo=timezone.utc)
        rows = await get_shadow_check_rows(db, since, SHADOW_SUFFIX)
        states = [slice_state(rows, name, start, as_of, count_resolver(as_of)) for name in SLICES]
        if score_slice is None:
            return "\n".join(count_lines(states, as_of))
        counted = next(s for s in states if s.name == score_slice)
        if counted.locked_on is None or not counted.coverage_ok:
            return "\n".join(count_lines(states, as_of) + [f"  Refused: {score_slice} has not met its floors and coverage."])
        results = await get_match_results(db, score_candidates(rows, score_slice, start, as_of))
    state = slice_state(rows, score_slice, start, as_of, score_resolver(as_of, results))
    if state.locked_on is None or not state.coverage_ok:
        return "\n".join(count_lines([state], as_of) + ["  Accruing: retirements took the slice below its floors."])
    return "\n".join(score_lines(state, results))


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Forward check {CHECK_VERSION} (read-only)")
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    parser.add_argument("--score", action="store_true", help="read results and print the verdict once floors are met")
    parser.add_argument("--slice", choices=SLICES)
    args = parser.parse_args()
    if args.score != (args.slice is not None):
        parser.error("--score and --slice go together")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print(asyncio.run(_load(args.slice, args.as_of)))


if __name__ == "__main__":
    main()
