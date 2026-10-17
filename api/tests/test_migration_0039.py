"""Pins the 0039 compatibility views to the NFL tables' pre-17a columns.

NFL code reads and writes the nfl_* views by these exact column names until 17b,
so a view that drops, adds or renames one would break it at runtime only. The
expected lists below were read from the live schema on 2026-10-01.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

MIGRATION = Path(__file__).parents[1] / "app/db/migrations/versions/0039_shared_team_sport_tables.py"

PRE_17A_COLUMNS: dict[str, list[str]] = {
    "nfl_teams": ["id", "team_code", "name", "conference", "division", "created_at"],
    "nfl_players": ["id", "nflverse_id", "name", "position", "team_id", "created_at", "updated_at"],
    "nfl_player_aliases": ["id", "nfl_player_id", "alias_name", "alias_name_norm", "source", "created_at"],
    "nfl_games": [
        "id", "nflverse_game_id", "season", "week", "game_type", "game_date", "start_utc",
        "home_team_id", "away_team_id", "home_score", "away_score", "status", "created_at",
        "updated_at", "espn_event_id", "spread_line", "total_line", "home_moneyline",
        "away_moneyline", "roof", "home_rest", "away_rest", "temp", "wind",
    ],
    "nfl_prop_lines": [
        "id", "provider", "provider_prop_id", "player_id", "game_id", "market", "line",
        "over_odds", "under_odds", "start_time", "fetched_at", "raw_json", "segment", "odds_type",
    ],
    "nfl_game_odds": [
        "id", "game_id", "book", "market", "line", "first_side", "second_side", "first_odds",
        "second_odds", "first_market_prob", "second_market_prob", "fetched_at", "raw_json",
    ],
    "nfl_prop_predictions": [
        "id", "prop_line_id", "model_version", "projection", "p_over", "p_under", "edge",
        "confidence", "quality_flags", "feature_snapshot", "generated_at", "over_probability_version",
    ],
}


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migration_0039", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _select_list(sql: str) -> list[str]:
    columns = sql.removeprefix("SELECT ").split(" FROM ")[0]
    return [column.strip() for column in columns.split(",")]


def test_each_view_exposes_exactly_the_pre_17a_columns_plus_sport() -> None:
    migration = _migration()
    assert set(migration.TABLE_RENAMES) == set(PRE_17A_COLUMNS)
    for view, expected in PRE_17A_COLUMNS.items():
        exposed = [column.split(" AS ")[-1] for column in _select_list(migration.view_select(view))]
        assert exposed == [*expected, "sport"], view


def test_renamed_columns_are_aliased_back_to_their_old_names() -> None:
    migration = _migration()
    assert "source_game_id AS nflverse_game_id" in _select_list(migration.view_select("nfl_games"))
    assert "source_player_id AS nflverse_id" in _select_list(migration.view_select("nfl_players"))
    assert "player_id AS nfl_player_id" in _select_list(migration.view_select("nfl_player_aliases"))
    for view, renames in migration.COLUMN_RENAMES.items():
        assert set(renames) <= set(PRE_17A_COLUMNS[view]), view


def test_views_read_only_nfl_rows_from_the_shared_tables() -> None:
    migration = _migration()
    for view, table in migration.TABLE_RENAMES.items():
        assert table.startswith("sport_"), view
        assert migration.view_select(view).endswith(f"FROM {table} WHERE sport = 'nfl'"), view


def test_upgrade_analyzes_every_shared_table_last() -> None:
    migration = _migration()
    statements: list[str] = []
    migration.op = type("Op", (), {"execute": staticmethod(statements.append)})()
    migration.upgrade()
    tail = statements[-len(migration.TABLE_RENAMES):]
    assert tail == [f"ANALYZE {table}" for table in migration.TABLE_RENAMES.values()]


def test_migration_follows_0038() -> None:
    migration = _migration()
    assert (migration.revision, migration.down_revision) == ("0039", "0038")
