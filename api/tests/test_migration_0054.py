import importlib.util
from io import StringIO
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations


def _offline_sql(direction: str) -> str:
    path = Path(__file__).parents[1] / "app/db/migrations/versions/0054_prediction_shadows.py"
    spec = importlib.util.spec_from_file_location("migration_0054", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert (migration.revision, migration.down_revision) == ("0054", "0053")
    buffer = StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": buffer})
    with Operations.context(context):
        getattr(migration, direction)()
    return " ".join(buffer.getvalue().split())


def test_upgrade_creates_a_sibling_table_and_leaves_predictions_alone() -> None:
    sql = _offline_sql("upgrade")
    assert "CREATE TABLE prediction_shadows" in sql
    assert "FOREIGN KEY(prediction_id) REFERENCES predictions (id) ON DELETE CASCADE" in sql
    assert "UNIQUE (prediction_id, model_version)" in sql
    assert "CHECK (p1_prob > 0 AND p1_prob < 1)" in sql
    assert "ALTER TABLE predictions" not in sql


def test_downgrade_drops_only_the_shadow_table() -> None:
    sql = _offline_sql("downgrade")
    assert sql.strip() == "DROP TABLE prediction_shadows;"
