"""Allow the tennis ELO shadow experiment v2 beside the closed, immutable v1 rows.

Revision ID: 0051
Revises: 0050
"""
from alembic import op

revision: str = "0051"
down_revision: str = "0050"
branch_labels: None = None
depends_on: None = None

_TABLE = "tennis_elo_freeze_cycles"
_CHECK = "ck_elo_cycle_experiment"


def upgrade() -> None:
    op.drop_constraint(_CHECK, _TABLE, type_="check")
    op.create_check_constraint(
        _CHECK, _TABLE, "experiment_version IN ('tennis-elo-source-v1', 'tennis-elo-source-v2')",
    )


def downgrade() -> None:
    # Restoring the v1-only check would fail on v2 rows; refuse rather than delete them.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM tennis_elo_freeze_cycles "
        "WHERE experiment_version <> 'tennis-elo-source-v1') THEN "
        "RAISE EXCEPTION 'tennis-elo-source-v2 rows exist; downgrade refused'; END IF; END $$"
    )
    op.drop_constraint(_CHECK, _TABLE, type_="check")
    op.create_check_constraint(_CHECK, _TABLE, "experiment_version = 'tennis-elo-source-v1'")
