import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.db.pool import get_db
from app.repositories import report_snapshots
from app.routers import nfl as nfl_router
from app.services.nfl import track_record
from app.services.nfl.track_record import build_clv_record, build_line_record, build_ranking_record
from tests.test_nfl_track_record_service import (
    GRADED_AT, _call, _clv_pick, _grade, _inputs, _line, _line_inputs,
)


@pytest.fixture(autouse=True)
def no_snapshot_in_dev(monkeypatch):
    """The prop-lines route reads a stored snapshot first; these tests cover the live path."""
    async def no_snapshot(_db, _report, _season):
        return None

    monkeypatch.setattr(report_snapshots, "get_snapshot", no_snapshot)
    monkeypatch.setattr(settings, "api_env", "dev")


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(nfl_router.router, prefix="/nfl")
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


def test_ranking_route_serializes_in_camel_case(monkeypatch):
    seasons = []

    async def record(_db, season, model_version=track_record.NFL_PROJECTION_MODEL_VERSION):
        seasons.append(season)
        return build_ranking_record(_inputs([_call(i) for i in range(3)]), season, GRADED_AT, model_version)

    monkeypatch.setattr(track_record, "get_ranking_record", record)

    res = _client().get("/nfl/model/ranking", params={"season": 2026})

    assert res.status_code == 200
    assert seasons == [2026]
    body = res.json()
    assert body["lastSettledWeek"] == 3
    assert body["rule"]["minPicks"] == 200
    assert body["funnel"]["withPOver"] == 3
    assert set(body["slices"][0]) >= {"oddsType", "hitRate", "standardError", "breakEven", "signal"}


def test_clv_route_serializes_in_camel_case(monkeypatch):
    async def record(_db, season):
        return build_clv_record([_grade([_clv_pick(i, 2, 1.0) for i in range(3)])], season, GRADED_AT)

    monkeypatch.setattr(track_record, "get_clv_record", record)

    body = _client().get("/nfl/model/game-line-clv", params={"season": 2026}).json()

    market = body["markets"][0]
    assert market["modelVersion"] == "NFL_SCORING_V1"
    assert market["headline"]["meanClv"] == 1.0
    assert body["rule"]["verdictPicks"] == 150


def test_prop_lines_route_serializes_in_camel_case(monkeypatch):
    async def record(_db, season):
        lines = [_line(1, stat_value=6.0), _line(2, stat_value=3.0)]
        return build_line_record(_line_inputs(lines, {1: 1.0, 2: 1.0}, {1: 0.6}), season, GRADED_AT)

    monkeypatch.setattr(track_record, "get_line_record", record)

    body = _client().get("/nfl/model/prop-lines", params={"season": 2026}).json()

    assert body["calls"]["hitRate"] == 0.5
    assert body["byEdge"][2]["label"] == "edge >= 15%"
    assert body["byMarket"][0]["market"] == "receptions"
    assert body["coverage"]["weekNotLoaded"] == 0
    assert body["overProbability"][-1]["oddsType"] == "all"
    assert body["reliability"][0]["meanPredicted"] == 0.6


def test_routes_503_when_grading_failed(monkeypatch):
    async def failed(_db, _season, _model_version=track_record.NFL_PROJECTION_MODEL_VERSION):
        return None

    monkeypatch.setattr(track_record, "get_ranking_record", failed)
    monkeypatch.setattr(track_record, "get_clv_record", failed)
    monkeypatch.setattr(track_record, "get_line_record", failed)
    client = _client()

    assert client.get("/nfl/model/ranking", params={"season": 2026}).status_code == 503
    assert client.get("/nfl/model/game-line-clv", params={"season": 2026}).status_code == 503
    assert client.get("/nfl/model/prop-lines", params={"season": 2026}).status_code == 503


def test_routes_require_a_season():
    assert _client().get("/nfl/model/ranking").status_code == 422


def test_fit_route_serves_the_recorded_table():
    body = _client().get("/nfl/model/over-probability-fit").json()

    assert body["served"] is True
    assert body["fitSeason"] == 2025
    assert body["rule"] == {"minCases": 300, "maxEce": 0.02, "maxBinGap": 0.05, "minBinPairs": 200}
    shown = [m["market"] for m in body["markets"] if m["verdict"] == "show"]
    assert shown == ["receiving_yards", "rushing_yards"]
    assert len(body["markets"]) == 8
    assert body["markets"][0]["atProjectionObserved"] == 0.381


def test_fit_route_reports_not_served_once_the_projection_moves_on(monkeypatch):
    monkeypatch.setattr(track_record, "NFL_PROJECTION_MODEL_VERSION", "some-later-version")

    assert _client().get("/nfl/model/over-probability-fit").json()["served"] is False
