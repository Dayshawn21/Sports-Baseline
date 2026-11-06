import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.rate_limits import RateRule, client_key, rule_for_path
from app.main import app

DEFAULT = "120/minute"
HEAVY = "10/minute"


@pytest.mark.parametrize(
    "path",
    ["/nfl/model/prop-lines", "/tennis/model/predictions", "/nba/model/ranking", "/nfl/slate", "/admin/session", "/ask"],
)
def test_heavy_routes_get_their_own_bucket(path: str) -> None:
    assert rule_for_path(path, DEFAULT, HEAVY) == RateRule(HEAVY, path)


@pytest.mark.parametrize("path", ["/nba/slate", "/tennis/predictions/today", "/nfl/games/1", "/ask/status"])
def test_other_routes_share_the_default_bucket(path: str) -> None:
    assert rule_for_path(path, DEFAULT, HEAVY) == RateRule(DEFAULT, "default")


def test_health_is_never_limited() -> None:
    assert rule_for_path("/health", DEFAULT, HEAVY) is None


def test_the_request_past_the_default_limit_gets_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_default", "2/minute")
    client = TestClient(app)
    assert [client.get("/openapi.json").status_code for _ in range(2)] == [200, 200]
    res = client.get("/openapi.json")
    assert res.status_code == 429
    assert 1 <= int(res.headers["Retry-After"]) <= 60
    assert res.headers["X-Content-Type-Options"] == "nosniff"


def test_a_heavy_route_hits_its_own_limit_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_heavy", "1/minute")
    client = TestClient(app)
    path = "/nfl/model/over-probability-fit"
    assert client.get(path).status_code == 200
    assert client.get(path).status_code == 429
    assert client.get("/openapi.json").status_code == 200


def test_health_stays_up_while_a_client_is_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_default", "1/minute")
    client = TestClient(app)
    client.get("/openapi.json")
    assert client.get("/openapi.json").status_code == 429
    assert client.get("/health").status_code == 200


def test_a_429_carries_cors_headers_for_an_allowed_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_default", "1/minute")
    client = TestClient(app)
    origin = {"Origin": "http://localhost:3001"}
    client.get("/openapi.json", headers=origin)
    res = client.get("/openapi.json", headers=origin)
    assert res.status_code == 429
    assert res.headers["access-control-allow-origin"] == "http://localhost:3001"


def test_the_cloudflare_address_wins_over_a_spoofed_forwarded_for() -> None:
    headers = {"cf-connecting-ip": "198.51.100.4", "x-forwarded-for": "203.0.113.7, 198.51.100.4"}
    assert client_key(headers, "10.0.0.1") == "198.51.100.4"


def test_x_forwarded_for_alone_is_ignored() -> None:
    assert client_key({"x-forwarded-for": "203.0.113.7"}, "10.0.0.1") == "10.0.0.1"


@pytest.mark.parametrize("headers", [{}, {"cf-connecting-ip": "  "}])
def test_a_missing_or_blank_cloudflare_header_falls_back_to_the_peer(headers: dict[str, str]) -> None:
    assert client_key(headers, "10.0.0.1") == "10.0.0.1"


def test_no_header_and_no_peer_is_unknown() -> None:
    assert client_key({}, None) == "unknown"


def test_rotating_forwarded_for_does_not_reset_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_default", "1/minute")
    client = TestClient(app)
    client.get("/openapi.json", headers={"X-Forwarded-For": "203.0.113.1"})
    assert client.get("/openapi.json", headers={"X-Forwarded-For": "203.0.113.2"}).status_code == 429


def test_each_cloudflare_address_gets_its_own_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_default", "1/minute")
    client = TestClient(app)
    assert client.get("/openapi.json", headers={"CF-Connecting-IP": "198.51.100.1"}).status_code == 200
    assert client.get("/openapi.json", headers={"CF-Connecting-IP": "198.51.100.2"}).status_code == 200
    assert client.get("/openapi.json", headers={"CF-Connecting-IP": "198.51.100.1"}).status_code == 429
