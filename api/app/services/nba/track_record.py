"""The NBA model track record (20g4): the forward ranking check the CLI prints and `/nba/model` serves."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import nba_over_probability_fit as fit
from app.core.nba_projection_backtest import NBA_PROJECTION_MODEL_VERSION
from app.repositories import nba as nba_repo
from app.services import prop_ranking
from app.services.prop_ranking import RankingCalls, RankingRecord
from app.services.sport_registry import prop_source
from app.services.tennis.live_odds_cache import TimedSingleFlight

CACHE_TTL_SECONDS = 15 * 60


async def nba_season(db: AsyncSession, now: datetime) -> int | None:
    """The season of the next regular-season game, else the latest loaded; None with no `REG` game at all."""
    current = await nba_repo.get_current_week(db, now)
    return current[0] if current is not None else None


async def load_ranking_calls(db: AsyncSession, season: int) -> RankingCalls:
    """Each provider prop's latest frozen pre-tip row as a settled call, or the reason it is not one."""
    return await prop_ranking.load_ranking_calls(db, prop_source("nba"), season)


def build_ranking_record(inputs: RankingCalls, season: int, graded_at: datetime) -> RankingRecord:
    return prop_ranking.build_ranking_record(
        inputs, season, graded_at, NBA_PROJECTION_MODEL_VERSION, fit.OVER_PROBABILITY_VERSION,
    )


_RANKING: TimedSingleFlight[RankingRecord] = TimedSingleFlight(CACHE_TTL_SECONDS)


async def get_ranking_record(db: AsyncSession, season: int) -> RankingRecord | None:
    """None when grading failed; the failure is shared for the cache window too."""
    async def fetch() -> RankingRecord:
        return build_ranking_record(await load_ranking_calls(db, season), season, datetime.now(UTC))

    return await _RANKING.get(season, fetch)
