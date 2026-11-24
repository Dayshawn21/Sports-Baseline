import datetime as dt

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.nba_slate_gaps import DIGEST_LIMIT, SLATE_GAPS_MAX
from app.db.pool import get_db
from app.routers import nba as nba_router
from app.schemas.nba import NbaSlateGapsResponse


def _client(monkeypatch) -> tuple[TestClient, list[int]]:
    limits: list[int] = []

    async def build(_db, date, _now, market=None, limit=DIGEST_LIMIT):
        limits.append(limit)
        return NbaSlateGapsResponse(date=date, model_version="v", items=[])

    monkeypatch.setattr(nba_router, "build_slate_gaps", build)
    app = FastAPI()
    app.include_router(nba_router.router, prefix="/nba")
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app), limits


def test_the_page_digest_size_is_the_default(monkeypatch):
    client, limits = _client(monkeypatch)

    assert client.get("/nba/slate/gaps", params={"date": dt.date(2026, 10, 28).isoformat()}).status_code == 200
    assert limits == [DIGEST_LIMIT]


def test_a_limit_is_forwarded_up_to_the_cap(monkeypatch):
    client, limits = _client(monkeypatch)

    for limit in (1, SLATE_GAPS_MAX):
        assert client.get("/nba/slate/gaps", params={"date": "2026-10-28", "limit": limit}).status_code == 200
    assert limits == [1, SLATE_GAPS_MAX]


def test_a_limit_outside_the_bounds_is_rejected(monkeypatch):
    client, limits = _client(monkeypatch)

    for limit in (0, SLATE_GAPS_MAX + 1):
        assert client.get("/nba/slate/gaps", params={"date": "2026-10-28", "limit": limit}).status_code == 422
    assert limits == []
