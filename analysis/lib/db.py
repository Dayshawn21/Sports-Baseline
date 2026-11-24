"""The one database connection for notebooks. Read-only at the server, never a writer."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url

APP_ENV_FILE = Path(__file__).resolve().parents[2] / "api" / "app" / ".env"
# Two layers: the server default covers every transaction on the connection, and
# psycopg's per-transaction BEGIN READ ONLY still holds if a pooler drops options.
READ_ONLY_OPTIONS = "-c default_transaction_read_only=on"


class DatabaseUrlMissing(RuntimeError):
    pass


def sync_url(url: str) -> str:
    """Any PostgreSQL URL (async drivers included) as a sync psycopg URL."""
    parsed = make_url(url)
    if parsed.get_backend_name() not in {"postgresql", "postgres"}:
        raise ValueError("DATABASE_URL is not a PostgreSQL URL")
    return parsed.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)


def database_url(env_file: Path = APP_ENV_FILE) -> str:
    """DATABASE_URL from the environment, else from the app's env file. Never printed."""
    url = os.environ.get("DATABASE_URL")
    if not url and env_file.is_file():
        url = dotenv_values(env_file).get("DATABASE_URL")
    if not url:
        raise DatabaseUrlMissing(f"DATABASE_URL is not set in the environment or in {env_file}")
    return sync_url(url)


def read_engine() -> Engine:
    engine = create_engine(
        database_url(),
        connect_args={"options": READ_ONLY_OPTIONS},
        pool_pre_ping=True,
    )
    return engine.execution_options(postgresql_readonly=True)
