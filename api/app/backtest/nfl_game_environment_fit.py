"""Fit the per-market game-environment slopes on one season (build-plan item 27e).

Each player-game is compared with the player's other games that season: the
stat against their leave-one-out mean, and the implied team total and margin
against the same games' means. The kept slopes are copied by hand into
`GAME_ENVIRONMENT_SLOPES`; nothing is stored. Fit on 2024 only, since 2025 is
the projection holdout.

Run from api/: python -m app.backtest.nfl_game_environment_fit [--season 2024]
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from app.core.nfl_game_environment import (
    KEEP_SLOPE_STANDARD_ERRORS, NflEnvironmentFit, NflEnvironmentGame, environment_samples, fit_environment_slopes,
)
from app.nfl.markets import NFL_V4_PROP_MARKETS, NflPropMarket

FIT_MARKETS = tuple(
    market for market in NflPropMarket
    if market in NFL_V4_PROP_MARKETS and market is not NflPropMarket.ANYTIME_TOUCHDOWN
)


def _row(market: NflPropMarket, fit: NflEnvironmentFit | None) -> str:
    if fit is None:
        return f"  {market.value:<22}  not enough players to fit"
    kept = fit.kept()
    return (
        f"  {market.value:<22}{fit.n:>7}{fit.players:>8}"
        f"{fit.total:>+9.3f}{fit.total_se:>8.3f}{fit.margin:>+9.3f}{fit.margin_se:>8.3f}"
        f"{kept.total:>+9.3f}{kept.margin:>+9.3f}"
    )


def report(season: int, games: list[NflEnvironmentGame]) -> str:
    lines = [
        f"NFL game-environment fit, {season} REG, {len(games)} player-games with closing lines",
        f"Slopes kept only when at least {KEEP_SLOPE_STANDARD_ERRORS:g} player-clustered SE from zero.",
        "total: change per unit team_total / baseline_team_total - 1; margin: per 7 points above baseline margin",
        f"  {'market':<22}{'n':>7}{'players':>8}{'total':>9}{'SE':>8}{'margin':>9}{'SE':>8}{'keep T':>9}{'keep M':>9}",
    ]
    for market in FIT_MARKETS:
        lines.append(_row(market, fit_environment_slopes(environment_samples(games, market))))
    return "\n".join(lines)


async def _main(season: int) -> None:
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    async with SessionLocal() as db:
        games = await nfl_repo.get_environment_fit_games(db, season)
    print(report(season, games))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fit NFL game-environment slopes on one season")
    parser.add_argument("--season", type=int, default=2024)
    args = parser.parse_args()
    if args.season >= 2025:
        parser.error("2025 onward is the projection holdout; fit on 2024")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.season))
