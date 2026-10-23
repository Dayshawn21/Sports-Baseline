"""A shared cache for the `/nba/props` board body.

Every request rebuilt the whole date: about 1.7 s warm, a 6.5 MB body, and a
peak about 90 MB above the idle process per build (2026-10-23, local). Builds
run one at a time and only the serialized body is kept, as `/nfl/slate` does.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.nba import NbaPropBoardResponse
from app.services.nba.prop_board import build_prop_board
from app.services.serial_build_cache import SerialBuildCache

# Matches the web's 5-minute staleTime for NBA data.
CACHE_TTL_SECONDS = 5 * 60
FAILURE_TTL_SECONDS = 10
# The default date plus a few neighbours, about 32 MB at today's body size.
MAX_ENTRIES = 5

_BOARDS: SerialBuildCache[bytes] = SerialBuildCache(CACHE_TTL_SECONDS, FAILURE_TTL_SECONDS, MAX_ENTRIES)


def board_json(board: NbaPropBoardResponse) -> bytes:
    """The body FastAPI would send for `board` under its camelCase response model."""
    return board.model_dump_json(by_alias=True).encode()


async def cached_prop_board_json(db: AsyncSession, requested: dt.date | None, today: dt.date) -> Optional[bytes]:
    """The board as JSON, or None when its build failed.

    Keyed with `today` because the default date is resolved from it.
    """

    async def build() -> bytes:
        return board_json(await build_prop_board(db, requested, today))

    return await _BOARDS.get((requested, today), build)
