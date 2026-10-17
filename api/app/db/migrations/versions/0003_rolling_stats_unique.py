"""rolling_stats_unique_constraint

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-08
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the plain index added in 0002 and replace with a unique index.
    # NULLS NOT DISTINCT (PG 15+) ensures (player_id, NULL, stat_period) is
    # treated as a single unique row, enabling ON CONFLICT upserts.
    op.drop_index("idx_rolling_player", table_name="player_rolling_stats")
    op.execute("""
        CREATE UNIQUE INDEX idx_rolling_player
        ON player_rolling_stats (player_id, stat_period, surface)
        NULLS NOT DISTINCT
    """)


def downgrade() -> None:
    op.drop_index("idx_rolling_player", table_name="player_rolling_stats")
    op.create_index(
        "idx_rolling_player",
        "player_rolling_stats",
        ["player_id", "surface", "stat_period"],
    )
