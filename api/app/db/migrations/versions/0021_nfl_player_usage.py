"""Store nullable NFL player receiving-usage inputs.

Revision ID: 0021
Revises: 0020
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, Sequence[str], None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # These remain nullable because historical rows are not yet backfilled. A
    # zero is a real in-game usage value and must not stand in for unknown data.
    op.add_column("nfl_player_weekly_stats", sa.Column("targets", sa.SmallInteger(), nullable=True))
    op.add_column("nfl_player_weekly_stats", sa.Column("target_share", sa.Float(), nullable=True))
    op.add_column("nfl_player_weekly_stats", sa.Column("air_yards_share", sa.Float(), nullable=True))
    op.add_column("nfl_player_weekly_stats", sa.Column("wopr", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("nfl_player_weekly_stats", "wopr")
    op.drop_column("nfl_player_weekly_stats", "air_yards_share")
    op.drop_column("nfl_player_weekly_stats", "target_share")
    op.drop_column("nfl_player_weekly_stats", "targets")
