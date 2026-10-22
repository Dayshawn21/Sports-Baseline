from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.nfl_projection import NFL_PROJECTION_MODEL_VERSION, NflHistoricalAverages, baseline_projection, quality_flags
from app.core.production_settings import is_production
from app.db.pool import get_db
from app.nfl.markets import NFL_V4_PROP_MARKETS, NflPropMarket
from app.repositories import nfl as nfl_repo
from app.schemas.nfl import (
    NflCurrentWeekResponse, NflGameContextResponse, NflGameDetailResponse, NflGameNotesResponse, NflGameSchema, NflGamesResponse,
    NflLineOnlyPropsResponse, NflLineOnlyBoardResponse,
    NflModelClvResponse, NflModelFitResponse, NflModelPropLinesResponse, NflModelRankingResponse,
    NflPlayerDetailResponse, NflProjectionSchema, NflProjectionsResponse, NflPropLineSchema, NflProspectsResponse,
    NflRankingModelVersion, NflSlateResponse,
)
from app.services.nfl.game_detail import build_game_detail
from app.services.nfl.game_notes import build_game_notes
from app.services.nfl.line_only_props import build_line_only_props, build_week_line_only_props
from app.services.nfl.matchup_context import build_game_context
from app.services.nfl.player_detail import build_player_detail
from app.services.nfl import prop_lines_snapshot, track_record
from app.services.nfl.slate import anytime_td
from app.services.nfl.slate_cache import cached_slate_json

router = APIRouter()

@router.get("/current-week", response_model=NflCurrentWeekResponse)
async def get_current_week(db: AsyncSession = Depends(get_db)) -> NflCurrentWeekResponse:
    current = await nfl_repo.get_current_week(db, datetime.now(UTC))
    if current is None:
        raise HTTPException(status_code=404, detail="No NFL regular-season games are loaded")
    season, week = current
    return NflCurrentWeekResponse(season=season, week=week)


@router.get("/games", response_model=NflGamesResponse)
async def get_games(
    season: int,
    week: int,
    db: AsyncSession = Depends(get_db),
) -> NflGamesResponse:
    games = await nfl_repo.get_games(db, season, week)
    return NflGamesResponse(season=season, week=week, count=len(games), games=[NflGameSchema(**game) for game in games])


@router.get("/games/{game_id}", response_model=NflGameDetailResponse)
async def get_game(game_id: int, db: AsyncSession = Depends(get_db)) -> NflGameDetailResponse:
    detail = await build_game_detail(db, game_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"NFL game {game_id} not found")
    return detail


@router.get("/games/{game_id}/line-only-props", response_model=NflLineOnlyPropsResponse)
async def get_game_line_only_props(game_id: int, db: AsyncSession = Depends(get_db)) -> NflLineOnlyPropsResponse:
    props = await build_line_only_props(db, game_id)
    if props is None:
        raise HTTPException(status_code=404, detail=f"NFL game {game_id} not found")
    return props


@router.get("/games/{game_id}/context", response_model=NflGameContextResponse)
async def get_game_context(game_id: int, db: AsyncSession = Depends(get_db)) -> NflGameContextResponse:
    context = await build_game_context(db, game_id)
    if context is None:
        raise HTTPException(status_code=404, detail=f"NFL game {game_id} not found")
    return context


@router.get("/line-only-props", response_model=NflLineOnlyBoardResponse)
async def get_week_line_only_props(
    season: int, week: int, db: AsyncSession = Depends(get_db),
) -> NflLineOnlyBoardResponse:
    return await build_week_line_only_props(db, season, week)


@router.get("/players/{player_id}", response_model=NflPlayerDetailResponse)
async def get_player(player_id: int, db: AsyncSession = Depends(get_db)) -> NflPlayerDetailResponse:
    detail = await build_player_detail(db, player_id, datetime.now(UTC))
    if detail is None:
        raise HTTPException(status_code=404, detail=f"NFL player {player_id} not found")
    return detail


