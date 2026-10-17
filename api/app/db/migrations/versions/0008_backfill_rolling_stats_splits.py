"""backfill_rolling_stats_splits

Ensure split_type and split_value exist on player_rolling_stats even on databases
that missed revision 0007. This keeps contextual stats compatible with the live
schema while older environments continue to work.

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE player_rolling_stats
        ADD COLUMN IF NOT EXISTS split_type TEXT
    """)
    op.execute("""
        ALTER TABLE player_rolling_stats
        ADD COLUMN IF NOT EXISTS split_value TEXT
    """)

    op.execute("""
        UPDATE player_rolling_stats
        SET split_type = COALESCE(split_type, 'overall'),
            split_value = COALESCE(split_value, 'all')
        WHERE split_type IS NULL OR split_value IS NULL
    """)

    op.execute("DROP INDEX IF EXISTS idx_rolling_player")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_rolling_player
        ON player_rolling_stats (player_id, stat_period, surface, split_type, split_value)
        NULLS NOT DISTINCT
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_rolling_player")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_rolling_player
        ON player_rolling_stats (player_id, stat_period, surface)
        NULLS NOT DISTINCT
    """)
