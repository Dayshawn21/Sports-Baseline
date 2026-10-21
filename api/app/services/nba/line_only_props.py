"""The NBA game page's line-only props: each stored line and the player's recent values (item 20e1).

Display only. Since 20g2 the endpoint serves the line-only markets (double-double);
the builder orders and settles any NBA market.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_line_only import line_only_value
from app.core.nba_names import espn_team_code
from app.nba.markets import NBA_MARKETS, nba_market
from app.repositories import nba as nba_repo
from app.schemas.nba import (
    NbaInjuryReportSchema, NbaInjurySchema, NbaLineOnlyLineSchema, NbaLineOnlyPropsResponse, NbaLineOnlyRecentSchema,
)
from app.services.nba.injuries import injury_index, load_injury_reports

_MARKET_ORDER = {market.value: index for index, market in enumerate(NBA_MARKETS)}


async def build_line_only_props(
    db: AsyncSession, game_id: int, as_of: dt.datetime | None = None,
) -> NbaLineOnlyPropsResponse | None:
    as_of = as_of if as_of is not None else dt.datetime.now(dt.UTC)
    game = await nba_repo.get_game(db, game_id)
    if game is None:
        return None
    lines = await nba_repo.get_line_only_lines(db, game_id)
    player_ids = sorted({int(str(line["player_id"])) for line in lines})
    recent_rows = await nba_repo.get_recent_box_scores(db, player_ids, cast(dt.date, game["game_date"])) if player_ids else []
    reports = await load_injury_reports(db, [game], as_of)
    return line_only_props(game_id, lines, recent_rows, reports[game_id])


def line_only_props(
    game_id: int, lines: Sequence[Mapping[str, object]], recent_rows: Sequence[Mapping[str, object]],
    report: NbaInjuryReportSchema | None = None,
) -> NbaLineOnlyPropsResponse:
    report = report if report is not None else NbaInjuryReportSchema()
    injuries = injury_index(report)
    rows_by_player = group_by_player(recent_rows)
    return NbaLineOnlyPropsResponse(
        game_id=game_id, injury_report=report,
        lines=[
            NbaLineOnlyLineSchema(**line_fields(line, injuries), recent=recent_values(line, rows_by_player))
            for line in ordered_lines(lines)
        ],
    )


def ordered_lines(lines: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    """By market (enum order), then player name, then line."""
    return sorted(lines, key=lambda line: (_MARKET_ORDER[str(line["market"])], str(line["player_name"]), float(str(line["line"]))))


def group_by_player(rows: Sequence[Mapping[str, object]]) -> dict[object, list[Mapping[str, object]]]:
    grouped: dict[object, list[Mapping[str, object]]] = {}
    for row in rows:
        grouped.setdefault(row["player_id"], []).append(row)
    return grouped


def line_fields(
    line: Mapping[str, object], injuries: Mapping[tuple[int, str], NbaInjurySchema],
) -> dict[str, object]:
    """A stored line with its provider team as the ESPN code the game's teams use."""
    team = espn_team_code(cast(str | None, line["team"]))
    injury = injuries.get((int(str(line["player_id"])), team)) if team is not None else None
    return {**line, "team": team, "injury": injury}


def recent_values(
    line: Mapping[str, object], rows_by_player: Mapping[object, Sequence[Mapping[str, object]]],
) -> list[NbaLineOnlyRecentSchema]:
    market = nba_market(str(line["market"]))
    return [
        NbaLineOnlyRecentSchema(game_date=row["game_date"], opponent=row["opponent"], value=line_only_value(market, row))
        for row in rows_by_player.get(line["player_id"], [])
    ]
