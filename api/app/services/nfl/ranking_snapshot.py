"""The NFL model page's ranking checks, precomputed for the hosted demo.

A live v4 ranking build adds about 90 MB, and the page asks for all three
versions at once, which pushed the 512 MB demo over its limit (2026-11-08).
The weekly `nfl_ranking_snapshot` CLI stores each version's response;
`/nfl/model/ranking` serves that copy, and only dev builds it live.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import get_args

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_volume_projection import NFL_VOLUME_MODEL_VERSION
from app.core.report_snapshot_source import ReportSource, report_source
from app.repositories import report_snapshots
from app.repositories.report_snapshots import JsonObject
from app.schemas.nfl import NflLogLossSchema, NflModelRankingResponse, NflRankingModelVersion
from app.services.nfl import track_record, volume_ranking
from app.services.nfl.volume_ranking import VolumeRankingRecord
from app.services.prop_ranking import RankingRecord

RANKING_MODEL_VERSIONS: tuple[str, ...] = get_args(NflRankingModelVersion)


def ranking_report(model_version: str) -> str:
    """`report_snapshots` is keyed by report and season, so the version is in the name."""
    return f"nfl_model_ranking_{model_version}"


def volume_response(volume: VolumeRankingRecord) -> NflModelRankingResponse:
    response = NflModelRankingResponse.model_validate(volume.record)
    response.log_loss = NflLogLossSchema.model_validate({"progress": volume.log_loss_progress, "slices": volume.states})
    return response


def _response(record: RankingRecord | VolumeRankingRecord) -> NflModelRankingResponse:
    if isinstance(record, VolumeRankingRecord):
        return volume_response(record)
    return NflModelRankingResponse.model_validate(record)


async def build_ranking_response(db: AsyncSession, season: int, model_version: str) -> NflModelRankingResponse:
    """The live build, bypassing the page cache so the stored copy is current."""
    now = datetime.now(UTC)
    if model_version == NFL_VOLUME_MODEL_VERSION:
        inputs = await volume_ranking.load_volume_inputs(db, season)
        return volume_response(volume_ranking.build_volume_record(inputs, season, now))
    calls = await track_record.load_ranking_calls(db, season, model_version)
    return _response(track_record.build_ranking_record(calls, season, now, model_version))


def to_payload(response: NflModelRankingResponse) -> JsonObject:
    return response.model_dump(mode="json")


async def _cached_live_response(db: AsyncSession, season: int, model_version: str) -> NflModelRankingResponse | None:
    if model_version == NFL_VOLUME_MODEL_VERSION:
        volume = await volume_ranking.get_volume_record(db, season)
        return None if volume is None else volume_response(volume)
    record = await track_record.get_ranking_record(db, season, model_version)
    return None if record is None else _response(record)


async def get_ranking_response(
    db: AsyncSession, season: int, model_version: str, production: bool,
) -> NflModelRankingResponse | None:
    """The stored copy, a live build in dev, or None when neither may be served."""
    snapshot = await report_snapshots.get_snapshot(db, ranking_report(model_version), season)
    source = report_source(snapshot is not None, production)
    if source is ReportSource.SNAPSHOT and snapshot is not None:
        return NflModelRankingResponse.model_validate(snapshot.payload)
    if source is ReportSource.UNAVAILABLE:
        return None
    return await _cached_live_response(db, season, model_version)
