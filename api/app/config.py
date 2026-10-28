import re
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolves to the .env file next to this file (api/app/.env)
_ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    database_url: str
    api_title: str = "Lineform"
    api_env: str = "dev"
    odds_api_key: str = ""
    the_odds_api_key: str = ""
    # Odds-API.io's free plan allows two books; Bet365 went paid-only on 2026-10-26.
    live_odds_bookmakers: str = "DraftKings,FanDuel"
    api_sports_nfl_key: str = ""
    livetennis_api_key: str = ""
    livetennis_tier: str = "free"  # free | basic | pro | ultra
    # Future PrizePicks live-prop ingest safety floor. The provider is rate-limited,
    # so callers must retain cached snapshots between polls.
    prizepicks_poll_interval_minutes: int = 120
    # Shared secret for mutating / quota-spending routes. Empty leaves them open,
    # which is the local default — see app/security.py.
    admin_api_key: str = ""
    # JSON list in .env, e.g. CORS_ORIGINS=["https://app.example.com"].
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]
    # Per client IP, in the `limits` notation; heavy routes are in app/core/rate_limits.py.
    rate_limit_default: str = "120/minute"
    rate_limit_heavy: str = "10/minute"
    # Ask Lineform. Passed to the client explicitly: pydantic-settings reads the
    # .env file without exporting it, so the SDK cannot find the key on its own.
    anthropic_api_key: str = ""
    # Off by default; production also refuses it without ANTHROPIC_API_KEY.
    ask_enabled: bool = False
    ask_model: str = "claude-haiku-5-5"
    # Bounded so a typo in the environment cannot make one question expensive.
    ask_max_tokens: int = Field(2048, ge=256, le=4096)
    ask_max_tool_iterations: int = Field(5, ge=1, le=8)
    ask_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    # USD per million tokens for ask_model (claude-haiku-5-5, checked 2026-10-28);
    # cache writes are the 5-minute rate, the only TTL the loop uses.
    ask_price_input_per_mtok: float = 0.10
    ask_price_output_per_mtok: float = 0.50
    ask_price_cache_read_per_mtok: float = 0.01
    ask_price_cache_write_per_mtok: float = 0.125
    # In memory, so a restart resets both; see app/services/ask/guardrails.py.
    ask_daily_questions_per_ip: int = Field(20, ge=1, le=200)
    ask_daily_spend_cap_usd: float = Field(1.0, gt=0, le=20)

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        # Strip unsupported params
        url = re.sub(r"\?.*", "", url)
        # Ensure psycopg3 async driver
        url = re.sub(r"^postgresql(\+\w+)?://", "postgresql+psycopg://", url)
        return url


settings = Settings()
