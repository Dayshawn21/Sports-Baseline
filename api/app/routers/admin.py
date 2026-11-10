"""
Admin router — data quality management.

Endpoints let the admin fix missing player data (ELO, rolling stats) that
surfaces as quality flags on the TennisPage predictions.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.tennis_flag_queue import ELO_FLAGS, STATS_FLAG, missing_surfaces, refine_player_flags
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

router = APIRouter()

_TARGET_FLAGS = ELO_FLAGS | {STATS_FLAG}


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
    from app.services.tennis.predictor import predict_today
    from app.repositories.matches import get_upcoming
    from app.repositories.players import get_players_by_ids, get_latest_elo_batch, get_rolling_stats_batch_all_surfaces
    from app.ingest.player_stats import _slug

    today = date.today()
    target_dates = [today, today + timedelta(days=1)]

    predictions = await predict_today(db, request.app.state.registry, target_dates)
    matches = await get_upcoming(db, target_dates)
    match_map = {m.id: m for m in matches}

    # Map player_id → set of flags, and the surfaces of the matches flagging them
    flagged: dict[int, set[str]] = {}
    surfaces: dict[int, set[str | None]] = {}

    for pred in predictions:
        m = match_map.get(pred.match_id)
        if not m:
            continue
        active_flags = set(pred.quality_flags) & _TARGET_FLAGS
        if not active_flags:
            continue

        for flag in active_flags:
            if flag == "p1_elo_missing":
                flagged.setdefault(m.p1_id, set()).add(flag)
            elif flag == "p2_elo_missing":
                flagged.setdefault(m.p2_id, set()).add(flag)
            elif flag == "elo_missing":
                # Both players missing ELO
                flagged.setdefault(m.p1_id, set()).add(flag)
                flagged.setdefault(m.p2_id, set()).add(flag)
            elif flag == STATS_FLAG:
                # Attribute to both — will be filtered below to whoever truly lacks stats
                for pid in (m.p1_id, m.p2_id):
                    flagged.setdefault(pid, set()).add(flag)
                    surfaces.setdefault(pid, set()).add(m.surface)

    if not flagged:
        return FlaggedPlayersResponse(count=0, players=[])

    all_ids = list(flagged.keys())
    players_map = await get_players_by_ids(db, all_ids)
    elo_map = await get_latest_elo_batch(db, all_ids)
    # The same lookup the predictor uses, so (pid, None) is the all-surface row
    stats_map = await get_rolling_stats_batch_all_surfaces(db, all_ids, "last_52w")
    stat_surfaces: dict[int, set[str | None]] = {}
    for stat_pid, stat_surface in stats_map:
        stat_surfaces.setdefault(stat_pid, set()).add(stat_surface)

    result: list[FlaggedPlayer] = []
    for pid, flags in flagged.items():
        player = players_map.get(pid)
        if not player:
            continue

        elo = elo_map.get(pid)
        stats = stats_map.get((pid, None))
        has_elo = elo is not None and elo.elo is not None
        refined_flags = refine_player_flags(
            flags,
            has_elo=has_elo,
            stat_surfaces=stat_surfaces.get(pid, set()),
            match_surfaces=surfaces.get(pid, set()),
        )

        if not refined_flags:
            continue

        result.append(FlaggedPlayer(
            player_id=pid,
            player_name=player.name,
            tour=player.tour,
            flags=sorted(refined_flags),
            has_elo=has_elo,
            has_stats=stats is not None,
            missing_surfaces=missing_surfaces(stat_surfaces.get(pid, set()), surfaces.get(pid, set())),
            ta_slug=player.ta_slug,
            auto_slug=_slug(player.name),
        ))

    return FlaggedPlayersResponse(count=len(result), players=result)


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
