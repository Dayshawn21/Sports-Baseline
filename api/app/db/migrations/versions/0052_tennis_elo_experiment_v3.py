"""Allow the tennis ELO shadow experiment v3 beside the closed, immutable v1 and v2 rows.

Revision ID: 0052
Revises: 0051
"""
from alembic import op

revision: str = "0052"
down_revision: str = "0051"
branch_labels: None = None
depends_on: None = None

_TABLE = "tennis_elo_freeze_cycles"
_CHECK = "ck_elo_cycle_experiment"


def upgrade() -> None:
    op.drop_constraint(_CHECK, _TABLE, type_="check")
    op.create_check_constraint(
        _CHECK, _TABLE,
        "experiment_version IN ('tennis-elo-source-v1', 'tennis-elo-source-v2', 'tennis-elo-source-v3')",
    )


def downgrade() -> None:
    # Restoring the v1/v2-only check would fail on v3 rows; refuse rather than delete them.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM tennis_elo_freeze_cycles "
        "WHERE experiment_version = 'tennis-elo-source-v3') THEN "
        "RAISE EXCEPTION 'tennis-elo-source-v3 rows exist; downgrade refused'; END IF; END $$"
    )
    op.drop_constraint(_CHECK, _TABLE, type_="check")
    op.create_check_constraint(
        _CHECK, _TABLE, "experiment_version IN ('tennis-elo-source-v1', 'tennis-elo-source-v2')",
    )
