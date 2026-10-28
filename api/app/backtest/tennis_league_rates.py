"""Tour league ace and double-fault rates for the prop matchup factors (48a).

Read-only. The matchup factors divide an opponent's allowed rate by a league
rate, so the league rate should be what a typical same-tour opponent allows.
One constant served both tours, and WTA opponents average more allowed double
faults than it, so nearly every WTA projection was inflated. This reports the
population the props page reads, per player tour, so the constants can be
frozen from it. It reads no prop line or outcome.

Run from api/: python -m app.backtest.tennis_league_rates [--min-matches 5]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass

from app.repositories.players import LeagueRateRow

RATE_FIELDS = ("allowed_aces_per_sp", "allowed_df_per_sp", "aces_per_sp", "df_per_sp")


@dataclass(frozen=True)
class RateSummary:
    field: str
    n: int
    mean: float | None
    weighted_mean: float | None
    """Weighted by matches played, so busy players count more."""


def summarize(rows: list[LeagueRateRow], min_matches: int) -> dict[str, list[RateSummary]]:
    by_tour: dict[str, list[LeagueRateRow]] = {}
    for row in rows:
        if row.matches >= min_matches:
            by_tour.setdefault(row.tour, []).append(row)
    result: dict[str, list[RateSummary]] = {}
    for tour, group in sorted(by_tour.items()):
        summaries = []
        for field in RATE_FIELDS:
            pairs = [(getattr(row, field), row.matches) for row in group if getattr(row, field) is not None]
            weight = sum(matches for _, matches in pairs)
            summaries.append(RateSummary(
                field,
                len(pairs),
                sum(value for value, _ in pairs) / len(pairs) if pairs else None,
                sum(value * matches for value, matches in pairs) / weight if weight else None,
            ))
        result[tour] = summaries
    return result


def _fmt(value: float | None) -> str:
    return f"{value:9.4f}" if value is not None else f"{'n/a':>9}"


def report(summary: dict[str, list[RateSummary]], min_matches: int) -> str:
    lines = [
        "Tour league rates per serve point (last_52w, all surfaces, overall split)",
        f"  players with at least {min_matches} matches",
        f"  {'tour':<12}{'field':<22}{'n':>6}{'mean':>9}{'weighted':>9}",
    ]
    for tour, summaries in summary.items():
        for s in summaries:
            lines.append(f"  {tour:<12}{s.field:<22}{s.n:>6}{_fmt(s.mean)}{_fmt(s.weighted_mean)}")
    return "\n".join(lines)


async def _main(min_matches: int) -> None:
    from app.db.pool import SessionLocal
    from app.repositories.players import get_league_rate_rows

    async with SessionLocal() as db:
        rows = await get_league_rate_rows(db)
    print(report(summarize(rows, min_matches), min_matches))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Report tour league ace and double-fault rates")
    parser.add_argument("--min-matches", type=int, default=5)
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.min_matches))
