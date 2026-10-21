from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_projection_backtest import NBA_PROJECTION_MODEL_VERSION, NbaHistoryRow
from app.core.nba_slate import adjacent_dates, slate_date
from app.repositories import nba as nba_repo
from app.schemas.nba import NbaInjuryReportSchema, NbaPropBoardGameSchema, NbaPropBoardResponse, NbaTeamStatsContextSchema
from app.services.nba.injuries import load_injury_reports
from app.services.nba.line_only_props import line_only_props
from app.services.nba.props import props_response
from app.services.nba.team_stats import load_team_stats, team_stats_schema


async def build_prop_board(
    db: AsyncSession, requested: dt.date | None, today: dt.date, as_of: dt.datetime | None = None,
) -> NbaPropBoardResponse:
    as_of = as_of if as_of is not None else dt.datetime.now(dt.UTC)
    game_dates = await nba_repo.get_game_dates(db)
    date = slate_date(requested, today, game_dates)
    previous_date, next_date = adjacent_dates(date, game_dates)
    games = await nba_repo.get_games_on(db, date)
    modelled = await nba_repo.get_date_modelled_lines(db, date)
    line_only = await nba_repo.get_date_line_only_lines(db, date)
    player_ids = sorted({
        int(str(line["player_id"]))
        for lines_by_game in (modelled, line_only) for lines in lines_by_game.values() for line in lines
    })
    prior = await nba_repo.get_prior_games(db, player_ids, date) if player_ids else {}
    recent = await nba_repo.get_recent_box_scores(db, player_ids, date) if player_ids else []
    reports = await load_injury_reports(db, games, as_of)
    contexts = {game_id: team_stats_schema(context) for game_id, context in (await load_team_stats(db, games)).items()}
    return prop_board_response(date, previous_date, next_date, games, modelled, line_only, prior, recent, reports, contexts)


def prop_board_response(
    date: dt.date,
    previous_date: dt.date | None,
    next_date: dt.date | None,
    games: Sequence[Mapping[str, object]],
    modelled_by_game: Mapping[int, Sequence[Mapping[str, object]]],
    line_only_by_game: Mapping[int, Sequence[Mapping[str, object]]],
    prior_by_player: Mapping[int, Sequence[NbaHistoryRow]],
    recent_rows: Sequence[Mapping[str, object]],
    reports: Mapping[int, NbaInjuryReportSchema] | None = None,
    team_stats: Mapping[int, NbaTeamStatsContextSchema] | None = None,
) -> NbaPropBoardResponse:
    served = []
    for game in games:
        game_id = int(str(game["game_id"]))
        report = reports.get(game_id) if reports is not None else None
        served.append(NbaPropBoardGameSchema(
            game_id=game_id, away_team=str(game["away_team"]), home_team=str(game["home_team"]),
            start_utc=cast(dt.datetime | None, game["start_utc"]), status=str(game["status"]),
            lines=props_response(game_id, modelled_by_game.get(game_id, []), prior_by_player, recent_rows, report).lines,
            line_only_lines=line_only_props(game_id, line_only_by_game.get(game_id, []), recent_rows, report).lines,
            injury_report=report if report is not None else NbaInjuryReportSchema(),
            team_stats=team_stats.get(game_id) if team_stats is not None else None,
        ))
    return NbaPropBoardResponse(
        date=date, previous_date=previous_date, next_date=next_date,
        model_version=NBA_PROJECTION_MODEL_VERSION, games=served,
    )
