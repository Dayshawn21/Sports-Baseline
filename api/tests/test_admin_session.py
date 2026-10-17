import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

KEY = "k" * 32


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}])
def test_a_missing_or_wrong_key_is_refused(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, headers: dict[str, str]
) -> None:
    monkeypatch.setattr(settings, "admin_api_key", KEY)
    assert client.get("/admin/session", headers=headers).status_code == 401


def test_the_right_key_signs_in(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_api_key", KEY)
    res = client.get("/admin/session", headers={"X-API-Key": KEY})
    assert res.status_code == 200
    assert res.json() == {"keyRequired": True}


def test_with_no_server_key_the_session_is_open(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_api_key", "")
    res = client.get("/admin/session")
    assert res.status_code == 200
    assert res.json() == {"keyRequired": False}
