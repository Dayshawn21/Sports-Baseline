"""rolling_stats_period

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Replace window_matches (rolling window int) with stat_period (text label)
    # e.g. 'current_season', '12_month', 'all_time'
    op.drop_index("idx_rolling_player", table_name="player_rolling_stats")
    op.drop_column("player_rolling_stats", "window_matches")
    op.add_column("player_rolling_stats", sa.Column("stat_period", sa.Text, nullable=True))
    op.create_index(
        "idx_rolling_player",
        "player_rolling_stats",
        ["player_id", "surface", "stat_period"],
    )


def downgrade() -> None:
    op.drop_index("idx_rolling_player", table_name="player_rolling_stats")
    op.drop_column("player_rolling_stats", "stat_period")
    op.add_column("player_rolling_stats", sa.Column("window_matches", sa.Integer, nullable=True))
    op.create_index(
        "idx_rolling_player",
        "player_rolling_stats",
        ["player_id", "surface", "window_matches"],
    )
