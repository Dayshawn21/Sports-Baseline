import logging

import pytest
from fastapi.testclient import TestClient

from pydantic import ValidationError

from app.config import Settings, settings
from app.core.production_settings import validate_production_settings
from app.main import app, configure_app_logging

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


def test_production_allows_ask_with_a_key() -> None:
    assert validate_production_settings("production", STRONG_KEY, SITE, True, "sk-ant-test") == []


@pytest.mark.parametrize("key", ["", "   "])
def test_production_refuses_ask_without_a_key(key: str) -> None:
    [problem] = validate_production_settings("production", STRONG_KEY, SITE, True, key)
    assert problem == "ANTHROPIC_API_KEY is empty while ASK_ENABLED is on"


def test_production_allows_ask_off_without_a_key() -> None:
    assert validate_production_settings("production", STRONG_KEY, SITE, False, "") == []


def test_dev_allows_ask_without_a_key() -> None:
    assert validate_production_settings("dev", "", SITE, True, "") == []


def test_production_start_with_ask_and_no_key_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_env", "production")
    monkeypatch.setattr(settings, "admin_api_key", STRONG_KEY)
    monkeypatch.setattr(settings, "cors_origins", SITE)
    monkeypatch.setattr(settings, "ask_enabled", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is empty while ASK_ENABLED is on"):
        with TestClient(app):
            pass


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ask_max_tokens", 255), ("ask_max_tokens", 4097),
        ("ask_max_tool_iterations", 0), ("ask_max_tool_iterations", 9),
        ("ask_daily_questions_per_ip", 0), ("ask_daily_questions_per_ip", 201),
        ("ask_daily_spend_cap_usd", 0), ("ask_daily_spend_cap_usd", 20.01),
    ],
)
def test_out_of_range_ask_limits_fail_validation(field: str, value: float) -> None:
    with pytest.raises(ValidationError, match=field):
        Settings(database_url="postgresql://localhost/ci", _env_file=None, **{field: value})


def test_the_ask_defaults_are_in_range() -> None:
    defaults = Settings(database_url="postgresql://localhost/ci", _env_file=None)
    assert (defaults.ask_max_tokens, defaults.ask_max_tool_iterations) == (2048, 5)
    assert (defaults.ask_daily_questions_per_ip, defaults.ask_daily_spend_cap_usd) == (20, 1.0)


def test_the_api_prints_its_own_info_lines() -> None:
    # Importing app.main (as uvicorn does) must make app.* INFO visible.
    app_log = logging.getLogger("app")
    assert app_log.getEffectiveLevel() == logging.INFO
    assert app_log.handlers
    assert logging.getLogger("app.services.ask.answer_stream").isEnabledFor(logging.INFO)


def test_configuring_twice_adds_no_second_handler() -> None:
    before = len(logging.getLogger("app").handlers)
    configure_app_logging()
    assert len(logging.getLogger("app").handlers) == before
