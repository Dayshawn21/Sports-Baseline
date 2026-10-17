"""Store per-game NFL red-zone carries and targets from play-by-play.

Revision ID: 0024
Revises: 0023
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: Union[str, Sequence[str], None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RED_ZONE_COLUMNS = ("rz20_carries", "rz20_targets", "rz5_carries", "rz5_targets")


def upgrade() -> None:
    # NULL means play-by-play was never loaded for the game; 0 means it was and
    # the player had no such plays. The backtest depends on telling them apart.
    for column in RED_ZONE_COLUMNS:
        op.add_column("nfl_player_weekly_stats", sa.Column(column, sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    for column in reversed(RED_ZONE_COLUMNS):
        op.drop_column("nfl_player_weekly_stats", column)
