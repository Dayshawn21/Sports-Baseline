import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.production_settings import validate_production_settings
from app.main import app

STRONG_KEY = "k" * 32
SITE = ["https://sportapp.example.com"]


def test_a_non_production_env_is_never_checked() -> None:
    assert validate_production_settings("dev", "", ["*"]) == []


def test_a_sound_production_config_passes() -> None:
    assert validate_production_settings("production", STRONG_KEY, SITE) == []


def test_production_env_name_ignores_case_and_spaces() -> None:
    assert validate_production_settings(" Production ", "", SITE) != []


@pytest.mark.parametrize(
    ("key", "expected"),
    [("", "is empty"), ("   ", "is empty"), ("k" * 31, "shorter than 32")],
)
def test_a_missing_or_short_admin_key_is_refused(key: str, expected: str) -> None:
    [problem] = validate_production_settings("production", key, SITE)
    assert expected in problem


@pytest.mark.parametrize(
    ("origins", "expected"),
    [
        ([], "is empty"),
        (["*"], "every origin"),
        (["http://localhost:3001"], "local origin"),
        (["http://127.0.0.1:8000"], "local origin"),
    ],
)
def test_an_open_or_local_cors_origin_is_refused(origins: list[str], expected: str) -> None:
    [problem] = validate_production_settings("production", STRONG_KEY, origins)
    assert expected in problem


def test_every_problem_is_reported_at_once() -> None:
    assert len(validate_production_settings("production", "", ["*"])) == 2


def test_production_start_with_local_defaults_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_env", "production")
    monkeypatch.setattr(settings, "admin_api_key", "")
    with pytest.raises(RuntimeError, match="Refusing to start in production: ADMIN_API_KEY is empty"):
        with TestClient(app):
            pass


def test_responses_carry_security_headers() -> None:
    res = TestClient(app).get("/health")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Strict-Transport-Security" not in res.headers


def test_hsts_is_sent_in_production_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_env", "production")
    res = TestClient(app).get("/health")
    assert res.headers["Strict-Transport-Security"].startswith("max-age=")


def test_production_refuses_ask_before_its_limits_exist() -> None:
    [problem] = validate_production_settings("production", STRONG_KEY, SITE, ask_enabled=True)
    assert "ASK_ENABLED" in problem


def test_dev_allows_ask() -> None:
    assert validate_production_settings("dev", "", SITE, ask_enabled=True) == []


def test_production_start_with_ask_enabled_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_env", "production")
    monkeypatch.setattr(settings, "admin_api_key", STRONG_KEY)
    monkeypatch.setattr(settings, "cors_origins", SITE)
    monkeypatch.setattr(settings, "ask_enabled", True)
    with pytest.raises(RuntimeError, match="ASK_ENABLED is on"):
        with TestClient(app):
            pass
