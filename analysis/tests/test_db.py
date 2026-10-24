from pathlib import Path

import pytest

from lib import db

ASYNC_URL = "postgresql+psycopg_async://user:secret@host.example/neondb?sslmode=require"


def test_sync_url_swaps_async_driver_and_keeps_query():
    assert db.sync_url(ASYNC_URL) == "postgresql+psycopg://user:secret@host.example/neondb?sslmode=require"


@pytest.mark.parametrize("url", ["postgresql://u:p@h/d", "postgresql+asyncpg://u:p@h/d"])
def test_sync_url_normalizes_plain_and_asyncpg(url):
    assert db.sync_url(url).startswith("postgresql+psycopg://")


def test_sync_url_rejects_other_databases():
    with pytest.raises(ValueError):
        db.sync_url("sqlite:///local.db")


def _env_file(tmp_path: Path, url: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(f"DATABASE_URL={url}\nOTHER=1\n")
    return path


def test_environment_wins_over_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://env:p@h/d")
    assert "env:p@h" in db.database_url(_env_file(tmp_path, "postgresql://file:p@h/d"))


def test_env_file_used_when_environment_is_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert "file:p@h" in db.database_url(_env_file(tmp_path, "postgresql://file:p@h/d"))


def test_missing_url_raises_without_leaking(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(db.DatabaseUrlMissing) as error:
        db.database_url(tmp_path / "absent.env")
    assert "postgresql" not in str(error.value)


def test_read_engine_is_read_only_at_server_and_per_transaction(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", ASYNC_URL)
    engine = db.read_engine()
    assert engine.get_execution_options()["postgresql_readonly"] is True
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg"
    assert db.READ_ONLY_OPTIONS == "-c default_transaction_read_only=on"
