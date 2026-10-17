"""rolling_stats_contextual_splits

Add split_type and split_value to player_rolling_stats so contextual Tennis
Abstract aggregates can coexist with baseline overall rows.

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("player_rolling_stats", sa.Column("split_type", sa.Text(), nullable=True))
    op.add_column("player_rolling_stats", sa.Column("split_value", sa.Text(), nullable=True))

    op.execute("""
        UPDATE player_rolling_stats
        SET split_type = 'overall',
            split_value = 'all'
        WHERE split_type IS NULL OR split_value IS NULL
    """)

    op.drop_index("idx_rolling_player", table_name="player_rolling_stats")

    op.execute("""
        DELETE FROM player_rolling_stats prs
        USING (
            SELECT id
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY player_id, stat_period, surface, split_type, split_value
                           ORDER BY computed_at DESC, id DESC
                       ) AS rn
                FROM player_rolling_stats
            ) ranked
            WHERE ranked.rn > 1
        ) dupes
        WHERE prs.id = dupes.id
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_rolling_player
        ON player_rolling_stats (player_id, stat_period, surface, split_type, split_value)
        NULLS NOT DISTINCT
    """)


def downgrade() -> None:
    op.drop_index("idx_rolling_player", table_name="player_rolling_stats")

    op.execute("""
        DELETE FROM player_rolling_stats
        WHERE COALESCE(split_type, 'overall') <> 'overall'
           OR COALESCE(split_value, 'all') <> 'all'
    """)

    op.drop_column("player_rolling_stats", "split_value")
    op.drop_column("player_rolling_stats", "split_type")

    op.execute("""
        CREATE UNIQUE INDEX idx_rolling_player
        ON player_rolling_stats (player_id, stat_period, surface)
        NULLS NOT DISTINCT
    """)
