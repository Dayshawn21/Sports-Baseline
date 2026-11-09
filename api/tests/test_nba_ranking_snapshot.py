"""The precomputed NBA ranking check: the stored copy is served as built,
production never builds live, and dev still can."""
import asyncio
import json

import pytest

from app.ingest.nba_ranking_snapshot import headline
from app.repositories import report_snapshots
from app.repositories.report_snapshots import StoredSnapshot
from app.schemas.nba import NbaModelRankingResponse
from app.services.nba import track_record
from app.services.nba.ranking_snapshot import RANKING_REPORT, get_ranking_response, to_payload
from tests.helpers.nfl_track_record_service import GRADED_AT, _call, _inputs


def _record(season: int = 2026):
    return track_record.build_ranking_record(_inputs([_call(i) for i in range(3)]), season, GRADED_AT)


def _response(season: int = 2026) -> NbaModelRankingResponse:
    return NbaModelRankingResponse.model_validate(_record(season))


def test_the_stored_payload_rebuilds_the_same_response():
    response = _response()
    stored = json.loads(json.dumps(to_payload(response)))

    assert NbaModelRankingResponse.model_validate(stored).model_dump(by_alias=True) == response.model_dump(by_alias=True)


def test_headline_names_the_season_and_model():
    line = headline(_response())

    assert "NBA" in line and "2026" in line and _response().model_version in line


@pytest.fixture
def live_calls(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []

    async def live(_db, season):
        calls.append(season)
        return _record(season)

    monkeypatch.setattr(track_record, "get_ranking_record", live)
    return calls


def _stored(monkeypatch: pytest.MonkeyPatch, snapshot: StoredSnapshot | None) -> list[tuple[str, int]]:
    reads: list[tuple[str, int]] = []

    async def get(_db, report, season):
        reads.append((report, season))
        return snapshot

    monkeypatch.setattr(report_snapshots, "get_snapshot", get)
    return reads


def test_a_snapshot_is_served_without_a_live_build(monkeypatch, live_calls):
    response = _response(2025)
    reads = _stored(monkeypatch, StoredSnapshot(to_payload(response), GRADED_AT))

    served = asyncio.run(get_ranking_response(None, 2025, production=True))

    assert served == response
    assert reads == [(RANKING_REPORT, 2025)]
    assert live_calls == []


def test_production_without_a_snapshot_is_unavailable(monkeypatch, live_calls):
    _stored(monkeypatch, None)

    assert asyncio.run(get_ranking_response(None, 2026, production=True)) is None
    assert live_calls == []


def test_dev_without_a_snapshot_builds_live(monkeypatch, live_calls):
    _stored(monkeypatch, None)

    served = asyncio.run(get_ranking_response(None, 2026, production=False))

    assert served is not None and served.season == 2026
    assert live_calls == [2026]


def test_dev_passes_a_failed_live_build_through_as_unavailable(monkeypatch):
    _stored(monkeypatch, None)

    async def failed(_db, _season):
        return None

    monkeypatch.setattr(track_record, "get_ranking_record", failed)

    assert asyncio.run(get_ranking_response(None, 2026, production=False)) is None
