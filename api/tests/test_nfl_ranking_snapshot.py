"""The precomputed NFL ranking checks: the stored copy is served as built, one
report per model version, production never builds live, and dev still can."""
import asyncio
import json

import pytest

from app.core.nfl_projection import NFL_PROJECTION_MODEL_VERSION as V4
from app.core.nfl_volume_projection import NFL_VOLUME_MODEL_VERSION
from app.ingest.nfl_ranking_snapshot import headline
from app.repositories import report_snapshots
from app.repositories.report_snapshots import StoredSnapshot
from app.schemas.nfl import NflModelRankingResponse
from app.services.nfl import track_record, volume_ranking
from app.services.nfl.ranking_snapshot import (
    RANKING_MODEL_VERSIONS, get_ranking_response, ranking_report, to_payload, volume_response,
)
from app.services.nfl.track_record import build_ranking_record
from tests.helpers.nfl_track_record_service import GRADED_AT, _call, _inputs
from tests.helpers.nfl_volume_ranking_service import _fresh_caches, _passing_sample, _volume  # noqa: F401

TARGETS = "nfl-targets-v1"


def _record(season: int = 2026, model_version: str = V4):
    return build_ranking_record(_inputs([_call(i) for i in range(3)]), season, GRADED_AT, model_version)


def _response(season: int = 2026) -> NflModelRankingResponse:
    return NflModelRankingResponse.model_validate(_record(season))


def test_every_page_version_has_its_own_report():
    assert set(RANKING_MODEL_VERSIONS) == {V4, TARGETS, NFL_VOLUME_MODEL_VERSION}
    assert len({ranking_report(version) for version in RANKING_MODEL_VERSIONS}) == 3


def test_the_stored_payload_rebuilds_the_same_response(monkeypatch):
    for response in (_response(), volume_response(_volume(monkeypatch, _passing_sample()))):
        stored = json.loads(json.dumps(to_payload(response)))

        assert NflModelRankingResponse.model_validate(stored).model_dump(by_alias=True) == response.model_dump(
            by_alias=True
        )


def test_the_volume_payload_keeps_its_log_loss(monkeypatch):
    response = volume_response(_volume(monkeypatch, _passing_sample()))

    assert response.log_loss is not None
    assert NflModelRankingResponse.model_validate(to_payload(response)).log_loss == response.log_loss


def test_headline_names_the_version_and_weeks():
    line = headline(_response())

    assert V4 in line and "2026" in line


@pytest.fixture
def live_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, str]]:
    calls: list[tuple[int, str]] = []

    async def live(_db, season, model_version=V4):
        calls.append((season, model_version))
        return _record(season, model_version)

    async def live_volume(_db, season):
        calls.append((season, NFL_VOLUME_MODEL_VERSION))
        return None

    monkeypatch.setattr(track_record, "get_ranking_record", live)
    monkeypatch.setattr(volume_ranking, "get_volume_record", live_volume)
    return calls


def _stored(monkeypatch: pytest.MonkeyPatch, snapshot: StoredSnapshot | None) -> list[tuple[str, int]]:
    reads: list[tuple[str, int]] = []

    async def get(_db, report, season):
        reads.append((report, season))
        return snapshot

    monkeypatch.setattr(report_snapshots, "get_snapshot", get)
    return reads


def test_a_snapshot_is_served_without_a_live_build(monkeypatch, live_calls):
    response = _response()
    reads = _stored(monkeypatch, StoredSnapshot(to_payload(response), GRADED_AT))

    served = asyncio.run(get_ranking_response(None, 2026, V4, production=True))

    assert served == response
    assert reads == [(ranking_report(V4), 2026)]
    assert live_calls == []


@pytest.mark.parametrize("model_version", [V4, TARGETS, NFL_VOLUME_MODEL_VERSION])
def test_each_version_reads_its_own_report(monkeypatch, live_calls, model_version):
    reads = _stored(monkeypatch, StoredSnapshot(to_payload(_response()), GRADED_AT))

    asyncio.run(get_ranking_response(None, 2026, model_version, production=True))

    assert reads == [(ranking_report(model_version), 2026)]


def test_production_without_a_snapshot_is_unavailable(monkeypatch, live_calls):
    _stored(monkeypatch, None)

    assert asyncio.run(get_ranking_response(None, 2026, V4, production=True)) is None
    assert live_calls == []


def test_dev_without_a_snapshot_builds_live(monkeypatch, live_calls):
    _stored(monkeypatch, None)

    served = asyncio.run(get_ranking_response(None, 2026, TARGETS, production=False))

    assert served is not None and served.model_version == _record(2026, TARGETS).model_version
    assert live_calls == [(2026, TARGETS)]


def test_dev_volume_routes_to_the_volume_builder(monkeypatch, live_calls):
    _stored(monkeypatch, None)

    assert asyncio.run(get_ranking_response(None, 2026, NFL_VOLUME_MODEL_VERSION, production=False)) is None
    assert live_calls == [(2026, NFL_VOLUME_MODEL_VERSION)]
