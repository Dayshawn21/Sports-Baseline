from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.core.nfl_projection import NFL_PROJECTION_MODEL_VERSION as V4
from app.db.pool import get_db
from app.repositories import report_snapshots
from app.routers import nfl as nfl_router
from app.schemas.nfl import NflModelRankingResponse
from app.services.nfl import track_record, volume_ranking
from app.services.nfl.track_record import build_ranking_record
from tests.helpers.nfl_track_record_service import GRADED_AT, _call, _inputs
from tests.helpers.nfl_volume_ranking_service import FINISHED, _fresh_caches, _passing_sample, _rungs, _volume  # noqa: F401


@pytest.fixture(autouse=True)
def dev_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_snapshot(_db, _report, _season):
        return None

    monkeypatch.setattr(report_snapshots, "get_snapshot", no_snapshot)
    monkeypatch.setattr(settings, "api_env", "dev")


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(nfl_router.router, prefix="/nfl")
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


def _volume_record(
    monkeypatch: pytest.MonkeyPatch, lines: list | None = None, finished: set[int] = FINISHED,
) -> volume_ranking.VolumeRankingRecord:
    return _volume(monkeypatch, lines if lines is not None else _passing_sample(), finished=finished)


def _patch_volume(monkeypatch: pytest.MonkeyPatch, record: volume_ranking.VolumeRankingRecord | None) -> list[int]:
    seasons: list[int] = []

    async def fake(_db, season):
        seasons.append(season)
        return record

    monkeypatch.setattr(volume_ranking, "get_volume_record", fake)
    return seasons


def _patch_v4(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    versions: list[str] = []

    async def record(_db, season, model_version=V4):
        versions.append(model_version)
        return build_ranking_record(_inputs([_call(i) for i in range(3)]), season, GRADED_AT, model_version)

    monkeypatch.setattr(track_record, "get_ranking_record", record)
    return versions


def test_the_default_and_explicit_v4_selectors_return_the_same_record(monkeypatch: pytest.MonkeyPatch) -> None:
    versions = _patch_v4(monkeypatch)

    default = _client().get("/nfl/model/ranking", params={"season": 2026})
    explicit = _client().get("/nfl/model/ranking", params={"season": 2026, "model_version": V4})

    assert default.status_code == explicit.status_code == 200
    assert default.json() == explicit.json() and versions == [V4, V4]
    assert default.json()["logLoss"] is None
    assert default.json()["modelVersion"] == V4


def test_the_volume_selector_returns_its_identity_and_the_log_loss_block(monkeypatch: pytest.MonkeyPatch) -> None:
    seasons = _patch_volume(monkeypatch, _volume_record(monkeypatch))

    res = _client().get("/nfl/model/ranking", params={"season": 2026, "model_version": "nfl-volume-v1"})

    assert res.status_code == 200 and seasons == [2026]
    body = res.json()
    assert (body["modelVersion"], body["overProbabilityVersion"]) == ("nfl-volume-v1", "nfl-volume-anchor-v1")
    assert [(row["oddsType"], row["side"], row["verdict"]) for row in body["slices"]] == [
        ("standard", "over", "adopt"), ("standard", "under", "insufficient"),
        ("goblin", "over", "insufficient"), ("demon", "over", "insufficient"),
    ]
    log_loss = body["logLoss"]
    assert set(log_loss["progress"]) >= {"n", "weeksWon", "weeksRequired", "blend", "raw", "half", "passed"}
    states = {(item["oddsType"], item["side"]): item["state"] for item in log_loss["slices"]}
    assert states == {
        ("standard", "over"): "evaluated", ("standard", "under"): "evaluated",
        ("goblin", "over"): "not_frozen", ("demon", "over"): "not_frozen",
    }
    assert log_loss["slices"][0]["logLoss"]["passed"] is True and log_loss["slices"][2]["logLoss"] is None


def test_a_rung_payout_with_frozen_rows_is_evaluated_and_the_rest_stay_not_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_volume(monkeypatch, _volume_record(monkeypatch, _passing_sample() + _rungs("demon", 2_000_000)))

    body = _client().get("/nfl/model/ranking", params={"season": 2026, "model_version": "nfl-volume-v1"}).json()

    states = {(item["oddsType"], item["side"]): item["state"] for item in body["logLoss"]["slices"]}
    assert states == {
        ("standard", "over"): "evaluated", ("standard", "under"): "evaluated",
        ("goblin", "over"): "not_frozen", ("demon", "over"): "evaluated",
    }
    demon = next(row for row in body["slices"] if row["oddsType"] == "demon")
    assert (demon["verdict"], demon["n"]) == ("adopt", 200)
    assert next(item for item in body["logLoss"]["slices"] if item["oddsType"] == "demon")["logLoss"]["passed"] is True


def test_an_empty_volume_sample_is_a_200(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_volume(monkeypatch, _volume_record(monkeypatch, [], finished=set()))

    res = _client().get("/nfl/model/ranking", params={"season": 2026, "model_version": "nfl-volume-v1"})

    assert res.status_code == 200
    body = res.json()
    assert body["frozenRows"] == 0 and all(row["n"] == 0 for row in body["slices"])
    assert body["logLoss"]["progress"]["n"] == 0 and body["logLoss"]["progress"]["blend"] is None


def test_an_unsupported_selector_is_a_422(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_v4(monkeypatch)
    res = _client().get("/nfl/model/ranking", params={"season": 2026, "model_version": "nfl-volume-v2"})
    assert res.status_code == 422


def test_a_volume_failure_is_a_503_that_leaves_the_other_records_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_volume(monkeypatch, None)
    _patch_v4(monkeypatch)

    failed = _client().get("/nfl/model/ranking", params={"season": 2026, "model_version": "nfl-volume-v1"})
    other = _client().get("/nfl/model/ranking", params={"season": 2026})

    assert failed.status_code == 503 and failed.json()["detail"] == "The ranking check is unavailable; try again shortly"
    assert other.status_code == 200


def test_the_log_loss_field_is_optional_and_absent_records_serialize_as_null() -> None:
    record = build_ranking_record(_inputs([_call(i) for i in range(3)]), 2026, GRADED_AT, V4)
    response = NflModelRankingResponse.model_validate(record)

    assert response.log_loss is None
    assert response.model_dump(by_alias=True)["logLoss"] is None

