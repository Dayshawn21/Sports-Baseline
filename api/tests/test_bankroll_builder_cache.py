"""The Bankroll Builder reads the shared prediction cache, bounds its limits and
logs an overlay failure (F-23)."""
import asyncio
import logging
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.pool import get_db
from app.repositories import matches as match_repo
from app.routers import tennis as tennis_router
from app.services.tennis import bankroll_builder, prediction_cache
from app.services.tennis.live_odds_cache import TimedSingleFlight

TODAY = date(2026, 11, 6)


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = TimedSingleFlight(prediction_cache.CACHE_TTL_SECONDS, failure_ttl_seconds=0)
    monkeypatch.setattr(prediction_cache, "_PREDICTIONS", cache)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(tennis_router.router, prefix="/tennis")
    app.state.registry = None
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


@pytest.mark.parametrize(
    "params",
    [
        {"max_singles": tennis_router.MAX_BANKROLL_SINGLES + 1},
        {"max_parlays": tennis_router.MAX_BANKROLL_PARLAYS + 1},
        {"max_singles": 0},
        {"max_parlays": 0},
    ],
)
def test_out_of_range_limits_are_rejected(params):
    assert _client().get("/tennis/bankroll/today", params=params).status_code == 422


@pytest.mark.parametrize("path", ["/tennis/bankroll/today", "/tennis/parlays/suggested"])
def test_a_failed_prediction_build_is_a_503(monkeypatch, path):
    async def predict_today(_db, _registry, _dates):
        raise RuntimeError("model load failed")

    monkeypatch.setattr(prediction_cache, "predict_today", predict_today)

    res = _client().get(path)

    assert res.status_code == 503
    assert res.json()["detail"] == "Tennis predictions are temporarily unavailable."


def test_repeat_builds_share_one_prediction_run(monkeypatch):
    calls: list[list[date]] = []

    async def predict_today(_db, _registry, dates):
        calls.append(dates)
        return []

    monkeypatch.setattr(prediction_cache, "predict_today", predict_today)

    async def twice():
        for _ in range(2):
            await bankroll_builder.build_bankroll_picks(None, None, None, TODAY)

    asyncio.run(twice())

    assert calls == [[TODAY, date(2026, 11, 7)]]


def test_an_overlay_failure_is_logged_and_the_build_continues(monkeypatch, caplog):
    async def predict_today(_db, _registry, _dates):
        return [SimpleNamespace(match_id=1, tour="ATP")]

    async def overlay(_predictions):
        raise RuntimeError("odds provider down")

    async def no_rows(*_args):
        return {}

    async def no_matches(*_args):
        return []

    monkeypatch.setattr(prediction_cache, "predict_today", predict_today)
    monkeypatch.setattr(bankroll_builder, "overlay_live_moneyline", overlay)
    monkeypatch.setattr(match_repo, "get_all_market_odds_batch", no_rows)
    monkeypatch.setattr(match_repo, "get_upcoming", no_matches)
    monkeypatch.setattr(bankroll_builder, "_generate_ml_picks", lambda _pred: [])
    monkeypatch.setattr(bankroll_builder, "_generate_set_picks", lambda _pred, _odds: [])

    with caplog.at_level(logging.WARNING, logger=bankroll_builder.__name__):
        result = asyncio.run(bankroll_builder.build_bankroll_picks(None, None, TODAY, TODAY))

    assert result.total_matches_scanned == 1
    assert "overlay failed" in caplog.text
    assert "odds provider down" in caplog.text
