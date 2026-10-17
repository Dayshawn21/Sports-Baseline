import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.pool import get_db
from app.main import app
from app.routers import admin

KEY = "k" * 32
SET_ELO = "/admin/players/1/set-elo"


async def _no_player(_db: object, _player_id: int) -> None:
    return None


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(admin, "get_player_by_id", _no_player)
    app.dependency_overrides[get_db] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.pop(get_db)


@pytest.fixture
def key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_api_key", KEY)


WRITES = [
    ("post", "/admin/players/1/fetch-stats"),
    ("post", "/admin/players/1/fetch-elo"),
    ("post", SET_ELO),
    ("get", "/admin/players/flagged"),
]


@pytest.mark.usefixtures("key_set")
@pytest.mark.parametrize(("method", "path"), WRITES)
@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}])
def test_a_missing_or_wrong_key_is_refused(
    client: TestClient, method: str, path: str, headers: dict[str, str]
) -> None:
    res = client.request(method, path, headers=headers)
    assert res.status_code == 401


@pytest.mark.usefixtures("key_set")
def test_the_right_key_reaches_the_route(client: TestClient) -> None:
    res = client.post(SET_ELO, json={"elo": 1500}, headers={"X-API-Key": KEY})
    assert res.status_code == 404


def test_writes_stay_open_when_no_key_is_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "admin_api_key", "")
    assert client.post(SET_ELO, json={"elo": 1500}).status_code == 404


def test_the_bets_routes_are_gone(client: TestClient) -> None:
    assert client.get("/bets/summary").status_code == 404
