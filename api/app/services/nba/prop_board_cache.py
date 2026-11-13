"""A shared cache for the `/nba/props` board body.

Every request rebuilt the whole date: about 1.7 s warm, a 6.5 MB body, and a
peak about 90 MB above the idle process per build (2026-10-23, local). Builds
run one at a time and only the serialized body is kept, as `/nfl/slate` does.

Boards are keyed by their resolved date, so the default request and the same
date asked for explicitly share one build (F-43). An expired board is served
for up to 30 minutes while one background task rebuilds it (F-44), so the
build opens its own session rather than borrowing the request's.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_slate import slate_date
from app.db.pool import SessionLocal
from app.repositories import nba as nba_repo
from app.schemas.nba import NbaPropBoardResponse
from app.services.nba.prop_board import build_prop_board
from app.services.serial_build_cache import SerialBuildCache

# Matches the web's 5-minute staleTime for NBA data.
CACHE_TTL_SECONDS = 5 * 60
FAILURE_TTL_SECONDS = 10
# The default date plus a few neighbours, about 32 MB at today's body size.
MAX_ENTRIES = 5
MAX_STALE_SECONDS = 30 * 60

_BOARDS: SerialBuildCache[bytes] = SerialBuildCache(
    CACHE_TTL_SECONDS, FAILURE_TTL_SECONDS, MAX_ENTRIES, max_stale_seconds=MAX_STALE_SECONDS,
)
# The default board date for each `today`, so a warm default request costs no read.
_DEFAULT_DATES: SerialBuildCache[dt.date] = SerialBuildCache(CACHE_TTL_SECONDS, FAILURE_TTL_SECONDS, MAX_ENTRIES)


def board_json(board: NbaPropBoardResponse) -> bytes:
    """The body FastAPI would send for `board` under its camelCase response model."""
    return board.model_dump_json(by_alias=True).encode()


async def board_date(db: AsyncSession, requested: dt.date | None, today: dt.date) -> Optional[dt.date]:
    """The date the board will show, or None when the game dates could not be read."""
    if requested is not None:
        return requested

    async def resolve() -> dt.date:
        return slate_date(None, today, await nba_repo.get_game_dates(db))

    return await _DEFAULT_DATES.get(today, resolve)


async def cached_prop_board_json(db: AsyncSession, requested: dt.date | None, today: dt.date) -> Optional[bytes]:
    """The board as JSON, or None when its date or build failed.

    `db` only resolves the default date; the build may outlive the request.
    """
    date = await board_date(db, requested, today)
    if date is None:
        return None

    async def build() -> bytes:
        async with SessionLocal() as session:
            return board_json(await build_prop_board(session, date, today))

    return await _BOARDS.get((date, today), build)
