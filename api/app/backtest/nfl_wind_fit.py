"""Fit the per-market wind slopes on one season (build-plan item 27k).

Each known-wind player-game is compared with the player's other games that
season. The kept slopes are copied by hand into `WIND_SLOPES`; nothing is
stored. Fit on 2024 only, since 2025 is the projection holdout.

Run from api/: python -m app.backtest.nfl_wind_fit [--season 2024]
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from app.core.nfl_game_context import INDOOR_ROOFS
from app.core.nfl_game_environment import KEEP_SLOPE_STANDARD_ERRORS, NflEnvironmentGame
from app.core.nfl_wind import (
    WIND_MARKETS, WIND_SCALE_MPH, WIND_THRESHOLD_MPH, NflWindFit, excess_wind, fit_wind_slope, wind_samples,
)


def _row(market: str, fit: NflWindFit | None) -> str:
    if fit is None:
        return f"  {market:<22}  not enough players to fit"
    return (
        f"  {market:<22}{fit.n:>7}{fit.players:>8}{fit.windy:>7}"
        f"{fit.slope:>+9.3f}{fit.se:>8.3f}{fit.kept():>+9.3f}"
    )


def _coverage(games: list[NflEnvironmentGame]) -> str:
    excesses = [excess_wind(game.roof, game.wind) for game in games]
    indoor = sum(1 for game in games if game.roof in INDOOR_ROOFS)
    unknown = sum(1 for excess in excesses if excess is None)
    windy = sum(1 for excess in excesses if excess is not None and excess > 0)
    return f"player-games: {len(games)} total, {indoor} indoor, {windy} windy outdoors, {unknown} wind unknown"


def report(season: int, games: list[NflEnvironmentGame]) -> str:
    lines = [
        f"NFL wind fit, {season} REG",
        _coverage(games),
        f"x = max(0, wind - {WIND_THRESHOLD_MPH}) / {WIND_SCALE_MPH:g} mph outdoors, 0 indoors; "
        f"kept only when at least {KEEP_SLOPE_STANDARD_ERRORS:g} player-clustered SE from zero.",
        f"  {'market':<22}{'n':>7}{'players':>8}{'windy':>7}{'slope':>9}{'SE':>8}{'keep':>9}",
    ]
    for market in sorted(WIND_MARKETS):
        lines.append(_row(market.value, fit_wind_slope(wind_samples(games, market))))
    return "\n".join(lines)


async def _main(season: int) -> None:
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    async with SessionLocal() as db:
        games = await nfl_repo.get_environment_fit_games(db, season)
    print(report(season, games))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fit NFL wind slopes for passing markets on one season")
    parser.add_argument("--season", type=int, default=2024)
    args = parser.parse_args()
    if args.season >= 2025:
        parser.error("2025 onward is the projection holdout; fit on 2024")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.season))
