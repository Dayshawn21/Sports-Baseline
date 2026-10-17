"""Pins 0041 to what it undoes: 0039's views and the global keys 0040 left behind."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

VERSIONS = Path(__file__).parents[1] / "app/db/migrations/versions"


def _load(filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), VERSIONS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_downgrade_restores_0039s_views_exactly() -> None:
    m0039, m0041 = _load("0039_shared_team_sport_tables.py"), _load("0041_drop_nfl_views.py")

    assert m0041.TABLE_RENAMES == m0039.TABLE_RENAMES
    for view in m0039.TABLE_RENAMES:
        assert m0041.view_select(view) == m0039.view_select(view), view


def test_it_drops_exactly_the_global_keys_0040_kept_beside_the_scoped_ones() -> None:
    m0040, m0041 = _load("0040_sport_scoped_keys.py"), _load("0041_drop_nfl_views.py")

    assert set(m0041.GLOBAL_KEYS) == set(m0040.GLOBAL_KEYS.values())
    for scoped, global_index in m0040.GLOBAL_KEYS.items():
        table, columns = m0040.SCOPED_KEYS[scoped]
        assert m0041.GLOBAL_KEYS[global_index] == (table, columns[1]) and columns[0] == "sport"


def test_upgrade_drops_and_downgrade_guards_then_recreates(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = _load("0041_drop_nfl_views.py")
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()
    assert statements == [f"DROP VIEW {view}" for view in migration.TABLE_RENAMES] + [
        f"DROP INDEX {index}" for index in migration.GLOBAL_KEYS
    ]

    statements.clear()
    migration.downgrade()
    guards = [s for s in statements if "RAISE EXCEPTION" in s]
    assert len(guards) == 7
    assert statements.index(guards[-1]) < min(
        i for i, s in enumerate(statements) if s.startswith(("CREATE UNIQUE INDEX", "CREATE VIEW"))
    )
    assert sum(s.endswith("WITH LOCAL CHECK OPTION") for s in statements) == 7
    assert sum(s.endswith("SET DEFAULT 'nfl'") for s in statements) == 7
