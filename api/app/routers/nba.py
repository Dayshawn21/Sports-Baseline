from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.pool import get_db
from app.schemas.nba import (
    NbaGameDetailResponse, NbaLineOnlyPropsResponse, NbaModelRankingResponse, NbaPropsResponse, NbaSlateGapsResponse,
    NbaPropBoardResponse, NbaSlateResponse,
)
from app.services.nba import track_record
from app.services.nba.game_detail import build_game_detail
from app.services.nba.line_only_props import build_line_only_props
from app.services.nba.prop_board_cache import cached_prop_board_json
from app.services.nba.props import build_props
from app.services.nba.slate import build_slate
from app.services.nba.slate_gaps import build_slate_gaps

router = APIRouter()

# NBA game dates are Eastern dates (item 20b), so "today" is too.
EASTERN = ZoneInfo("America/New_York")


@router.get("/slate", response_model=NbaSlateResponse)
async def get_slate(date: dt.date | None = None, db: AsyncSession = Depends(get_db)) -> NbaSlateResponse:
    return await build_slate(db, date, dt.datetime.now(EASTERN).date())


@router.get("/slate/gaps", response_model=NbaSlateGapsResponse)
async def get_slate_gaps(date: dt.date, db: AsyncSession = Depends(get_db)) -> NbaSlateGapsResponse:
    return await build_slate_gaps(db, date, dt.datetime.now(dt.UTC))


@router.get("/props", response_model=NbaPropBoardResponse)
async def get_prop_board(date: dt.date | None = None, db: AsyncSession = Depends(get_db)) -> Response:
    body = await cached_prop_board_json(db, date, dt.datetime.now(EASTERN).date())
    if body is None:
        raise HTTPException(status_code=503, detail="The NBA prop board is unavailable; try again shortly")
    return Response(content=body, media_type="application/json")


@router.get("/games/{game_id}", response_model=NbaGameDetailResponse)
async def get_game(game_id: int, db: AsyncSession = Depends(get_db)) -> NbaGameDetailResponse:
    detail = await build_game_detail(db, game_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"NBA game {game_id} not found")
    return detail


@router.get("/games/{game_id}/line-only-props", response_model=NbaLineOnlyPropsResponse)
async def get_game_line_only_props(game_id: int, db: AsyncSession = Depends(get_db)) -> NbaLineOnlyPropsResponse:
    props = await build_line_only_props(db, game_id)
    if props is None:
        raise HTTPException(status_code=404, detail=f"NBA game {game_id} not found")
    return props


@router.get("/games/{game_id}/props", response_model=NbaPropsResponse)
async def get_game_props(game_id: int, db: AsyncSession = Depends(get_db)) -> NbaPropsResponse:
    props = await build_props(db, game_id)
    if props is None:
        raise HTTPException(status_code=404, detail=f"NBA game {game_id} not found")
    return props


@router.get("/model/ranking", response_model=NbaModelRankingResponse)
async def get_model_ranking(season: int | None = None, db: AsyncSession = Depends(get_db)) -> NbaModelRankingResponse:
    # Resolved before the cache, so the cache is always keyed by a concrete season.
    if season is None:
        season = await track_record.nba_season(db, dt.datetime.now(dt.UTC))
    if season is None:
        raise HTTPException(status_code=404, detail="No NBA regular-season games are loaded")
    record = await track_record.get_ranking_record(db, season)
    if record is None:
        raise HTTPException(status_code=503, detail="The ranking check is unavailable; try again shortly")
    return NbaModelRankingResponse.model_validate(record)
