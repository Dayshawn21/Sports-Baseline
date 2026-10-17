"""Freeze what the NBA game page serves for each line before tip-off (item 20g3)."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_prop_predictions import freezable_games
from app.core.prop_predictions import FreezableGame
from app.repositories import nba as nba_repo


async def week_freezable_games(db: AsyncSession, season: int, week: int, now: datetime) -> list[FreezableGame]:
    """The week's modelled lines, each projected from the player's games before its own game date."""
    lines = await nba_repo.get_week_modelled_lines(db, season, week)
    players_by_date: dict[date, set[int]] = {}
    for line in lines:
        players_by_date.setdefault(line.game_date, set()).add(line.player_id)
    prior_by_date = {
        game_date: await nba_repo.get_prior_games(db, sorted(player_ids), game_date)
        for game_date, player_ids in players_by_date.items()
    }
    return freezable_games(lines, prior_by_date, now)
