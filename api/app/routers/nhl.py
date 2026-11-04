from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.pool import get_db
from app.schemas.nhl import (
    NhlGameDetailResponse, NhlLineOnlyPropsResponse, NhlPlayerPropsResponse, NhlPropBoardResponse, NhlSlateResponse,
)
from app.services.nhl.game_detail import build_game_detail
from app.services.nhl.line_only_props import build_line_only_props
from app.services.nhl.player_props import build_player_props
from app.services.nhl.prop_board import build_prop_board
from app.services.nhl.slate import build_slate

router = APIRouter()
EASTERN = ZoneInfo("America/New_York")


@router.get("/slate", response_model=NhlSlateResponse)
async def get_slate(date: dt.date | None = None, db: AsyncSession = Depends(get_db)) -> NhlSlateResponse:
    clock = dt.datetime.now(dt.timezone.utc)
    return await build_slate(db, date, clock.astimezone(EASTERN).date(), as_of=clock)


@router.get("/props", response_model=NhlPropBoardResponse)
async def get_prop_board(date: dt.date | None = None, db: AsyncSession = Depends(get_db)) -> NhlPropBoardResponse:
    clock = dt.datetime.now(dt.timezone.utc)
    return await build_prop_board(db, date, clock.astimezone(EASTERN).date(), as_of=clock)


@router.get("/games/{game_id}", response_model=NhlGameDetailResponse)
async def get_game(game_id: int, db: AsyncSession = Depends(get_db)) -> NhlGameDetailResponse:
    detail = await build_game_detail(db, game_id, as_of=dt.datetime.now(dt.timezone.utc))
    if detail is None:
        raise HTTPException(status_code=404, detail=f"NHL game {game_id} not found")
    return detail


@router.get("/games/{game_id}/line-only-props", response_model=NhlLineOnlyPropsResponse)
async def get_game_line_only_props(game_id: int, db: AsyncSession = Depends(get_db)) -> NhlLineOnlyPropsResponse:
    props = await build_line_only_props(db, game_id, as_of=dt.datetime.now(dt.timezone.utc))
    if props is None:
        raise HTTPException(status_code=404, detail=f"NHL game {game_id} not found")
    return props


@router.get("/players/{player_id}/props", response_model=NhlPlayerPropsResponse)
async def get_player_props(
    player_id: int, date: dt.date | None = None, db: AsyncSession = Depends(get_db),
) -> NhlPlayerPropsResponse:
    clock = dt.datetime.now(dt.timezone.utc)
    props = await build_player_props(db, player_id, date, clock.astimezone(EASTERN).date(), as_of=clock)
    if props is None:
        raise HTTPException(status_code=404, detail=f"NHL player {player_id} not found")
    return props
