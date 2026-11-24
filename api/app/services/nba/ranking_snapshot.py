"""The NBA model page's ranking check, precomputed for the hosted demo.

A live build adds about 100 MB, enough with the NFL page's builds to push the
512 MB demo over its limit (2026-11-08). The daily `nba_ranking_snapshot` CLI
stores the response; `/nba/model/ranking` serves that copy, and only dev builds
it live.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.report_snapshot_source import ReportSource, report_source
from app.repositories import report_snapshots
from app.repositories.report_snapshots import JsonObject
from app.schemas.nba import NbaModelRankingResponse
from app.services.nba import track_record

RANKING_REPORT = "nba_model_ranking"


async def build_ranking_response(db: AsyncSession, season: int) -> NbaModelRankingResponse:
    """The live build, bypassing the page cache so the stored copy is current."""
    calls = await track_record.load_ranking_calls(db, season)
    return NbaModelRankingResponse.model_validate(track_record.build_ranking_record(calls, season, datetime.now(UTC)))


def to_payload(response: NbaModelRankingResponse) -> JsonObject:
    return response.model_dump(mode="json")


async def get_ranking_response(db: AsyncSession, season: int, production: bool) -> NbaModelRankingResponse | None:
    """The stored copy, a live build in dev, or None when neither may be served."""
    snapshot = await report_snapshots.get_snapshot(db, RANKING_REPORT, season)
    source = report_source(snapshot is not None, production)
    if source is ReportSource.SNAPSHOT and snapshot is not None:
        return NbaModelRankingResponse.model_validate(snapshot.payload)
    if source is ReportSource.UNAVAILABLE:
        return None
    record = await track_record.get_ranking_record(db, season)
    return None if record is None else NbaModelRankingResponse.model_validate(record)
