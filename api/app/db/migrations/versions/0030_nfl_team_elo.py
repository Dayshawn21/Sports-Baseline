"""Store pre-game NFL team ELO per team per regular-season game.

Revision ID: 0030
Revises: 0029
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: Union[str, Sequence[str], None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nfl_team_elo",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("nfl_teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_id", sa.BigInteger, sa.ForeignKey("nfl_games.id", ondelete="CASCADE"), nullable=False),
        # Copied from the game so as-of queries can bound by (season, week) without a join.
        sa.Column("season", sa.SmallInteger, nullable=False),
        sa.Column("week", sa.SmallInteger, nullable=False),
        sa.Column("is_home", sa.Boolean, nullable=False),
        sa.Column("elo_pre", sa.Float, nullable=False),
        # NULL until the game is final.
        sa.Column("elo_post", sa.Float, nullable=True),
        sa.Column("model_version", sa.Text, nullable=False),
        sa.Column("computed_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("team_id", "game_id", "model_version", name="uq_nfl_team_elo_team_game_version"),
    )
    op.create_index("ix_nfl_team_elo_season_week", "nfl_team_elo", ["season", "week"])


def downgrade() -> None:
    op.drop_index("ix_nfl_team_elo_season_week", table_name="nfl_team_elo")
    op.drop_table("nfl_team_elo")
