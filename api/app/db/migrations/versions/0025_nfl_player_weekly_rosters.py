"""Store each NFL player's team and roster status for every regular-season week.

Revision ID: 0025
Revises: 0024
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: Union[str, Sequence[str], None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nfl_player_weekly_rosters",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("nfl_players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.SmallInteger, nullable=False),
        sa.Column("week", sa.SmallInteger, nullable=False),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("nfl_teams.id"), nullable=False),
        # NFLverse roster status verbatim (ACT, DEV, RES, INA, CUT, RET, EXE). CUT and
        # RET mean the player has no team that week, which the team-as-of rule needs.
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("player_id", "season", "week", name="uq_nfl_player_weekly_rosters_player_week"),
    )
    op.create_index("ix_nfl_player_weekly_rosters_season_week", "nfl_player_weekly_rosters", ["season", "week"])


def downgrade() -> None:
    op.drop_index("ix_nfl_player_weekly_rosters_season_week", table_name="nfl_player_weekly_rosters")
    op.drop_table("nfl_player_weekly_rosters")
