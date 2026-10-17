"""rolling_stats_new_columns

Adds first_in_pct, first_won_pct, second_won_pct, dominance_ratio to player_rolling_stats.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("player_rolling_stats", sa.Column("first_in_pct", sa.Numeric(7, 4), nullable=True))
    op.add_column("player_rolling_stats", sa.Column("first_won_pct", sa.Numeric(7, 4), nullable=True))
    op.add_column("player_rolling_stats", sa.Column("second_won_pct", sa.Numeric(7, 4), nullable=True))
    op.add_column("player_rolling_stats", sa.Column("dominance_ratio", sa.Numeric(7, 4), nullable=True))


def downgrade() -> None:
    op.drop_column("player_rolling_stats", "dominance_ratio")
    op.drop_column("player_rolling_stats", "second_won_pct")
    op.drop_column("player_rolling_stats", "first_won_pct")
    op.drop_column("player_rolling_stats", "first_in_pct")
