"""Retry a write transaction that Postgres aborted for a concurrency conflict.

Ingest jobs upsert into `players` in whatever order the provider returned them. Two jobs
running at once therefore take row locks in different orders and can deadlock, at which
point Postgres kills one of them. That is not a bug in either job and there is nothing to
fix in the data: the loser simply has to run its transaction again.

It happens in practice. The hourly cron in tennis-ingest.yml overlaps with any manual run,
and a backfill sharing the table with the daily ingest deadlocked on exactly this.

A deadlock aborts the whole transaction, so the retry has to open a fresh session and redo
the work. That is safe here because every ingest write is an idempotent upsert keyed on
match_key or name_norm: replaying a window rewrites the same rows.
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Awaitable, Callable, TypeVar

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.pool import SessionLocal

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Postgres class 40: transaction rollback. Both are the server telling us to try again.
#   40P01 deadlock_detected
#   40001 serialization_failure
_RETRYABLE_SQLSTATES = frozenset({"40P01", "40001"})

DEFAULT_ATTEMPTS = 4
_BASE_DELAY_SECONDS = 0.5


def is_retryable_conflict(exc: BaseException) -> bool:
    """True when Postgres aborted the transaction and re-running it may succeed."""
    sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
    return sqlstate in _RETRYABLE_SQLSTATES


async def run_in_session_with_retry(
    work: Callable[[AsyncSession], Awaitable[T]],
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    description: str = "transaction",
) -> T:
    """Run `work` in a fresh session, retrying on deadlock or serialization failure.

    `work` must be safe to run more than once, and must not hold state from a previous
    attempt: it is handed a new session each time.
    """
    for attempt in range(1, attempts + 1):
        try:
            async with SessionLocal() as db:
                return await work(db)
        except DBAPIError as exc:
            if not is_retryable_conflict(exc) or attempt == attempts:
                raise
            # Full jitter, so two jobs that collided do not retry in lockstep and
            # deadlock again on the same rows.
            delay = random.uniform(0, _BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
            logger.warning(
                "%s hit %s (attempt %d/%d), retrying in %.2fs",
                description,
                getattr(getattr(exc, "orig", None), "sqlstate", "?"),
                attempt,
                attempts,
                delay,
            )
            await asyncio.sleep(delay)

    raise AssertionError("unreachable: loop either returns or raises")
