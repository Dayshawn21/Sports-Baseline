"""One stored NHL date of line-only offerings, built from the same rows and ordering as each game's props endpoint."""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.slate_dates import adjacent_dates, slate_date
from app.repositories import nhl
from app.schemas.nhl import NhlPropBoardGameSchema, NhlPropBoardResponse
from app.services.nhl.line_only_props import line_only_props


def prop_board_response(
    date: dt.date,
    previous_date: dt.date | None,
    next_date: dt.date | None,
    games: Sequence[Mapping[str, object]],
    lines_by_game: Mapping[int, Sequence[Mapping[str, object]]],
) -> NhlPropBoardResponse:
    return NhlPropBoardResponse(
        date=date, previous_date=previous_date, next_date=next_date,
        games=[
            NhlPropBoardGameSchema(
                game_id=int(str(game["game_id"])), away_team=str(game["away_team"]), home_team=str(game["home_team"]),
                start_utc=cast(dt.datetime | None, game["start_utc"]), status=str(game["status"]),
                lines=line_only_props(game, lines_by_game.get(int(str(game["game_id"])), [])).lines,
            )
            for game in games
        ],
    )


async def build_prop_board(db: AsyncSession, requested: dt.date | None, today: dt.date) -> NhlPropBoardResponse:
    dates = await nhl.get_game_dates(db)
    selected = slate_date(requested, today, dates)
    previous_date, next_date = adjacent_dates(selected, dates)
    games = await nhl.get_games_on(db, selected)
    lines = await nhl.get_date_line_only_lines(db, selected) if games else {}
    return prop_board_response(selected, previous_date, next_date, games, lines)
