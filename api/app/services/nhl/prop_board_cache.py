"""A shared cache for the `/nhl/props` board body.

Every request rebuilt the whole date: about 0.3 s warm and 1.05 s cold for a
1.1 MB body (2026-11-04, local). Builds run one at a time and only the
serialized body is kept, as the NBA board does.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.nhl import NhlPropBoardResponse
from app.services.nhl.prop_board import build_prop_board
from app.services.serial_build_cache import SerialBuildCache

CACHE_TTL_SECONDS = 5 * 60
FAILURE_TTL_SECONDS = 10
MAX_ENTRIES = 5

_BOARDS: SerialBuildCache[bytes] = SerialBuildCache(CACHE_TTL_SECONDS, FAILURE_TTL_SECONDS, MAX_ENTRIES)


def board_json(board: NhlPropBoardResponse) -> bytes:
    """The body FastAPI would send for `board` under its camelCase response model."""
    return board.model_dump_json(by_alias=True).encode()


async def cached_prop_board_json(db: AsyncSession, requested: dt.date | None, today: dt.date) -> Optional[bytes]:
    """The board as JSON, or None when its build failed.

    Keyed with `today` because the default date is resolved from it.
    """

    async def build() -> bytes:
        clock = dt.datetime.now(dt.timezone.utc)
        return board_json(await build_prop_board(db, requested, today, as_of=clock))

    return await _BOARDS.get((requested, today), build)