@router.get("/projections", response_model=NflProjectionsResponse)
async def get_projections(
    season: int,
    week: int,
    db: AsyncSession = Depends(get_db),
) -> NflProjectionsResponse:
    rows = await nfl_repo.get_historical_player_baselines(db, season, week)
    projections: list[NflProjectionSchema] = []
    for row in rows:
        averages = NflHistoricalAverages(**row["averages"])
        flags = quality_flags(averages)
        confidence = "LEAN" if averages.games >= 8 else "PASS"
        for market in NFL_V4_PROP_MARKETS:
            projections.append(NflProjectionSchema(
                game_id=row["game_id"], player_id=row["player_id"], player_name=row["player_name"],
                position=row["position"], market=market.value,
                projection=_projection_value(market, row, season, averages), games_in_sample=averages.games,
                confidence=confidence, quality_flags=flags,
            ))
    return NflProjectionsResponse(season=season, week=week, count=len(projections), projections=projections)


def _projection_value(market: NflPropMarket, row: dict, season: int, averages: NflHistoricalAverages) -> float:
    if market is not NflPropMarket.ANYTIME_TOUCHDOWN:
        return baseline_projection(market, averages)
    return anytime_td(row, season, row.get("position_td_rate", 0.0))[0]


@router.get("/prospects", response_model=NflProspectsResponse)
async def get_prospects(db: AsyncSession = Depends(get_db)) -> NflProspectsResponse:
    lines = await nfl_repo.get_latest_prop_lines(db)
    return NflProspectsResponse(count=len(lines), lines=[NflPropLineSchema(**line) for line in lines])


@router.get("/slate", response_model=NflSlateResponse)
async def get_slate(
    season: int,
    week: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    body = await cached_slate_json(db, season, week, is_production(settings.api_env))
    if body is None:
        raise HTTPException(status_code=503, detail="The NFL slate is unavailable; try again shortly")
    return Response(content=body, media_type="application/json")


@router.get("/game-notes", response_model=NflGameNotesResponse)
async def get_game_notes(
    season: int,
    week: int,
    db: AsyncSession = Depends(get_db),
) -> NflGameNotesResponse:
    return await build_game_notes(db, season, week)


@router.get("/model/ranking", response_model=NflModelRankingResponse)
async def get_model_ranking(
    season: int,
    model_version: NflRankingModelVersion = NFL_PROJECTION_MODEL_VERSION,
    db: AsyncSession = Depends(get_db),
) -> NflModelRankingResponse:
    record = await track_record.get_ranking_record(db, season, model_version)
    if record is None:
        raise HTTPException(status_code=503, detail="The ranking check is unavailable; try again shortly")
    return NflModelRankingResponse.model_validate(record)


@router.get("/model/game-line-clv", response_model=NflModelClvResponse)
async def get_model_game_line_clv(season: int, db: AsyncSession = Depends(get_db)) -> NflModelClvResponse:
    record = await track_record.get_clv_record(db, season)
    if record is None:
        raise HTTPException(status_code=503, detail="Game-line CLV is unavailable; try again shortly")
    return NflModelClvResponse.model_validate(record)


@router.get("/model/prop-lines", response_model=NflModelPropLinesResponse)
async def get_model_prop_lines(season: int, db: AsyncSession = Depends(get_db)) -> NflModelPropLinesResponse:
    response = await prop_lines_snapshot.get_prop_lines_response(db, season, is_production(settings.api_env))
    if response is None:
        raise HTTPException(
            status_code=503,
            detail="PrizePicks line grading is computed weekly and is not available yet; try again later",
        )
    return response


@router.get("/model/over-probability-fit", response_model=NflModelFitResponse)
async def get_model_over_probability_fit() -> NflModelFitResponse:
    return NflModelFitResponse.model_validate(track_record.get_fit_record())
