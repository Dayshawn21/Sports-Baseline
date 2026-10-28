import asyncio
from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.pool import get_db
from app.routers import tennis as tennis_router
from app.services.tennis import track_record
from app.services.tennis.track_record import build_prediction_grading
from tests.test_track_record_service import GRADED_AT, MODEL, _row


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(tennis_router.router, prefix="/tennis")
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


def test_predictions_route_serializes_in_camel_case(monkeypatch):
    async def grading(_db, _version):
        return build_prediction_grading([_row(1, close=0.62), _row(2, tour="WTA")], MODEL, GRADED_AT)

    monkeypatch.setattr(track_record, "get_prediction_grading", grading)

    res = _client().get("/tennis/model/predictions")

    assert res.status_code == 200
    body = res.json()
    assert body["modelVersion"] == MODEL
    assert body["gradedAt"].startswith("2026-09-29T12:00:00")
    assert body["counts"]["withClose"] == 1
    ensemble = body["groups"][0]["components"][1]
    assert ensemble["name"] == "ensemble"
    assert set(ensemble["vsMarket"]) == {"mean", "standardError", "signal"}
    assert body["calibration"][0]["bins"][0]["meanPredicted"] > 0
    assert body["clv"][0]["meanMoveToward"] is not None
    assert body["versions"][0] == {"modelVersion": track_record.DEFAULT_MODEL_VERSION, "settled": 0, "served": True}
    assert body["versions"][1] == {"modelVersion": MODEL, "settled": 2, "served": False}


def _rows_loader(monkeypatch, rows):
    calls = []

    async def load(_db):
        calls.append(1)
        return rows

    monkeypatch.setattr(track_record.prediction_repo, "get_graded_predictions", load)
    monkeypatch.setattr(track_record, "_PREDICTIONS", track_record.TimedSingleFlight(60))
    return calls


def test_predictions_route_grades_the_requested_version(monkeypatch):
    _rows_loader(monkeypatch, [_row(1), _row(2, version="ensemble-v1+lgbm-v5")])

    body = _client().get("/tennis/model/predictions", params={"model_version": MODEL}).json()

    assert body["modelVersion"] == MODEL
    assert body["counts"]["graded"] == 1


def test_predictions_route_serializes_no_ml_pair_without_expanding_all_four_sample(monkeypatch):
    version = "ensemble-v3+lgbm-none"
    _rows_loader(monkeypatch, [_row(1, tour="CHALLENGER", ml=None, version=version)])

    body = _client().get("/tennis/model/predictions", params={"model_version": version}).json()

    pair = next(g for g in body["ensembleMarketGroups"] if g["group"] == "CHALLENGER")
    assert pair["n"] == 1
    assert [c["name"] for c in pair["components"]] == ["market", "ensemble"]
    assert pair["components"][1]["vsMarket"]["standardError"] is None
    assert pair["components"][1]["vsMarket"]["signal"] == "neutral"
    assert all(g["n"] == 0 for g in body["groups"])
    assert all(s["bins"] == [] for s in body["calibration"])


def test_predictions_route_defaults_to_the_served_version_with_nothing_settled(monkeypatch):
    _rows_loader(monkeypatch, [_row(1)])

    body = _client().get("/tennis/model/predictions").json()

    assert body["modelVersion"] == track_record.DEFAULT_MODEL_VERSION
    assert body["counts"]["graded"] == 0
    assert body["groups"][0]["n"] == 0


def test_predictions_route_404s_for_an_unknown_version(monkeypatch):
    _rows_loader(monkeypatch, [_row(1)])

    res = _client().get("/tennis/model/predictions", params={"model_version": "ensemble-v9"})

    assert res.status_code == 404


def test_predictions_route_503s_when_grading_failed(monkeypatch):
    async def grading(_db, _version):
        return None

    monkeypatch.setattr(track_record, "get_prediction_grading", grading)

    assert _client().get("/tennis/model/predictions").status_code == 503


def test_cached_loader_reads_once_for_every_version(monkeypatch):
    calls = _rows_loader(monkeypatch, [_row(1)])

    async def twice():
        return await track_record.get_prediction_grading(None), await track_record.get_prediction_grading(None, MODEL)

    served, older = asyncio.run(twice())

    assert (served.counts.graded, older.counts.graded) == (0, 1)
    assert served.graded_at == older.graded_at
    assert served.graded_at.utcoffset() == timedelta(0)
    assert len(calls) == 1


def test_prizepicks_lines_route_serializes_in_camel_case(monkeypatch):
    from app.services.tennis.track_record import build_line_settlement
    from tests.test_track_record_service import _line

    async def settlement(_db):
        return build_line_settlement([_line(1, 18.5), _line(2, 25.5, "goblin")], {}, GRADED_AT)

    monkeypatch.setattr(track_record, "get_line_settlement", settlement)

    res = _client().get("/tennis/model/prizepicks-lines")

    assert res.status_code == 200
    body = res.json()
    assert body["excluded"]["incompleteScore"] == 0
    standard, goblin = body["rows"]
    assert (standard["oddsType"], standard["overRate"], standard["signal"]) == ("standard", 1.0, "neutral")
    assert goblin["standardError"] is None
    assert goblin["breakEven"] > 0.75


def test_prop_tiers_route_serializes_in_camel_case(monkeypatch):
    from app.services.tennis.track_record import build_tier_grading
    from tests.test_track_record_service import AS_OF, _snap

    async def grading(_db):
        return build_tier_grading([_snap(1)], {}, AS_OF, GRADED_AT)

    monkeypatch.setattr(track_record, "get_tier_grading", grading)

    res = _client().get("/tennis/model/prop-tiers")

    assert res.status_code == 200
    body = res.json()
    assert body["projectionVersion"] == "props-v3"
    assert body["breakEven"] > 0.57
    lean = body["tiers"][2]
    assert (lean["tier"], lean["verdict"], lean["verdictSampleSize"]) == ("LEAN", "accruing", 1)
    assert body["passSnapshotted"] == 0
