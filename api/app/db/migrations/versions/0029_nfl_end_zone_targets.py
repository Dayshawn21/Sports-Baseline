"""Store per-game NFL end-zone targets from play-by-play.

Revision ID: 0029
Revises: 0028
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: Union[str, Sequence[str], None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL means the play-by-play file has not been loaded; zero means it has
    # and the player received no qualifying target.
    op.add_column("nfl_player_weekly_stats", sa.Column("end_zone_targets", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("nfl_player_weekly_stats", "end_zone_targets")
