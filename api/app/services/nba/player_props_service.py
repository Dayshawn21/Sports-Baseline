"""The NBA player page's data: one player's props on a slate date (item 53a)."""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_teammate_split import split_teammates
from app.core.slate_dates import slate_date
from app.repositories import nba as nba_repo
from app.schemas.nba import NbaInjuryReportSchema, NbaPlayerPropsResponse, NbaTeammateSplitSchema
from app.services.nba.injuries import load_injury_reports
from app.services.nba.player_props import (
    OPPONENT_GAMES_LIMIT, RECENT_GAMES_LIMIT, opponent_code, player_props_response, resolve_team, teammate_split,
)
from app.services.nba.team_stats import load_team_stats, team_stats_schema


async def build_player_props(
    db: AsyncSession, player_id: int, requested: dt.date | None, today: dt.date, as_of: dt.datetime | None = None,
) -> NbaPlayerPropsResponse | None:
    """None for an unknown player. A date with no line for them is an empty response, not an error."""
    as_of = as_of if as_of is not None else dt.datetime.now(dt.UTC)
    player = await nba_repo.get_player(db, player_id)
    if player is None:
        return None
    date = slate_date(requested, today, await nba_repo.get_game_dates(db))
    modelled = await nba_repo.get_player_date_modelled_lines(db, player_id, date)
    line_only = await nba_repo.get_player_date_line_only_lines(db, player_id, date)
    game_ids = {cast(int, line["game_id"]) for line in (*modelled, *line_only)}
    game = next((game for game in await nba_repo.get_games_on(db, date) if game["game_id"] in game_ids), None) if game_ids else None
    if game is None:
        return player_props_response(player, date, None, [], [], {}, [], [])
    lines = [_without_game(line) for line in modelled], [_without_game(line) for line in line_only]
    prior = await nba_repo.get_prior_games(db, [player_id], date)
    recent = await nba_repo.get_recent_box_scores(db, [player_id], date, limit=RECENT_GAMES_LIMIT)
    opponent = opponent_code(resolve_team(player, [*modelled, *line_only]), game)
    opponent_rows = (
        await nba_repo.get_player_games_against(db, player_id, opponent, date, OPPONENT_GAMES_LIMIT)
        if opponent is not None else []
    )
    report = (await load_injury_reports(db, [game], as_of))[cast(int, game["game_id"])]
    context = team_stats_schema((await load_team_stats(db, [game]))[cast(int, game["game_id"])])
    response = player_props_response(player, date, game, *lines, prior, recent, opponent_rows, report, context)
    response.teammate_split = await _teammate_split(db, response, cast(int, game["season"]), report)
    return response


async def _teammate_split(
    db: AsyncSession, response: NbaPlayerPropsResponse, season: int, report: NbaInjuryReportSchema,
) -> NbaTeammateSplitSchema | None:
    """None unless someone on the player's team is listed out; otherwise two queries bounded by one season."""
    team = response.team
    if team is None or response.opponent is None:
        return None
    teammates = split_teammates(report.injuries, team, response.player_id)
    if not teammates:
        return None
    games = await nba_repo.get_season_games_for_team(db, response.player_id, team, season, response.date)
    teammate_ids = [cast(int, entry.player_id) for entry in teammates]
    game_ids = [cast(int, row["game_id"]) for row in games]
    rows = await nba_repo.get_teammate_rows(db, teammate_ids, team, game_ids, response.date)
    markets = [market.market for market in response.markets]
    return teammate_split(season, team, markets, teammates, report.freshness == "stale", games, rows)


def _without_game(line: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in line.items() if key != "game_id"}
