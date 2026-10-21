"""Shared display-only team context for NBA game and prop surfaces."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_team_stats import TeamSeasonStats, team_stats
from app.repositories import nba as repo
from app.schemas.nba import NbaTeamStatsContextSchema


@dataclass(frozen=True)
class NbaTeamStatsContext:
    season: int
    before_date: date
    away: TeamSeasonStats
    home: TeamSeasonStats
    basis: Literal["stored_player_box_scores"] = "stored_player_box_scores"


def team_stats_schema(context: NbaTeamStatsContext) -> NbaTeamStatsContextSchema:
    return NbaTeamStatsContextSchema.model_validate(asdict(context))


async def load_team_stats(
    db: AsyncSession, games: Sequence[Mapping[str, object]],
) -> dict[int, NbaTeamStatsContext]:
    contexts = {}
    groups: dict[tuple[int, date], list[Mapping[str, object]]] = {}
    for game in games:
        key = (cast(int, game["season"]), cast(date, game["game_date"]))
        groups.setdefault(key, []).append(game)
    for (season, before), targets in groups.items():
        league = team_stats(await repo.get_team_box_games(db, season, before), season, before)
        for game in targets:
            contexts[cast(int, game["game_id"])] = NbaTeamStatsContext(
                season=season, before_date=before,
                away=league[str(game["away_team"])], home=league[str(game["home_team"])],
            )
    return contexts
