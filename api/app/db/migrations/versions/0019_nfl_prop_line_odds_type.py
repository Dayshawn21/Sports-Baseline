"""Record whether an NFL prop line is a real market line or an alternate.

PrizePicks publishes a ladder per player per market: `goblin` lines set
deliberately low and `demon` lines set deliberately high, each with the payout
adjusted to compensate, around the `standard` line that carries the market's
actual estimate. Only `standard` is comparable to a projection, so without this
column a demon line ranks as a huge false edge.

Mirrors `props.odds_type`, which tennis has carried since migration 0001.

Revision ID: 0019
Revises: 0018
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, Sequence[str], None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable rather than defaulted: existing rows have a real value waiting in
    # raw_json, and defaulting them to 'standard' would assert something false
    # about lines that are mostly demons. `--relink` backfills them.
    op.add_column("nfl_prop_lines", sa.Column("odds_type", sa.Text, nullable=True))
    op.create_index("idx_nfl_prop_lines_odds_type", "nfl_prop_lines", ["odds_type", "market"])


def downgrade() -> None:
    op.drop_index("idx_nfl_prop_lines_odds_type", table_name="nfl_prop_lines")
    op.drop_column("nfl_prop_lines", "odds_type")
