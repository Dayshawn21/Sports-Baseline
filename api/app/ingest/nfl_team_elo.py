"""Recompute NFL team ELO from every stored regular-season score.

The whole history is replayed each run, so a corrected score anywhere
propagates forward. Run from api/: python -m app.ingest.nfl_team_elo
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date

from scipy.stats import spearmanr

from app.core.nfl_elo import (
    NFL_ELO_MODEL_VERSION, current_ratings, point_differentials, replay, season_end_ratings,
)
from app.ingest.nflverse import current_nfl_season


def _ranking(ratings: dict[str, float], count: int) -> str:
    ordered = sorted(ratings.items(), key=lambda item: item[1], reverse=True)
    top = ", ".join(f"{team} {elo:.0f}" for team, elo in ordered[:count])
    bottom = ", ".join(f"{team} {elo:.0f}" for team, elo in ordered[-count:])
    return f"Top {count}: {top}\nBottom {count}: {bottom}"


async def run(check_season: int, dry_run: bool = False) -> str:
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    async with SessionLocal() as db:
        games = await nfl_repo.get_elo_games(db)
        rows = replay(games)
        deleted = inserted = 0
        if not dry_run:
            deleted, inserted = await nfl_repo.replace_team_elo(db, rows, NFL_ELO_MODEL_VERSION)
            await db.commit()

    seasons = sorted({game.season for game in games})
    end_ratings = season_end_ratings(rows, check_season)
    differentials = point_differentials(games, check_season)
    teams = sorted(end_ratings.keys() & differentials.keys())
    correlation = spearmanr([end_ratings[team] for team in teams], [differentials[team] for team in teams]).statistic
    return "\n".join([
        f"{NFL_ELO_MODEL_VERSION}: {len(rows)} rows from {len(games)} games, seasons {seasons[0]}-{seasons[-1]}"
        if seasons else f"{NFL_ELO_MODEL_VERSION}: no games stored",
        "dry run, nothing written" if dry_run else f"replaced {deleted} rows with {inserted}",
        f"Spearman, end-of-{check_season} ELO vs {check_season} point differential: {correlation:.3f}",
        _ranking(current_ratings(rows), 5),
    ])


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Recompute NFL team ELO from stored scores")
    parser.add_argument(
        "--check-season", type=int, default=None,
        help="finished season to sanity-check ratings against; defaults to the one before the current season",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    check_season = args.check_season if args.check_season is not None else current_nfl_season(date.today()) - 1
    print(await run(check_season, args.dry_run))


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
