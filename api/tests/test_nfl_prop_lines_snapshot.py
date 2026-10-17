"""The precomputed 27a line grading (37d): the stored copy is served as built,
production never replays it, and dev still can."""
import asyncio
import json

import pytest

from app.core.report_snapshot_source import ReportSource, report_source
from app.ingest.nfl_model_snapshot import headline
from app.repositories import report_snapshots
from app.repositories.report_snapshots import StoredSnapshot
from app.schemas.nfl import NflModelPropLinesResponse
from app.services.nfl import track_record
from app.services.nfl.prop_lines_snapshot import PROP_LINES_REPORT, get_prop_lines_response, to_payload
from app.services.nfl.track_record import build_line_record
from tests.test_nfl_track_record_service import GRADED_AT, _line, _line_inputs


def _response(season: int = 2026) -> NflModelPropLinesResponse:
    lines = [_line(1, stat_value=6.0), _line(2, stat_value=3.0)]
    record = build_line_record(_line_inputs(lines, {1: 1.0, 2: 1.0}, {1: 0.6}), season, GRADED_AT)
    return NflModelPropLinesResponse.model_validate(record)


class TestReportSource:
    def test_a_stored_snapshot_is_served_everywhere(self):
        assert report_source(True, production=True) is ReportSource.SNAPSHOT
        assert report_source(True, production=False) is ReportSource.SNAPSHOT

    def test_production_never_computes_live(self):
        assert report_source(False, production=True) is ReportSource.UNAVAILABLE

    def test_dev_computes_live_without_a_snapshot(self):
        assert report_source(False, production=False) is ReportSource.LIVE


def test_the_stored_payload_rebuilds_the_same_response():
    response = _response()
    stored = json.loads(json.dumps(to_payload(response)))

    assert NflModelPropLinesResponse.model_validate(stored) == response
    assert NflModelPropLinesResponse.model_validate(stored).model_dump(by_alias=True) == response.model_dump(
        by_alias=True
    )


@pytest.fixture
def live_calls(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []

    async def live(_db, season):
        calls.append(season)
        return build_line_record(_line_inputs([_line(1, stat_value=6.0)], {1: 1.0}, {}), season, GRADED_AT)

    monkeypatch.setattr(track_record, "get_line_record", live)
    return calls


def _stored(monkeypatch: pytest.MonkeyPatch, snapshot: StoredSnapshot | None) -> list[tuple[str, int]]:
    reads: list[tuple[str, int]] = []

    async def get(_db, report, season):
        reads.append((report, season))
        return snapshot

    monkeypatch.setattr(report_snapshots, "get_snapshot", get)
    return reads


def test_a_snapshot_is_served_without_a_replay(monkeypatch, live_calls):
    response = _response()
    reads = _stored(monkeypatch, StoredSnapshot(to_payload(response), GRADED_AT))

    served = asyncio.run(get_prop_lines_response(None, 2026, production=True))

    assert served == response
    assert reads == [(PROP_LINES_REPORT, 2026)]
    assert live_calls == []


def test_production_without_a_snapshot_is_unavailable(monkeypatch, live_calls):
    _stored(monkeypatch, None)

    assert asyncio.run(get_prop_lines_response(None, 2026, production=True)) is None
    assert live_calls == []


def test_dev_without_a_snapshot_replays_live(monkeypatch, live_calls):
    _stored(monkeypatch, None)

    served = asyncio.run(get_prop_lines_response(None, 2026, production=False))

    assert served is not None and served.season == 2026
    assert live_calls == [2026]


def test_the_headline_names_calls_rate_and_weeks():
    text = headline(_response())

    assert text.startswith("NFL prop-line grading 2026 (model ")
    assert "2 calls, hit rate 50.0%" in text
