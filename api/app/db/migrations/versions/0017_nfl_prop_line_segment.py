"""Record which slice of a game an NFL prop line covers.

PrizePicks publishes halves, quarters, and season-long totals under the same
stat_type strings as the full game, so without this column a season receiving
yards line is indistinguishable from a full-game one.

Revision ID: 0017
Revises: 0016
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, Sequence[str], None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing rows were ingested from the full-game league only, so the default
    # backfills them correctly.
    op.add_column(
        "nfl_prop_lines",
        sa.Column("segment", sa.Text, server_default="full_game", nullable=False),
    )
    op.create_index("idx_nfl_prop_lines_segment", "nfl_prop_lines", ["segment", "market"])


def downgrade() -> None:
    op.drop_index("idx_nfl_prop_lines_segment", table_name="nfl_prop_lines")
    op.drop_column("nfl_prop_lines", "segment")
