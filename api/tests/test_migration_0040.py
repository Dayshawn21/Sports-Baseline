"""Pins 0040's sport-scoped keys and that it leaves no nfl_ name behind except the
global keys 0041 drops."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

MIGRATION = Path(__file__).parents[1] / "app/db/migrations/versions/0040_sport_scoped_keys.py"

# Every nfl_-named index, constraint and sequence on the seven sport_* tables, read
# from the live catalog on 2026-10-02 (primary keys appear once, as constraints).
CATALOG_NFL_NAMES = {
    "idx_nfl_teams_code", "idx_nfl_players_nflverse_id", "idx_nfl_players_team",
    "idx_nfl_aliases_norm", "idx_nfl_aliases_player", "idx_nfl_games_provider",
    "idx_nfl_games_slate", "idx_nfl_games_espn_event", "idx_nfl_prop_lines_slate",
    "idx_nfl_prop_lines_provider", "idx_nfl_prop_lines_segment", "idx_nfl_prop_lines_odds_type",
    "idx_nfl_game_odds_lookup", "idx_nfl_game_odds_fetched", "idx_nfl_prop_predictions_line",
    "uq_nfl_prop_predictions_line_version",
    "nfl_teams_pkey", "nfl_players_pkey", "nfl_players_team_id_fkey", "nfl_player_aliases_pkey",
    "nfl_player_aliases_nfl_player_id_fkey", "nfl_games_pkey", "nfl_games_home_team_id_fkey",
    "nfl_games_away_team_id_fkey", "nfl_prop_lines_pkey", "nfl_prop_lines_player_id_fkey",
    "nfl_prop_lines_game_id_fkey", "nfl_game_odds_pkey", "nfl_game_odds_game_id_fkey",
    "ck_nfl_game_odds_market", "ck_nfl_game_odds_distinct_sides", "nfl_prop_predictions_pkey",
    "nfl_prop_predictions_prop_line_id_fkey",
    "nfl_teams_id_seq", "nfl_players_id_seq", "nfl_player_aliases_id_seq", "nfl_games_id_seq",
    "nfl_prop_lines_id_seq", "nfl_game_odds_id_seq", "nfl_prop_predictions_id_seq",
}


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migration_0040", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _renames(migration: ModuleType) -> dict[str, str]:
    constraints = {old: new for renames in migration.CONSTRAINT_RENAMES.values() for old, new in renames.items()}
    return {**migration.INDEX_RENAMES, **constraints, **migration.SEQUENCE_RENAMES}


def test_each_provider_key_is_unique_per_sport() -> None:
    assert _migration().SCOPED_KEYS == {
        "uq_sport_teams_code": ("sport_teams", ("sport", "team_code")),
        "uq_sport_players_source_id": ("sport_players", ("sport", "source_player_id")),
        "uq_sport_games_source_id": ("sport_games", ("sport", "source_game_id")),
        "uq_sport_player_aliases_norm": ("sport_player_aliases", ("sport", "alias_name_norm")),
    }


def test_every_nfl_name_is_renamed_or_left_for_0041_to_drop() -> None:
    migration = _migration()
    renamed = set(_renames(migration))
    left = set(migration.GLOBAL_KEYS.values())
    assert renamed.isdisjoint(left)
    assert renamed | left == CATALOG_NFL_NAMES


def test_renames_land_on_sport_names() -> None:
    for old, new in _renames(_migration()).items():
        assert "nfl" not in new and "sport_" in new, (old, new)


def test_downgrade_reverses_upgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = _migration()
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)
    migration.upgrade()
    upgrade = list(statements)
    statements.clear()
    migration.downgrade()

    assert len(statements) == len(upgrade)
    assert sum(s.startswith("CREATE UNIQUE INDEX") for s in upgrade) == 4
    assert sum(s.startswith("DROP INDEX") for s in statements) == 4
    for old, new in _renames(migration).items():
        assert any(f" {old} " in s and s.endswith(f" TO {new}") for s in upgrade), old
        assert any(f" {new} " in s and s.endswith(f" TO {old}") for s in statements), old
