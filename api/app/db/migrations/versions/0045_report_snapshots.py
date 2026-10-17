"""Stored payloads for reports too heavy to compute on the hosted demo (37d).

The NFL model page's 27a line grading replays every week's slate and peaked at
647 MB, past the 512 MB demo instance, so a CLI computes it and the API serves
the stored copy. One row per report and season, replaced on each run.

Revision ID: 0045
Revises: 0044
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0045"
down_revision: Union[str, Sequence[str], None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "report_snapshots",
        sa.Column("report", sa.Text(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("computed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("report", "season", name="pk_report_snapshots"),
    )


def downgrade() -> None:
    op.drop_table("report_snapshots")
