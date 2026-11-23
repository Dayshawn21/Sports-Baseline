"""How many 2024 replay rows a usage-shift parameter set would touch, and who it misses (70b2).

Counts only: it prints no projection, no error and no actual value, so it
spends nothing. It runs on 2024, the development season, alone; 2025 is the
holdout and is never read here.

Run from api/: python -m app.backtest.nfl_usage_shift_counts --transfer 1.0
    --min-own-volume 1.0 --max-multiplier 3.0
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from statistics import median

from app.core.nfl_projection_backtest import ReplayRow
from app.core.nfl_usage_shift import (
    CARRIES_BELOW_MIN, SHIFT_POSITIONS, TARGETS_BELOW_MIN, apply_usage_shift, missed_out_players, usage_shifts,
)
from app.nfl.markets import NflPropMarket

DEVELOPMENT_SEASON = 2024
REGULAR_SEASON_WEEKS = range(1, 19)
SHIFT_MARKETS = (
    NflPropMarket.RUSHING_YARDS, NflPropMarket.RUSHING_ATTEMPTS, NflPropMarket.RECEIVING_YARDS, NflPropMarket.RECEPTIONS,
)
_BELOW_MIN = {
    NflPropMarket.RUSHING_YARDS: CARRIES_BELOW_MIN, NflPropMarket.RUSHING_ATTEMPTS: CARRIES_BELOW_MIN,
    NflPropMarket.RECEIVING_YARDS: TARGETS_BELOW_MIN, NflPropMarket.RECEPTIONS: TARGETS_BELOW_MIN,
}


@dataclass
class MarketCounts:
    rows: int = 0
    multipliers: list[float] = field(default_factory=list)
    below_min: int = 0


@dataclass
class ShiftCounts:
    markets: dict[NflPropMarket, MarketCounts]
    givers: int
    missed: Counter[str]


def count_shifts(
    rows: Iterable[ReplayRow], transfer: float, min_own_volume: float, max_multiplier: float,
) -> ShiftCounts:
    markets = {market: MarketCounts() for market in SHIFT_MARKETS}
    givers: set[tuple[int, int]] = set()
    missed: dict[tuple[int, int], str] = {}
    for replay in rows:
        row, players = replay.row, replay.usage_shift_players
        if row.get("position") not in SHIFT_POSITIONS or row["market"] not in SHIFT_MARKETS or not players:
            continue
        game_id, market = row["game_id"], NflPropMarket(row["market"])
        counts = markets[market]
        counts.rows += 1
        shift = usage_shifts(players, transfer, min_own_volume, max_multiplier).get(row["player_id"])
        missed |= {(game_id, player_id): reason for player_id, reason in missed_out_players(players).items()}
        if shift is None:
            continue
        givers |= {(game_id, giver) for giver in shift.from_players}
        if _BELOW_MIN[market] in shift.unshifted:
            counts.below_min += 1
            continue
        shifted = apply_usage_shift(row, shift).get("usage_shift")
        if shifted is not None and shifted["multiplier"] != 1.0:
            counts.multipliers.append(shifted["multiplier"])
    return ShiftCounts(markets, len(givers), Counter(missed.values()))


def report(counts: ShiftCounts, transfer: float, min_own_volume: float, max_multiplier: float) -> str:
    lines = [
        f"NFL usage-shift counts, {DEVELOPMENT_SEASON} (counts only; no projection, error or result printed)",
        f"transfer={transfer:g} min_own_volume={min_own_volume:g} max_multiplier={max_multiplier:g}",
        "",
        f"{'Market':<18}{'RB/WR/TE rows':>15}{'Shifted':>9}{'Median x':>10}{'Range':>14}{'Below min':>11}",
    ]
    for market, market_counts in counts.markets.items():
        values = market_counts.multipliers
        spread = f"{min(values):.2f}-{max(values):.2f}" if values else "-"
        middle = f"{median(values):.2f}" if values else "-"
        lines.append(
            f"{market.value:<18}{market_counts.rows:>15}{len(values):>9}{middle:>10}{spread:>14}{market_counts.below_min:>11}"
        )
    missed = ", ".join(f"{reason} {count}" for reason, count in sorted(counts.missed.items())) or "none"
    lines += ["", f"Out players who gave volume: {counts.givers}", f"Out players missed: {missed}"]
    return "\n".join(lines)


async def _main(transfer: float, min_own_volume: float, max_multiplier: float) -> None:
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    rows: list[ReplayRow] = []
    async with SessionLocal() as db:
        for week in REGULAR_SEASON_WEEKS:
            rows += await nfl_repo.get_replay_rows(db, DEVELOPMENT_SEASON, week)
    print(report(count_shifts(rows, transfer, min_own_volume, max_multiplier), transfer, min_own_volume, max_multiplier))


def main() -> None:
    parser = argparse.ArgumentParser(description="Count 2024 replay rows a usage-shift parameter set would touch")
    parser.add_argument("--season", type=int, default=DEVELOPMENT_SEASON)
    parser.add_argument("--transfer", type=float, required=True)
    parser.add_argument("--min-own-volume", type=float, required=True)
    parser.add_argument("--max-multiplier", type=float, required=True)
    args = parser.parse_args()
    if args.season != DEVELOPMENT_SEASON:
        parser.error(
            f"only {DEVELOPMENT_SEASON}, the development season, may be read here; "
            "2025 is the usage-shift holdout and needs 70b3 and a separate yes"
        )
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.transfer, args.min_own_volume, args.max_multiplier))


if __name__ == "__main__":
    main()
