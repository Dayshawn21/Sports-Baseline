from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.pool import get_db
from app.routers import nba as nba_router
from app.services.nba import track_record
from tests.test_nfl_track_record_service import GRADED_AT, _call, _inputs


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(nba_router.router, prefix="/nba")
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


def _serve(monkeypatch, current_season: int | None) -> list[int]:
    graded: list[int] = []

    async def season(_db, _now):
        return current_season

    async def record(_db, season):
        graded.append(season)
        return track_record.build_ranking_record(_inputs([_call(i) for i in range(3)]), season, GRADED_AT)

    monkeypatch.setattr(track_record, "nba_season", season)
    monkeypatch.setattr(track_record, "get_ranking_record", record)
    return graded


def test_ranking_route_serves_nba_versions_in_the_shared_camel_case_shape(monkeypatch):
    graded = _serve(monkeypatch, current_season=2026)

    res = _client().get("/nba/model/ranking", params={"season": 2025})

    assert res.status_code == 200
    assert graded == [2025]
    body = res.json()
    assert body["season"] == 2025
    assert (body["modelVersion"], body["overProbabilityVersion"]) == ("nba-reference-v1", "nba-pover-v1")
    assert body["lastSettledWeek"] == 3 and body["rule"]["minPicks"] == 200
    assert body["funnel"]["withPOver"] == 3
    assert [(s["oddsType"], s["side"]) for s in body["slices"]] == [
        ("standard", "over"), ("standard", "under"), ("goblin", "over"), ("demon", "over"),
    ]
    assert set(body["slices"][0]) >= {"hitRate", "standardError", "breakEven", "signal", "weeks"}


def test_ranking_route_defaults_to_the_current_nba_season(monkeypatch):
    graded = _serve(monkeypatch, current_season=2026)

    res = _client().get("/nba/model/ranking")

    assert res.status_code == 200
    assert graded == [2026] and res.json()["season"] == 2026


def test_ranking_route_404s_with_no_regular_season_game(monkeypatch):
    graded = _serve(monkeypatch, current_season=None)

    res = _client().get("/nba/model/ranking")

    assert res.status_code == 404
    assert res.json()["detail"] == "No NBA regular-season games are loaded"
    assert graded == []


def test_ranking_route_503s_when_grading_failed(monkeypatch):
    async def failed(_db, _season):
        return None

    monkeypatch.setattr(track_record, "get_ranking_record", failed)

    assert _client().get("/nba/model/ranking", params={"season": 2026}).status_code == 503
