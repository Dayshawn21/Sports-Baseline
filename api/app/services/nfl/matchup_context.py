"""Bounded, read-only NFL display context shared by game notes and drawers."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_matchup_context import PlayerUsageGame, player_usage, position_allowed
from app.repositories import nfl as nfl_repo
from app.schemas.nfl import (
    NflContextPlayerSchema, NflGameContextResponse, NflMatchupContextSchema,
    NflMatchupTeamSchema, NflPositionAllowedSchema, NflUsageWindowSchema,
)


async def build_week_matchup_context(
    db: AsyncSession, season: int, week: int,
) -> dict[int, NflMatchupContextSchema]:
    games = await nfl_repo.get_context_games(db, season=season, week=week)
    return await _matchups(db, games)


async def _matchups(
    db: AsyncSession, games: list[nfl_repo.NflContextGame],
) -> dict[int, NflMatchupContextSchema]:
    if not games:
        return {}
    kickoffs = [game.start_utc for game in games if game.start_utc is not None]
    first = games[0]
    rows = await nfl_repo.get_context_allowed_games(db, first.season, first.week, max(kickoffs)) if kickoffs else []
    team_ids = {row.team_id for row in rows} | {team for game in games for team in (game.away_team_id, game.home_team_id)}
    matchups: dict[int, NflMatchupContextSchema] = {}
    for game in games:
        allowed = position_allowed(rows, team_ids, game.cutoff)
        matchups[game.game_id] = NflMatchupContextSchema(
            away=NflMatchupTeamSchema(team_id=game.away_team_id, team=game.away_team,
                                     allowed=NflPositionAllowedSchema(**allowed[game.away_team_id])),
            home=NflMatchupTeamSchema(team_id=game.home_team_id, team=game.home_team,
                                     allowed=NflPositionAllowedSchema(**allowed[game.home_team_id])),
        )
    return matchups


async def build_game_context(db: AsyncSession, game_id: int) -> NflGameContextResponse | None:
    games = await nfl_repo.get_context_games(db, game_id=game_id)
    if not games:
        return None
    game = games[0]
    matchups = await _matchups(db, games)
    roster = await nfl_repo.get_context_roster(db, game)
    history = await nfl_repo.get_context_player_history(db, game, [player.player_id for player in roster])
    by_player: dict[int, list[PlayerUsageGame]] = {}
    for row in history:
        by_player.setdefault(row.player_id, []).append(row.usage)
    players: list[NflContextPlayerSchema] = []
    for player in sorted(roster, key=lambda row: (row.team, row.name, row.player_id)):
        usage = player_usage(by_player.get(player.player_id, []), game.cutoff)
        players.append(NflContextPlayerSchema(
            player_id=player.player_id, name=player.name, position=player.position, team=player.team,
            season_usage=NflUsageWindowSchema.model_validate(usage.season_usage),
            recent_usage=NflUsageWindowSchema.model_validate(usage.recent_usage),
        ))
    return NflGameContextResponse(
        game_id=game.game_id, season=game.season, week=game.week, cutoff_week=game.week - 1,
        matchup_context=matchups[game.game_id], players=players,
    )
