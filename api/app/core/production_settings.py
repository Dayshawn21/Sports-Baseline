"""Startup checks that keep a production deploy from running with local defaults."""
from __future__ import annotations

PRODUCTION_ENV = "production"
MIN_ADMIN_KEY_LENGTH = 32


def is_production(api_env: str) -> bool:
    return api_env.strip().lower() == PRODUCTION_ENV


def validate_production_settings(
    api_env: str, admin_api_key: str, cors_origins: list[str]
) -> list[str]:
    """Return every problem that should stop a production start; empty off production."""
    if not is_production(api_env):
        return []
    problems: list[str] = []
    key = admin_api_key.strip()
    if not key:
        problems.append("ADMIN_API_KEY is empty, so every write route would be open")
    elif len(key) < MIN_ADMIN_KEY_LENGTH:
        problems.append(f"ADMIN_API_KEY is shorter than {MIN_ADMIN_KEY_LENGTH} characters")
    if not cors_origins:
        problems.append("CORS_ORIGINS is empty")
    for origin in cors_origins:
        if origin.strip() == "*":
            problems.append("CORS_ORIGINS allows every origin ('*')")
        elif "localhost" in origin or "127.0.0.1" in origin:
            problems.append(f"CORS_ORIGINS includes a local origin ({origin})")
    return problems
