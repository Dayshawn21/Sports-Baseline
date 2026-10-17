"""Store weekly NFL injury reports and pre-game depth-chart order per player.

Revision ID: 0026
Revises: 0025
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: Union[str, Sequence[str], None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _player_week_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("nfl_players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.SmallInteger, nullable=False),
        sa.Column("week", sa.SmallInteger, nullable=False),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("nfl_teams.id"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "nfl_player_injuries",
        *_player_week_columns(),
        # NULL report status means the player is on the practice report only, not
        # that a game status of "healthy" was published.
        sa.Column("report_status", sa.Text, nullable=True),
        sa.Column("practice_status", sa.Text, nullable=True),
        sa.Column("primary_injury", sa.Text, nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("player_id", "season", "week", name="uq_nfl_player_injuries_player_week"),
    )
    op.create_index("ix_nfl_player_injuries_season_week", "nfl_player_injuries", ["season", "week"])

    op.create_table(
        "nfl_player_depth_charts",
        *_player_week_columns(),
        sa.Column("position", sa.Text, nullable=False),
        sa.Column("depth_rank", sa.SmallInteger, nullable=False),
        # The pre-game snapshot this week's order came from.
        sa.Column("snapshot_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("player_id", "season", "week", name="uq_nfl_player_depth_charts_player_week"),
    )
    op.create_index("ix_nfl_player_depth_charts_season_week", "nfl_player_depth_charts", ["season", "week"])


def downgrade() -> None:
    op.drop_index("ix_nfl_player_depth_charts_season_week", table_name="nfl_player_depth_charts")
    op.drop_table("nfl_player_depth_charts")
    op.drop_index("ix_nfl_player_injuries_season_week", table_name="nfl_player_injuries")
    op.drop_table("nfl_player_injuries")
