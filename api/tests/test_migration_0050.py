import importlib.util
from io import StringIO
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_offline_migration_builds_postgres_constraints_and_reversible_table_order() -> None:
    path = Path(__file__).parents[1] / "app/db/migrations/versions/0050_nhl_context.py"
    spec = importlib.util.spec_from_file_location("migration_0050", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert (migration.revision, migration.down_revision) == ("0050", "0049")
    buffer = StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": buffer})
    with Operations.context(context):
        migration.upgrade()
    sql = buffer.getvalue()
    assert "UNIQUE NULLS NOT DISTINCT (source, kind, scope_date, fetched_at)" in sql
    assert "kind = 'injuries' AND scope_date IS NULL AND source_timestamp IS NOT NULL" in sql
    assert "kind = 'goalies' AND scope_date IS NOT NULL" in sql
    assert "REFERENCES sport_players (id)" in sql and "REFERENCES sport_games (id)" in sql
    assert "time_valid OR game_id IS NULL" in sql
    assert "ix_nhl_context_latest" in sql and "fetched_at DESC, id DESC" in sql
    assert "CASCADE" not in sql
    buffer.seek(0)
    buffer.truncate()
    with Operations.context(context):
        migration.downgrade()
    assert buffer.getvalue().splitlines() == [
        "DROP TABLE nhl_goalie_observations;", "", "DROP TABLE nhl_player_injuries;", "",
        "DROP TABLE nhl_context_snapshots;", "",
    ]
