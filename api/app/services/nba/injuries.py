"""Shared stored NBA injury context; never used by projection or freeze code."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_injuries import ESPN_NBA_TEAMS, NbaInjurySnapshot, injury_freshness
from app.repositories import nba_injuries as repo
from app.schemas.nba import NbaInjuryReportSchema, NbaInjurySchema


def injury_report(
    game: Mapping[str, object], snapshot: NbaInjurySnapshot | None, as_of: datetime,
) -> NbaInjuryReportSchema:
    start = cast(datetime | None, game["start_utc"])
    freshness = injury_freshness(snapshot.fetched_at if snapshot else None, start, as_of)
    if freshness == "unavailable" or snapshot is None:
        return NbaInjuryReportSchema()
    teams = {str(game["away_team"]), str(game["home_team"])}
    injuries = []
    for linked in snapshot.injuries:
        entry = linked.injury
        if entry.team_code not in teams:
            continue
        injuries.append(NbaInjurySchema(
            espn_athlete_id=entry.espn_athlete_id, player_id=linked.player_id,
            player_name=entry.player_name, team=entry.team_code,
            athlete_team=ESPN_NBA_TEAMS.get(entry.athlete_team_id) if entry.athlete_team_id else None,
            status=entry.status, detail=entry.detail, source_updated_at=entry.source_updated_at,
            return_date=entry.return_date, fetched_at=snapshot.fetched_at,
        ))
    return NbaInjuryReportSchema(fetched_at=snapshot.fetched_at, freshness=freshness, injuries=injuries)


def injury_index(report: NbaInjuryReportSchema) -> dict[tuple[int, str], NbaInjurySchema]:
    return {
        (entry.player_id, entry.team): entry for entry in report.injuries
        if entry.player_id is not None and (entry.athlete_team is None or entry.athlete_team == entry.team)
    }


async def load_injury_reports(
    db: AsyncSession, games: Sequence[Mapping[str, object]], as_of: datetime,
) -> dict[int, NbaInjuryReportSchema]:
    game_ids = [int(str(game["game_id"])) for game in games]
    snapshots = await repo.get_game_snapshots(db, game_ids, as_of) if game_ids else {}
    return {
        int(str(game["game_id"])): injury_report(game, snapshots.get(int(str(game["game_id"]))), as_of)
        for game in games
    }
