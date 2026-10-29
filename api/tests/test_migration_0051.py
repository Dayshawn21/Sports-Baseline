import importlib.util
from io import StringIO
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations


def _offline_sql(direction: str) -> str:
    path = Path(__file__).parents[1] / "app/db/migrations/versions/0051_tennis_elo_experiment_v2.py"
    spec = importlib.util.spec_from_file_location("migration_0051", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert (migration.revision, migration.down_revision) == ("0051", "0050")
    buffer = StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": buffer})
    with Operations.context(context):
        getattr(migration, direction)()
    return buffer.getvalue()


def test_upgrade_admits_v2_and_keeps_v1() -> None:
    sql = _offline_sql("upgrade")
    assert "DROP CONSTRAINT ck_elo_cycle_experiment" in sql
    assert "experiment_version IN ('tennis-elo-source-v1', 'tennis-elo-source-v2')" in sql
    assert "DELETE" not in sql and "UPDATE" not in sql


def test_downgrade_refuses_when_v2_rows_exist_before_restoring_v1_only() -> None:
    sql = _offline_sql("downgrade")
    assert sql.index("RAISE EXCEPTION") < sql.index("DROP CONSTRAINT ck_elo_cycle_experiment")
    assert "CHECK (experiment_version = 'tennis-elo-source-v1')" in sql
    assert "DELETE" not in sql
