"""Pins 0042: three nullable smallint stat columns, removed in reverse order."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa

VERSIONS = Path(__file__).parents[1] / "app/db/migrations/versions"


def _load() -> ModuleType:
    path = VERSIONS / "0042_nfl_kicking_punting_stats.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_adds_nullable_smallint_columns_without_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = _load()
    added: list[tuple[str, sa.Column]] = []
    monkeypatch.setattr(migration.op, "add_column", lambda table, column: added.append((table, column)))

    migration.upgrade()

    assert [(table, column.name) for table, column in added] == [
        ("nfl_player_weekly_stats", "fg_made"),
        ("nfl_player_weekly_stats", "pat_made"),
        ("nfl_player_weekly_stats", "punts"),
    ]
    for _, column in added:
        assert isinstance(column.type, sa.SmallInteger) and column.nullable
        assert column.default is None and column.server_default is None


def test_downgrade_drops_the_same_columns_in_reverse(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = _load()
    dropped: list[tuple[str, str]] = []
    monkeypatch.setattr(migration.op, "drop_column", lambda table, column: dropped.append((table, column)))

    migration.downgrade()

    assert dropped == [("nfl_player_weekly_stats", c) for c in ("punts", "pat_made", "fg_made")]
