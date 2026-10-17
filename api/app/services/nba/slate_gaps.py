"""The NBA slate digest (38c2): one date's largest reference-projection gaps.

Lines are projected through the game page's own `props_response`, so a digest
box never disagrees with the game it opens.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_projection_backtest import NBA_PROJECTION_MODEL_VERSION, NbaHistoryRow
from app.core.nba_slate_gaps import GapCandidate, rank_slate_gaps
from app.repositories import nba as nba_repo
from app.schemas.nba import NbaSlateGapSchema, NbaSlateGapsResponse
from app.services.nba.props import props_response


async def build_slate_gaps(db: AsyncSession, date: dt.date, now: dt.datetime) -> NbaSlateGapsResponse:
    games = [game for game in await nba_repo.get_games_on(db, date) if _not_tipped(game, now)]
    lines_by_game = {int(str(game["game_id"])): await nba_repo.get_modelled_lines(db, int(str(game["game_id"]))) for game in games}
    player_ids = sorted({int(str(line["player_id"])) for lines in lines_by_game.values() for line in lines})
    # One date, so one pre-tip cutoff serves every game's players.
    prior = await nba_repo.get_prior_games(db, player_ids, date) if player_ids else {}
    return slate_gaps_response(date, games, lines_by_game, prior, now)


def _not_tipped(game: Mapping[str, object], now: dt.datetime) -> bool:
    start = game["start_utc"]
    return game["status"] == "scheduled" and isinstance(start, dt.datetime) and start > now


def slate_gaps_response(
    date: dt.date,
    games: Sequence[Mapping[str, object]],
    lines_by_game: Mapping[int, Sequence[Mapping[str, object]]],
    prior_by_player: Mapping[int, Sequence[NbaHistoryRow]],
    now: dt.datetime,
) -> NbaSlateGapsResponse:
    by_id = {int(str(game["game_id"])): game for game in games}
    candidates = [
        GapCandidate(
            game_id=game_id, start_utc=cast(dt.datetime | None, by_id[game_id]["start_utc"]),
            status=str(by_id[game_id]["status"]), player_id=line.player_id, player_name=line.player_name,
            market=line.market, odds_type=line.odds_type, line=line.line, projection=line.projection, gap=line.gap,
        )
        for game_id, lines in lines_by_game.items() if game_id in by_id
        for line in props_response(game_id, lines, prior_by_player, []).lines
    ]
    items = [
        NbaSlateGapSchema(
            game_id=item.candidate.game_id, away_team=str(by_id[item.candidate.game_id]["away_team"]),
            home_team=str(by_id[item.candidate.game_id]["home_team"]), player_id=item.candidate.player_id,
            player_name=item.candidate.player_name, market=item.candidate.market, line=item.candidate.line,
            projection=cast(float, item.candidate.projection), gap=cast(float, item.candidate.gap),
            gap_share=item.gap_share,
        )
        for item in rank_slate_gaps(candidates, now)
    ]
    return NbaSlateGapsResponse(date=date, model_version=NBA_PROJECTION_MODEL_VERSION, items=items)
