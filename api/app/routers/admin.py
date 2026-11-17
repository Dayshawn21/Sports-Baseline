"""
Admin router — data quality management.

Endpoints let the admin fix missing player data (ELO, rolling stats) that
surfaces as quality flags on the TennisPage predictions.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.pool import get_db
from app.repositories.players import (
    get_latest_elo,
    get_player_by_id,
    get_rolling_stats,
    update_ta_slug,
    upsert_elo,
)
from app.schemas.admin import (
    AdminSessionResponse,
    FetchEloRequest,
    FetchEloResponse,
    FetchStatsRequest,
    FetchStatsResponse,
    FlaggedPlayer,
    FlaggedPlayersResponse,
    SetEloRequest,
    SetEloResponse,
)
from app.services.tennis.flagged_players import load_flagged_players

router = APIRouter()


@router.get("/session", response_model=AdminSessionResponse)
async def get_session() -> AdminSessionResponse:
    """Reached only past the router's key guard, so a 200 means the caller may use admin routes."""
    return AdminSessionResponse(key_required=bool((settings.admin_api_key or "").strip()))


@router.get("/players/flagged", response_model=FlaggedPlayersResponse)
async def get_flagged_players(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Return all players from today's (and tomorrow's) matches that have
    ELO or rolling-stats quality flags.
    """
    rows = await load_flagged_players(db, request.app.state.registry, date.today())
    return FlaggedPlayersResponse(
        count=len(rows),
        players=[FlaggedPlayer(**asdict(row)) for row in rows],
    )


@router.post("/players/{player_id}/fetch-stats", response_model=FetchStatsResponse)
async def fetch_player_stats(
    player_id: int,
    body: FetchStatsRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger a TennisAbstract stats fetch for a single player.
    If `ta_slug` is provided in the body, it is saved to the DB first
    (persists for future ingests) then used for this fetch.
    """
    from app.ingest.player_stats import ingest_single_player

    player = await get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    # Save new slug to DB if provided
    if body.ta_slug is not None and body.ta_slug.strip():
        await update_ta_slug(db, player_id, body.ta_slug.strip())
        await db.commit()
        effective_slug: Optional[str] = body.ta_slug.strip()
    else:
        # Fall back to whatever is already stored on the player record
        effective_slug = player.ta_slug  # may be None → _slug(name) will be used

    result = await ingest_single_player(
        db=db,
        player_id=player_id,
        player_name=player.name,
        tour=player.tour,
        ta_slug_override=effective_slug,
        commit=True,
    )

    return FetchStatsResponse(**result)


@router.post("/players/{player_id}/fetch-elo", response_model=FetchEloResponse)
async def fetch_player_elo(
    player_id: int,
    body: FetchEloRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Scrape TennisAbstract's ELO ratings page and find this player by name.
    Use ta_name to provide the correct spelling if TennisAbstract uses a different
    form than what's stored in our DB (e.g. hyphenation, accents, abbreviations).
    """
    from app.ingest.elo import fetch_single_player_elo

    player = await get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    result = await fetch_single_player_elo(
        db=db,
        player_id=player_id,
        player_name=player.name,
        tour=player.tour,
        ta_name_override=body.ta_name,
    )

    return FetchEloResponse(**result)


@router.post("/players/{player_id}/set-elo", response_model=SetEloResponse)
async def set_player_elo(
    player_id: int,
    body: SetEloRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually set ELO values for a player.
    Useful for qualifiers and lower-ranked players not in TennisAbstract's ratings table.
    """
    player = await get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    await upsert_elo(
        db,
        player_id=player_id,
        as_of=date.today(),
        elo=body.elo,
        elo_hard=body.elo_hard,
        elo_clay=body.elo_clay,
        elo_grass=body.elo_grass,
        source="admin",
    )
    await db.commit()

    return SetEloResponse(
        success=True,
        player_id=player_id,
        player_name=player.name,
    )
