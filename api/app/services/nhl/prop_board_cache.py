"""A shared cache for the `/nhl/props` board body.

Every request rebuilt the whole date: about 0.3 s warm and 1.05 s cold for a
1.1 MB body (2026-11-04, local). Builds run one at a time and only the
serialized body is kept, as the NBA board does.

Keyed by resolved date and served stale while rebuilding, as the NBA board
cache is (F-43, F-44), so the build opens its own session.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.slate_dates import slate_date
from app.db.pool import SessionLocal
from app.repositories import nhl
from app.schemas.nhl import NhlPropBoardResponse
from app.services.nhl.prop_board import build_prop_board
from app.services.serial_build_cache import SerialBuildCache

CACHE_TTL_SECONDS = 5 * 60
FAILURE_TTL_SECONDS = 10
MAX_ENTRIES = 5
MAX_STALE_SECONDS = 30 * 60

_BOARDS: SerialBuildCache[bytes] = SerialBuildCache(
    CACHE_TTL_SECONDS, FAILURE_TTL_SECONDS, MAX_ENTRIES, max_stale_seconds=MAX_STALE_SECONDS,
)
_DEFAULT_DATES: SerialBuildCache[dt.date] = SerialBuildCache(CACHE_TTL_SECONDS, FAILURE_TTL_SECONDS, MAX_ENTRIES)


def board_json(board: NhlPropBoardResponse) -> bytes:
    """The body FastAPI would send for `board` under its camelCase response model."""
    return board.model_dump_json(by_alias=True).encode()


async def board_date(db: AsyncSession, requested: dt.date | None, today: dt.date) -> Optional[dt.date]:
    """The date the board will show, or None when the game dates could not be read."""
    if requested is not None:
        return requested

    async def resolve() -> dt.date:
        return slate_date(None, today, await nhl.get_game_dates(db))

    return await _DEFAULT_DATES.get(today, resolve)


async def cached_prop_board_json(db: AsyncSession, requested: dt.date | None, today: dt.date) -> Optional[bytes]:
    """The board as JSON, or None when its date or build failed.

    `db` only resolves the default date; the build may outlive the request.
    """
    date = await board_date(db, requested, today)
    if date is None:
        return None

    async def build() -> bytes:
        clock = dt.datetime.now(dt.timezone.utc)
        async with SessionLocal() as session:
            return board_json(await build_prop_board(session, date, today, as_of=clock))

    return await _BOARDS.get((date, today), build)
