"""The NHL model page's ranking check, precomputed for the hosted demo.

A live build took 8.3 s cold on the 0.5 CPU host and 14 s beside the home
page's other builds (2026-11-22), grading a season that grows every week. The
daily `nhl_ranking_snapshot` CLI stores the response; `/nhl/model/ranking`
serves that copy, and only dev builds it live.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.report_snapshot_source import ReportSource, report_source
from app.repositories import report_snapshots
from app.repositories.report_snapshots import JsonObject
from app.schemas.nhl import NhlModelRankingResponse
from app.services.nhl import track_record

RANKING_REPORT = "nhl_model_ranking"


async def build_ranking_response(db: AsyncSession, season: int) -> NhlModelRankingResponse:
    """The live build, bypassing the page cache so the stored copy is current."""
    calls = await track_record.load_ranking_calls(db, season)
    return NhlModelRankingResponse.model_validate(track_record.build_ranking_record(calls, season, datetime.now(UTC)))


def to_payload(response: NhlModelRankingResponse) -> JsonObject:
    return response.model_dump(mode="json")


async def get_ranking_response(db: AsyncSession, season: int, production: bool) -> NhlModelRankingResponse | None:
    """The stored copy, a live build in dev, or None when neither may be served."""
    snapshot = await report_snapshots.get_snapshot(db, RANKING_REPORT, season)
    source = report_source(snapshot is not None, production)
    if source is ReportSource.SNAPSHOT and snapshot is not None:
        return NhlModelRankingResponse.model_validate(snapshot.payload)
    if source is ReportSource.UNAVAILABLE:
        return None
    record = await track_record.get_ranking_record(db, season)
    return None if record is None else NhlModelRankingResponse.model_validate(record)
