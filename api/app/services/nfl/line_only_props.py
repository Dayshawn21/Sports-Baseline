"""The game page's line-only props (item 35): each stored line and the player's recent values.

Display only. It reads stored lines and weekly stats directly and never calls
`build_slate`, so the modelled board and its parity are untouched.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_line_only import line_only_value
from app.nfl.markets import NflLineOnlyMarket
from app.repositories import nfl as nfl_repo
from app.schemas.nfl import NflLineOnlyLineSchema, NflLineOnlyPropsResponse, NflLineOnlyRecentSchema
from app.schemas.nfl import NflLineOnlyBoardGame, NflLineOnlyBoardResponse

_MARKET_ORDER = {market.value: index for index, market in enumerate(NflLineOnlyMarket)}


async def build_week_line_only_props(db: AsyncSession, season: int, week: int) -> NflLineOnlyBoardResponse:
    games = await nfl_repo.get_games(db, season, week)
    lines = await nfl_repo.get_week_line_only_lines(db, season, week)
    player_ids = sorted({line["player_id"] for line in lines})
    recent = await nfl_repo.get_recent_stat_rows(db, player_ids, season, week) if player_ids else []
    by_game: dict[int, list[dict]] = defaultdict(list)
    for line in lines:
        by_game[line["game_id"]].append(line)
    return NflLineOnlyBoardResponse(
        season=season, week=week,
        games=[NflLineOnlyBoardGame(
            **game, lines=line_only_props(game["game_id"], by_game[game["game_id"]], recent).lines,
        ) for game in games if game["game_id"] in by_game],
    )


async def build_line_only_props(db: AsyncSession, game_id: int) -> NflLineOnlyPropsResponse | None:
    game = await nfl_repo.get_game(db, game_id)
    if game is None:
        return None
    lines = await nfl_repo.get_line_only_lines(db, game_id)
    player_ids = sorted({line["player_id"] for line in lines})
    recent_rows = await nfl_repo.get_recent_stat_rows(db, player_ids, game["season"], game["week"]) if player_ids else []
    return line_only_props(game_id, lines, recent_rows)


def line_only_props(game_id: int, lines: list[dict], recent_rows: list[dict]) -> NflLineOnlyPropsResponse:
    rows_by_player: dict[int, list[dict]] = defaultdict(list)
    for row in recent_rows:
        rows_by_player[row["player_id"]].append(row)
    ordered = sorted(lines, key=lambda line: (_MARKET_ORDER[line["market"]], line["player_name"], line["line"]))
    return NflLineOnlyPropsResponse(
        game_id=game_id,
        lines=[
            NflLineOnlyLineSchema(
                **line,
                recent=[
                    NflLineOnlyRecentSchema(
                        season=row["season"], week=row["week"], opponent=row["opponent"],
                        value=line_only_value(NflLineOnlyMarket(line["market"]), row),
                    )
                    for row in rows_by_player[line["player_id"]]
                ],
            )
            for line in ordered
        ],
    )
