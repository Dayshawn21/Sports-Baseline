"""Let nfl_prop_predictions hold frozen pre-kickoff slate predictions (build-plan item 27i).

The table was created in 0015 and never written. Frozen rows record what the
slate served before kickoff, which can be a line with no baseline (no
projection) or a market with no fitted P(over), so those columns become
nullable. One row per line snapshot per projection and P(over) version; a
re-run never overwrites.

Revision ID: 0037
Revises: 0036
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: Union[str, Sequence[str], None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NULLABLE = ("projection", "p_over", "p_under")


def upgrade() -> None:
    for column in _NULLABLE:
        op.alter_column("nfl_prop_predictions", column, nullable=True)
    op.add_column("nfl_prop_predictions", sa.Column("over_probability_version", sa.Text, nullable=True))
    op.execute(
        "CREATE UNIQUE INDEX uq_nfl_prop_predictions_line_version ON nfl_prop_predictions "
        "(prop_line_id, model_version, over_probability_version) NULLS NOT DISTINCT"
    )


def downgrade() -> None:
    op.execute("DROP INDEX uq_nfl_prop_predictions_line_version")
    op.drop_column("nfl_prop_predictions", "over_probability_version")
    # The old shape cannot hold a prediction without a projection or P(over),
    # so those frozen rows are dropped rather than invented.
    op.execute(
        "DELETE FROM nfl_prop_predictions WHERE projection IS NULL OR p_over IS NULL OR p_under IS NULL"
    )
    for column in _NULLABLE:
        op.alter_column("nfl_prop_predictions", column, nullable=False)
