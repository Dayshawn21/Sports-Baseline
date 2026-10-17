"""The NFL model page's 27a line grading, precomputed for the hosted demo (37d).

The weekly `nfl_model_snapshot` CLI stores the response the page would build;
`/nfl/model/prop-lines` serves that copy, and only dev replays it live.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.report_snapshot_source import ReportSource, report_source
from app.repositories import report_snapshots
from app.repositories.report_snapshots import JsonObject
from app.schemas.nfl import NflModelPropLinesResponse
from app.services.nfl import track_record

PROP_LINES_REPORT = "nfl_line_grading"


async def build_prop_lines_response(db: AsyncSession, season: int) -> NflModelPropLinesResponse:
    """The live replay, bypassing the page cache so the stored copy is current."""
    inputs = await track_record.load_line_grading(db, season)
    record = track_record.build_line_record(inputs, season, datetime.now(UTC))
    return NflModelPropLinesResponse.model_validate(record)


def to_payload(response: NflModelPropLinesResponse) -> JsonObject:
    return response.model_dump(mode="json")


async def get_prop_lines_response(
    db: AsyncSession, season: int, production: bool,
) -> NflModelPropLinesResponse | None:
    """The stored copy, a live replay in dev, or None when neither may be served."""
    snapshot = await report_snapshots.get_snapshot(db, PROP_LINES_REPORT, season)
    source = report_source(snapshot is not None, production)
    if source is ReportSource.SNAPSHOT and snapshot is not None:
        return NflModelPropLinesResponse.model_validate(snapshot.payload)
    if source is ReportSource.UNAVAILABLE:
        return None
    record = await track_record.get_line_record(db, season)
    return None if record is None else NflModelPropLinesResponse.model_validate(record)
