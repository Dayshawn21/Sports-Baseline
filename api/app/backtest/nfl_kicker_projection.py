"""Score the pre-registered kicker projection (27l3) on a season against its reference.

Every K player-game with a stat row is replayed as a fantasy line through the
slate's own `_slate_line`, after `kicker_row` prepares it, and paired with the
K position's blended pre-week mean (`kicker_reference`). The verdict is 27b's
`adoption_verdict` with the reference in production's place. Pre-registered in
`PREREGISTRATION_COMMIT`, before any kicker projection was scored.

It reads and prints. Nothing is fitted, stored, or fed back into a projection.

Run from api/: python -m app.backtest.nfl_kicker_projection [--season 2025]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace

from app.core.nfl_kicker_projection import (
    KICKER_BACKTEST_SEASON, KICKER_REPLAY_MARKETS, NFL_KICKER_MODEL_VERSION, kicker_reference, kicker_row,
)
from app.core.nfl_projection import edge_is_comparable
from app.core.nfl_projection_backtest import ReplayCase, ReplayRow, adoption_verdict, market_metrics, paired
from app.backtest.nfl_projections import REGULAR_SEASON_WEEKS, RULE_TEXT
from app.nfl.markets import NflPropMarket
from app.services.nfl.slate import _slate_line

PREREGISTRATION_COMMIT = "9d4a2bba9dca91e8e7e1b0fd2747b6727429ddf3"
FEWER_THAN_FOUR_GAMES = "fewer than 4 baseline games"
NO_PROJECTION = "no projection (no games, PrizePicks points or position mean)"
NO_REFERENCE = "no position mean for the reference"


@dataclass(frozen=True)
class KickerCases:
    candidate: list[ReplayCase]
    reference: list[ReplayCase]
    excluded: Counter[str]


def _case(replay: ReplayRow, week: int, projection: float) -> ReplayCase:
    row = replay.row
    return ReplayCase(
        player_id=row["player_id"], game_id=row["game_id"], week=week, position=row["position"],
        market=row["market"], projection=projection, actual=replay.actual,
    )


def kicker_cases(rows: Iterable[ReplayRow], season: int, week: int) -> KickerCases:
    candidate, reference, excluded = [], [], Counter[str]()
    for replay in rows:
        line = _slate_line(kicker_row(replay.row, season), season, replay.home_market_prob)
        if line.projection is None:
            excluded[NO_PROJECTION] += 1
            continue
        if not edge_is_comparable(NflPropMarket(line.market), line.games_in_sample, line.segment, line.odds_type):
            excluded[FEWER_THAN_FOUR_GAMES] += 1
            continue
        mean = kicker_reference(replay.row, season)
        if mean is None:
            excluded[NO_REFERENCE] += 1
            continue
        candidate.append(_case(replay, week, line.projection))
        reference.append(_case(replay, week, mean))
    return KickerCases(candidate, reference, excluded)


def without_missed_pats(cases: Sequence[ReplayCase], pat_misses: Mapping[tuple[int, int], int]) -> list[ReplayCase]:
    """Actuals settled under the other consistent formula, -1 per missed PAT (27l2's unresolved term)."""
    return [replace(case, actual=case.actual - pat_misses.get((case.player_id, case.game_id), 0)) for case in cases]


def _metrics_lines(label: str, cases: Sequence[ReplayCase]) -> list[str]:
    m = market_metrics(cases)
    below = f"{m.share_below * 100:6.1f}%" if m.share_below is not None else "     --"
    return [f"  {label:<28}{m.n:>7}{m.mae:>9.3f}{m.rmse:>9.3f}{m.bias:>+9.3f}{below:>9}"]


def report(
    season: int, loaded: int, cases: KickerCases, pat_misses: Mapping[tuple[int, int], int],
) -> str:
    lines = [
        f"Kicker projection backtest, {season} ({NFL_KICKER_MODEL_VERSION}, 27l3, pre-registered {PREREGISTRATION_COMMIT[:8]})",
        "", RULE_TEXT, "Reference: the K position's blended pre-week mean, in production's place.",
        "", "Coverage (K player-games with a stat row, replayed as fantasy lines)",
        f"  {'loaded':<40}{loaded:>6}",
        f"  {'paired cases':<40}{len(cases.candidate):>6}",
    ]
    lines += [f"  {'excluded: ' + reason:<40}{count:>6}" for reason, count in sorted(cases.excluded.items())]
    if not cases.candidate:
        return "\n".join([*lines, "", "Verdict: insufficient (no paired cases)"])
    lines += ["", "Projection minus actual (PrizePicks points under the pinned formula)",
              f"  {'arm':<28}{'n':>7}{'MAE':>9}{'RMSE':>9}{'bias':>9}{'below':>9}"]
    lines += _metrics_lines("candidate " + NFL_KICKER_MODEL_VERSION, cases.candidate)
    lines += _metrics_lines("reference position mean", cases.reference)
    diff = paired(cases.reference, cases.candidate)
    lines += [
        "", "Candidate against reference, paired on player and game",
        f"  {'n':>7}{'ref MAE':>10}{'cand MAE':>10}{'change':>9}{'diff':>9}{'SE':>8}",
        f"  {diff.n:>7}{diff.production_mae:>10.3f}{diff.variant_mae:>10.3f}"
        f"{diff.relative_mae_change * 100:>+8.2f}%{diff.mean_diff:>+9.3f}{diff.standard_error:>8.3f}",
        "", f"Verdict: {adoption_verdict(diff)}",
    ]
    alt = paired(without_missed_pats(cases.reference, pat_misses), without_missed_pats(cases.candidate, pat_misses))
    missed = sum(1 for case in cases.candidate if pat_misses.get((case.player_id, case.game_id), 0))
    lines += [
        "", f"PAT-miss sensitivity (reported, never deciding): {missed} paired games had a missed PAT; "
        f"with -1 per miss, ref MAE {alt.production_mae:.3f}, cand MAE {alt.variant_mae:.3f}, "
        f"change {alt.relative_mae_change * 100:+.2f}%",
    ]
    return "\n".join(lines)


async def _main(season: int) -> None:
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    loaded, candidate, reference, excluded = 0, [], [], Counter[str]()
    async with SessionLocal() as db:
        for week in REGULAR_SEASON_WEEKS:
            rows = await nfl_repo.get_replay_rows(db, season, week, KICKER_REPLAY_MARKETS)
            loaded += len(rows)
            week_cases = kicker_cases(rows, season, week)
            candidate += week_cases.candidate
            reference += week_cases.reference
            excluded += week_cases.excluded
        pat_misses = await nfl_repo.get_kicker_pat_misses(db, season)
    print(report(season, loaded, KickerCases(candidate, reference, excluded), pat_misses))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Score the pre-registered kicker projection against its reference")
    parser.add_argument("--season", type=int, default=KICKER_BACKTEST_SEASON)
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.season))
