from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nhl_context_resolution import ContextGameCandidate, resolve_context_event
from app.core.nhl_context_snapshots import GoalieSnapshot, InjurySnapshot, StoredGoalie, context_freshness
from app.repositories import nhl_context as repo
from app.schemas.nhl import NhlSlateGameSchema
from app.schemas.nhl_context import (
    NhlGameContextSchema, NhlGoalieContext, NhlGoalieSide, NhlInjuryContext, NhlInjurySchema,
)


def unavailable_context(away: str, home: str) -> NhlGameContextSchema:
    return NhlGameContextSchema(injuries=NhlInjuryContext(), goalies=NhlGoalieContext(
        away=NhlGoalieSide(team=away), home=NhlGoalieSide(team=home),
    ))


def injury_context(game: NhlSlateGameSchema, snapshot: InjurySnapshot | None, as_of: datetime) -> NhlInjuryContext:
    freshness = context_freshness(snapshot.fetched_at if snapshot else None, game.start_utc, as_of)
    if snapshot is None or freshness == "unavailable":
        return NhlInjuryContext()
    sides: dict[str, list[NhlInjurySchema]] = {game.away_team: [], game.home_team: []}
    for stored in snapshot.injuries:
        entry = stored.entry
        if entry.team_code in sides:
            sides[entry.team_code].append(NhlInjurySchema(
                espn_athlete_id=entry.espn_athlete_id, player_id=stored.player.player_id,
                player_name=entry.player_name, team=entry.team_code, status=entry.status,
                detail=entry.detail, source_updated_at=entry.source_updated_at, return_date=entry.return_date,
                link_reason=stored.player.reason, team_mismatch=entry.team_mismatch,
            ))
    return NhlInjuryContext(
        fetched_at=snapshot.fetched_at, source_timestamp=snapshot.source_timestamp, freshness=freshness,
        away=sorted(sides[game.away_team], key=lambda row: (row.player_name, row.espn_athlete_id)),
        home=sorted(sides[game.home_team], key=lambda row: (row.player_name, row.espn_athlete_id)),
    )


def _valid_goalies(game: NhlSlateGameSchema, rows: tuple[StoredGoalie, ...]) -> bool:
    if len(rows) != 2 or len({row.observation.espn_event_id for row in rows}) != 1:
        return False
    if {row.observation.team_code for row in rows} != {game.away_team, game.home_team}:
        return False
    candidate = ContextGameCandidate(game.game_id, "nhl", game.game_type, game.away_team, game.home_team, game.start_utc)
    for stored in rows:
        entry = stored.observation
        match = resolve_context_event(entry.away_team, entry.home_team, entry.start_utc,
                                      [candidate], time_valid=entry.time_valid)
        if (entry.event_date != game.game_date or stored.game.game_id != game.game_id
                or stored.game.reason != "matched" or match.game_id != game.game_id):
            return False
    return True


def goalie_context(game: NhlSlateGameSchema, snapshot: GoalieSnapshot | None, as_of: datetime) -> NhlGoalieContext:
    missing = unavailable_context(game.away_team, game.home_team).goalies
    freshness = context_freshness(snapshot.fetched_at if snapshot else None, game.start_utc, as_of)
    if snapshot is None or freshness == "unavailable":
        return missing
    if not _valid_goalies(game, snapshot.observations):
        return missing.model_copy(update={"fetched_at": snapshot.fetched_at, "source_timestamp": snapshot.source_timestamp})
    sides = {}
    for stored in snapshot.observations:
        entry = stored.observation
        sides[entry.team_code] = NhlGoalieSide(
            team=entry.team_code, espn_athlete_id=entry.espn_athlete_id, player_id=stored.player.player_id,
            player_name=entry.player_name, status=entry.status, raw_status=entry.raw_status, link_reason=stored.player.reason,
        )
    return NhlGoalieContext(fetched_at=snapshot.fetched_at, source_timestamp=snapshot.source_timestamp,
                            freshness=freshness, away=sides[game.away_team], home=sides[game.home_team])


async def load_contexts(
    db: AsyncSession, games: Sequence[NhlSlateGameSchema], as_of: datetime,
) -> dict[int, NhlGameContextSchema]:
    game_ids = [game.game_id for game in games]
    if not game_ids:
        return {}
    try:
        injuries = await repo.get_injury_snapshots(db, game_ids, as_of)
        goalies = await repo.get_goalie_snapshots(db, game_ids, as_of)
    except ProgrammingError as exc:
        if getattr(exc.orig, "sqlstate", None) == "42P01":
            raise HTTPException(503, "NHL context storage is unavailable; apply migration 0050.") from None
        raise
    return {game.game_id: NhlGameContextSchema(
        injuries=injury_context(game, injuries.get(game.game_id), as_of),
        goalies=goalie_context(game, goalies.get(game.game_id), as_of),
    ) for game in games}
