"""The NBA game page's modelled props: each line with the reference projection (item 20g2).

Display only: the gap and P(over) are gray, never sorted by or compared to a payout,
until 20g4's ranking check adopts a slice.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_projection import project_line
from app.core.nba_projection_backtest import NBA_PROJECTION_MODEL_VERSION, NbaHistoryRow
from app.nba.markets import NbaPropMarket
from app.repositories import nba as nba_repo
from app.schemas.nba import NbaInjuryReportSchema, NbaPropLineSchema, NbaPropsResponse
from app.services.nba.injuries import injury_index, load_injury_reports
from app.services.nba.line_only_props import group_by_player, line_fields, ordered_lines, recent_values


async def build_props(
    db: AsyncSession, game_id: int, as_of: dt.datetime | None = None,
) -> NbaPropsResponse | None:
    as_of = as_of if as_of is not None else dt.datetime.now(dt.UTC)
    game = await nba_repo.get_game(db, game_id)
    if game is None:
        return None
    lines = await nba_repo.get_modelled_lines(db, game_id)
    player_ids = sorted({int(str(line["player_id"])) for line in lines})
    game_date = cast(dt.date, game["game_date"])
    prior = await nba_repo.get_prior_games(db, player_ids, game_date) if player_ids else {}
    recent_rows = await nba_repo.get_recent_box_scores(db, player_ids, game_date) if player_ids else []
    reports = await load_injury_reports(db, [game], as_of)
    return props_response(game_id, lines, prior, recent_rows, reports[game_id])


def props_response(
    game_id: int,
    lines: Sequence[Mapping[str, object]],
    prior_by_player: Mapping[int, Sequence[NbaHistoryRow]],
    recent_rows: Sequence[Mapping[str, object]],
    report: NbaInjuryReportSchema | None = None,
) -> NbaPropsResponse:
    report = report if report is not None else NbaInjuryReportSchema()
    injuries = injury_index(report)
    rows_by_player = group_by_player(recent_rows)
    served = []
    for line in ordered_lines(lines):
        prior = prior_by_player.get(int(str(line["player_id"])), [])
        projection = project_line(prior, NbaPropMarket(str(line["market"])), float(str(line["line"])))
        fields = {key: value for key, value in asdict(projection).items() if key != "model_version"}
        served.append(NbaPropLineSchema(
            **line_fields(line, injuries), **fields, recent=recent_values(line, rows_by_player),
        ))
    return NbaPropsResponse(
        game_id=game_id, model_version=NBA_PROJECTION_MODEL_VERSION, lines=served, injury_report=report,
    )
