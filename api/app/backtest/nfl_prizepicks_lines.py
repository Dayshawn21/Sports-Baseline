"""Grade stored NFL PrizePicks lines, and the model's calls on them, against results.

Every line counted is the last snapshot taken before kickoff; PrizePicks' NFL
payload carries no in-game marker, so kickoff is the only guard. The model is
replayed through the same `build_slate` the `/nfl/slate` endpoint serves, with
pre-week inputs only. It is today's code on past weeks, not a frozen record, so
a model change re-grades history (item 27h needs projections frozen at kickoff).

It reads and prints. Nothing is fitted, stored, or fed back into a projection.

Run from api/: python -m app.backtest.nfl_prizepicks_lines [--season 2026]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.core.nfl_line_grading import (
    HitSummary, LineResult, OverProbabilityRead, RateSummary, model_hits, over_probability_reads, rate,
    reference_lines,
)
from app.core.nfl_projection import NFL_PROJECTION_MODEL_VERSION
from app.nfl.markets import STANDARD_ODDS_TYPE

# A 2-pick Power pays 3x and a 3-pick 5x, so each pick must hit (1/3)^(1/2) and
# (1/5)^(1/3) of the time to break even.
POWER_2_PICK_BREAK_EVEN = (1 / 3) ** (1 / 2)
POWER_3_PICK_BREAK_EVEN = (1 / 5) ** (1 / 3)
BUCKETS = ("small", "medium", "large")
BUCKET_LABELS = {"small": "edge < 5%", "medium": "edge 5-15%", "large": "edge >= 15%"}


@dataclass(frozen=True)
class MoneylineTiming:
    games: int
    fetched_after_kickoff: int


def one_call_per_player_game(results: Sequence[LineResult]) -> list[LineResult]:
    """The newest standard full-game line per player, game, and market.

    A player's goblin and demon ladder, or a re-posted standard line, is the same
    bet several times over; counting each would overstate the sample.
    """
    newest: dict[tuple[int, int, str], LineResult] = {}
    for result in results:
        line = result.line
        if line.segment != "full_game" or line.odds_type != STANDARD_ODDS_TYPE:
            continue
        key = (line.player_id, line.game_id, line.market)
        current = newest.get(key)
        if current is None or (line.fetched_at, line.line_id) > (current.line.fetched_at, current.line.line_id):
            newest[key] = result
    return sorted(newest.values(), key=lambda result: result.line.line_id)


def _pct(value: float | None) -> str:
    return f"{value * 100:5.1f}%" if value is not None else "    --"


def _se(value: float | None) -> str:
    return f"+/-{value * 100:4.1f}" if value is not None else "       "


def _rate_row(label: str, summary: RateSummary) -> str:
    return (
        f"  {label:<34}{summary.decided + summary.push:>6}{_pct(summary.over_rate):>9} {_se(summary.standard_error)}"
        f"{summary.push:>7}"
    )


def _hit_row(label: str, summary: HitSummary | None) -> str:
    if summary is None or not summary.calls:
        return f"  {label:<34}{0:>6}{'--':>9}"
    return f"  {label:<34}{summary.calls:>6}{_pct(summary.hit_rate):>9} {_se(summary.standard_error)}{summary.pushes:>7}"


def _coverage_lines(results: Sequence[LineResult], timing: MoneylineTiming) -> list[str]:
    outcomes = [result.outcome for result in results]
    settled = sum(outcome in ("over", "under", "push") for outcome in outcomes)
    return [
        "Coverage",
        f"  lines loaded (pre-kickoff)  {len(results):>6}",
        f"  settled                     {settled:>6}",
        f"  did not play                {outcomes.count('void_dnp'):>6}  (voided by PrizePicks, never a miss)",
        f"  half, quarter or season     {outcomes.count('unsettleable_segment'):>6}  (no per-segment stats)",
        f"  week not loaded             {outcomes.count('week_not_loaded'):>6}  (stats not ingested yet)",
        f"  graded games whose latest moneyline was fetched after kickoff: "
        f"{timing.fetched_after_kickoff} of {timing.games} (an input leak 27b fixes)",
    ]


def _market_table(results: Sequence[LineResult]) -> list[str]:
    groups: dict[tuple[str, str], list[LineResult]] = {}
    for result in results:
        if result.outcome in ("over", "under", "push"):
            groups.setdefault((result.line.market, result.line.odds_type or "unknown"), []).append(result)
    lines = [
        "Over/under by market and odds type (all settled lines)",
        f"  {'market / odds type':<34}{'lines':>6}{'over':>9}{'':8}{'push':>7}",
    ]
    for (market, odds_type), group in sorted(groups.items()):
        lines.append(_rate_row(f"{market} / {odds_type}", rate(group)))
    return lines


def _hit_table(
    calls: Sequence[LineResult], edges: Mapping[int, float], references: Mapping[str, float],
) -> list[str]:
    overall = model_hits(calls, edges, references)
    lines = [
        "Model calls (standard full-game lines, one per player-game and market)",
        f"  break-even per pick: {POWER_2_PICK_BREAK_EVEN * 100:.1f}% (2-pick Power), "
        f"{POWER_3_PICK_BREAK_EVEN * 100:.1f}% (3-pick Power)",
        f"  {'':<34}{'calls':>6}{'hit':>9}{'':8}{'push':>7}",
        _hit_row("all", overall.get("all")),
        *(_hit_row(BUCKET_LABELS[bucket], overall.get(bucket)) for bucket in BUCKETS),
    ]
    for market in sorted({call.line.market for call in calls}):
        in_market = [call for call in calls if call.line.market == market]
        lines.append(_hit_row(f"market {market}", model_hits(in_market, edges, references).get("all")))
    for week in sorted({call.line.week for call in calls}):
        in_week = [call for call in calls if call.line.week == week]
        lines.append(_hit_row(f"week {week}", model_hits(in_week, edges, references).get("all")))
    return lines


def _over_probability_row(label: str, read: OverProbabilityRead) -> str:
    brier = f"{read.report.brier:>8.4f}" if read.report else f"{'--':>8}"
    return (
        f"  {label:<14}{read.scored:>7}{read.unscored:>12}{_pct(read.mean_predicted):>11}"
        f"{_pct(read.over_rate):>9} {_se(read.standard_error)}{brier}"
    )


def _over_probability_table(results: Sequence[LineResult], p_overs: Mapping[int, float]) -> list[str]:
    reads = over_probability_reads(results, p_overs)
    lines = [
        "P(over) against results (27g, display only; every settled line, so a player's ladder counts several times)",
        f"  {'odds type':<14}{'scored':>7}{'no P(over)':>12}{'predicted':>11}{'over':>9}{'':8}{'Brier':>8}",
    ]
    for key in ("standard", "goblin", "demon", "all"):
        if key in reads:
            lines.append(_over_probability_row(key, reads[key]))
    overall = reads.get("all")
    if overall is not None and overall.report is not None:
        lines.append(f"  reliability, all ({len(overall.report.bins)} of 5 bins filled)")
        lines += [
            f"    {b.n:>6} lines  predicted{_pct(b.mean_predicted):>8}  over{_pct(b.observed):>8}"
            for b in overall.report.bins
        ]
    return lines


def report(
    season: int, results: Sequence[LineResult], edges: Mapping[int, float], timing: MoneylineTiming,
    p_overs: Mapping[int, float] | None = None,
) -> str:
    references = reference_lines(result.line for result in results)
    calls = one_call_per_player_game(results)
    return "\n".join([
        f"PrizePicks NFL line grading, {season} (model {NFL_PROJECTION_MODEL_VERSION})",
        "",
        *_coverage_lines(results, timing),
        "",
        *_market_table(results),
        "",
        *_hit_table(calls, edges, references),
        "",
        *_over_probability_table(results, p_overs or {}),
    ])


async def _main(season: int) -> None:
    from app.db.pool import SessionLocal
    from app.services.nfl.track_record import load_line_grading

    async with SessionLocal() as db:
        inputs = await load_line_grading(db, season)
    print(report(season, inputs.results, inputs.edges, inputs.timing, inputs.p_overs))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Grade stored NFL PrizePicks lines against results")
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.season))
