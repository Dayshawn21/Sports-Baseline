"""Store ESPN's current NFL injury statuses beside the nflverse weekly report.

Kept apart from `nfl_player_injuries` so the official report stays queryable on
its own; readers show the more severe of the two. One row per player per week.

Revision ID: 0055
Revises: 0054
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0055"
down_revision: Union[str, Sequence[str], None] = "0054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nfl_player_espn_injuries",
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("sport_players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.SmallInteger, nullable=False),
        sa.Column("week", sa.SmallInteger, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("injury", sa.Text, nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("espn_updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("player_id", "season", "week"),
        sa.CheckConstraint("status IN ('Out', 'Doubtful', 'Questionable')", name="ck_nfl_espn_injuries_status"),
    )
    op.create_index("ix_nfl_player_espn_injuries_season_week", "nfl_player_espn_injuries", ["season", "week"])


def downgrade() -> None:
    op.drop_index("ix_nfl_player_espn_injuries_season_week", table_name="nfl_player_espn_injuries")
    op.drop_table("nfl_player_espn_injuries")
